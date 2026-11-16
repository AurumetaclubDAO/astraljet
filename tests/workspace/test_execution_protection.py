"""Żądania, uzgodnienia, restart, netting/hedging oraz BE/trailing."""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from astraljet.workspace.execution import ExecutionBlocked, OrderService
from astraljet.workspace.instruments import Side, eurusd_example
from astraljet.workspace.market import DataMode
from astraljet.workspace.model import MarginMode, OrderRequest, RequestKind, RequestState
from astraljet.workspace.protection import (
    BreakEvenRule, ProtectionState, RuleState, TrailingRule, protection_view,
)
from astraljet.workspace.instruments import FxTable
from astraljet.workspace.simulator import Behaviour, ScriptStep, SimulatedBroker

from .helpers import broker, quote

D = Decimal


def open_req(rid="req-00000001", side=Side.BUY, volume="0.10", sl=None, tp=None):
    return OrderRequest(rid, "SIM-T", RequestKind.OPEN, "EURUSD", side, D(volume),
                        sl=None if sl is None else D(sl), tp=None if tp is None else D(tp))


def trade_deals(b):
    return [d for d in b.history() if d.type.value == "TRADE"]


class Requests(unittest.TestCase):
    def test_fill_and_dedup_same_request_id(self):
        b, clock = broker()
        svc = OrderService(b, clock)
        r1 = svc.submit(open_req())
        r2 = svc.submit(open_req())
        self.assertIs(r1, r2)
        self.assertEqual(r1.state, RequestState.FILLED)
        self.assertEqual(r1.transmissions, 1)
        self.assertEqual(len(trade_deals(b)), 1)

    def test_broker_side_idempotency_on_resend(self):
        b, _ = broker()
        s1 = b.send(open_req())
        s2 = b.send(open_req())
        self.assertEqual(s1, s2)
        self.assertEqual(len(b.positions()), 1)

    def test_reject_is_visible_and_retry_allowed(self):
        b, clock = broker()
        b.script.append(ScriptStep(Behaviour.REJECT, "Brak środków (scenariusz)"))
        svc = OrderService(b, clock)
        rec = svc.submit(open_req())
        self.assertEqual(rec.state, RequestState.REJECTED)
        self.assertIn("Brak środków", rec.message)
        self.assertTrue(svc.retry_allowed(rec.request.request_id))
        self.assertEqual(b.positions(), [])

    def test_partial_fill(self):
        b, clock = broker()
        b.script.append(ScriptStep(Behaviour.PARTIAL, fraction=D("0.5")))
        rec = OrderService(b, clock).submit(open_req(volume="0.10"))
        self.assertEqual(rec.state, RequestState.PARTIALLY_FILLED)
        self.assertEqual(D(rec.broker["filled_volume"]), D("0.05"))
        self.assertEqual(b.positions()[0].volume, D("0.05"))

    def test_timeout_after_execution_is_uncertain_then_reconciled_without_duplicate(self):
        b, clock = broker()
        b.script.append(ScriptStep(Behaviour.TIMEOUT_AFTER_EXECUTION))
        svc = OrderService(b, clock)
        rec = svc.submit(open_req())
        self.assertEqual(rec.state, RequestState.UNCERTAIN)
        self.assertFalse(svc.retry_allowed(rec.request.request_id))
        again = svc.submit(open_req())          # użytkownik klika ponownie
        self.assertEqual(again.transmissions, 1)
        rec = svc.reconcile(rec.request.request_id)
        self.assertEqual(rec.state, RequestState.FILLED)
        self.assertEqual(len(b.positions()), 1)

    def test_timeout_not_received_reconciles_to_not_found(self):
        b, clock = broker()
        b.script.append(ScriptStep(Behaviour.TIMEOUT_NOT_RECEIVED))
        svc = OrderService(b, clock, absent_grace_s=5)
        rec = svc.submit(open_req())
        self.assertEqual(rec.state, RequestState.UNCERTAIN)
        self.assertEqual(svc.reconcile(rec.request.request_id).state, RequestState.UNCERTAIN)  # okno karencji
        clock.advance(6)
        self.assertEqual(svc.reconcile(rec.request.request_id).state, RequestState.NOT_FOUND)
        self.assertTrue(svc.retry_allowed(rec.request.request_id))
        self.assertEqual(b.positions(), [])

    def test_disconnected_not_sent_and_reconcile_keeps_uncertain(self):
        b, clock = broker()
        svc = OrderService(b, clock)
        b.connected = False
        rec = svc.submit(open_req())
        self.assertEqual(rec.state, RequestState.NOT_SENT)
        b.connected = True
        b.script.append(ScriptStep(Behaviour.TIMEOUT_AFTER_EXECUTION))
        rec2 = svc.submit(open_req("req-00000002"))
        b.connected = False
        self.assertEqual(svc.reconcile("req-00000002").state, RequestState.UNCERTAIN)
        b.connected = True
        self.assertEqual(svc.reconcile("req-00000002").state, RequestState.FILLED)
        self.assertEqual(rec2.state, RequestState.FILLED)

    def test_restart_restores_journal_and_does_not_resend(self):
        b, clock = broker()
        b.script.append(ScriptStep(Behaviour.TIMEOUT_AFTER_EXECUTION))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.json"
            OrderService(b, clock, journal_path=path).submit(open_req())
            restarted = OrderService(b, clock, journal_path=path)
            self.assertEqual(restarted.records["req-00000001"].state, RequestState.UNCERTAIN)
            self.assertEqual(len(restarted.open_issues()), 1)
            restarted.submit(open_req())       # ten sam ID po restarcie: brak drugiej wysyłki
            self.assertEqual(len(trade_deals(b)), 1)
            restarted.reconcile_all()
            self.assertEqual(restarted.records["req-00000001"].state, RequestState.FILLED)
            third = OrderService(b, clock, journal_path=path)
            self.assertEqual(third.records["req-00000001"].state, RequestState.FILLED)

    def test_kill_switch_blocks_open_not_close(self):
        b, clock = broker()
        svc = OrderService(b, clock)
        svc.submit(open_req())
        pid = b.positions()[0].position_id
        svc.set_kill_switch(True, "test")
        self.assertEqual(svc.submit(open_req("req-00000002")).state, RequestState.NOT_SENT)
        close = OrderRequest("req-close-01", "SIM-T", RequestKind.CLOSE, "EURUSD", Side.SELL, D("0.10"), position_id=pid)
        self.assertEqual(svc.submit(close).state, RequestState.FILLED)

    def test_non_simulated_adapter_blocked(self):
        class FakeDemo:
            mode = DataMode.DEMO

        with self.assertRaises(ExecutionBlocked):
            OrderService(FakeDemo(), lambda: None)
        with self.assertRaises(ValueError):
            SimulatedBroker("X", "USD", MarginMode.HEDGING, {}, FxTable(), lambda: None, mode=DataMode.LIVE)


class NettingHedging(unittest.TestCase):
    def test_hedging_keeps_two_positions(self):
        b, clock = broker(MarginMode.HEDGING)
        svc = OrderService(b, clock)
        svc.submit(open_req("req-buy-0001", Side.BUY))
        svc.submit(open_req("req-sell-001", Side.SELL))
        self.assertEqual(len(b.positions()), 2)

    def test_netting_reduces_and_reverses(self):
        b, clock = broker(MarginMode.NETTING)
        svc = OrderService(b, clock)
        svc.submit(open_req("req-buy-0001", Side.BUY, "0.10"))
        svc.submit(open_req("req-sell-001", Side.SELL, "0.04"))
        pos = b.positions()
        self.assertEqual(len(pos), 1)
        self.assertEqual((pos[0].side, pos[0].volume), (Side.BUY, D("0.06")))
        svc.submit(open_req("req-sell-002", Side.SELL, "0.10"))
        pos = b.positions()
        self.assertEqual((pos[0].side, pos[0].volume), (Side.SELL, D("0.04")))
        outs = [d for d in trade_deals(b) if d.entry.value == "OUT"]
        self.assertEqual(sum((d.volume for d in outs), D(0)), D("0.10"))

    def test_partial_close_and_commission(self):
        b, clock = broker(MarginMode.HEDGING, commission="3.5")
        svc = OrderService(b, clock)
        svc.submit(open_req(volume="0.10"))
        pid = b.positions()[0].position_id
        b.set_quote(quote("EURUSD", "1.15530", "1.15538", clock()))
        svc.submit(OrderRequest("req-close-01", "SIM-T", RequestKind.CLOSE, "EURUSD", Side.SELL, D("0.04"), position_id=pid))
        self.assertEqual(b.positions()[0].volume, D("0.06"))
        out = [d for d in trade_deals(b) if d.entry.value == "OUT"][0]
        self.assertEqual(out.profit, D("1.15530") * 0 + D("0.04") * D(100000) * (D("1.15530") - D("1.15438")))
        self.assertEqual(out.commission, D("-0.14"))


class Protection(unittest.TestCase):
    def setUp(self):
        self.spec = eurusd_example()
        self.b, self.clock = broker()
        self.svc = OrderService(self.b, self.clock)
        self.svc.submit(open_req(sl="1.14438"))
        self.pos = self.b.positions()[0]   # BUY @1.15438, SL 1.14438

    def move(self, bid_points):
        bid = D("1.15438") + self.spec.from_points(bid_points)
        q = quote("EURUSD", str(bid), str(bid + D("0.00008")), self.clock())
        self.b.set_quote(q)
        return q

    def apply(self, state, q, rid):
        pos = self.b.positions()[0]
        prop = state.evaluate(pos, self.spec, q.bid, q.ask, True)
        if prop is None:
            return None
        state.mark_sent(prop, rid)
        rec = self.svc.submit(OrderRequest(rid, "SIM-T", RequestKind.MODIFY_SLTP, "EURUSD", sl=prop.target,
                                           position_id=pos.position_id))
        state.mark_outcome(rec.state.value, rec.message, self.b.positions()[0])
        return prop

    def test_be_buy_target_is_entry_plus_offset_not_trigger(self):
        st = ProtectionState(self.pos.position_id, be=BreakEvenRule(D(100), D(10)))
        self.assertIsNone(self.apply(st, self.move(50), "m-00000001"))
        self.assertIs(st.be_status.state, RuleState.WAITING)
        prop = self.apply(st, self.move(100), "m-00000002")
        self.assertEqual(prop.target, D("1.15448"))
        self.assertIs(st.be_status.state, RuleState.CONFIRMED)
        self.assertEqual(self.b.positions()[0].sl, D("1.15448"))

    def test_be_sell_sign(self):
        spec = self.spec
        pos = self.pos.__class__("S1", "SIM-T", "EURUSD", Side.SELL, D("0.1"), D("1.15438"), self.pos.opened_at)
        self.assertEqual(BreakEvenRule(D(100), D(10)).target(pos, spec), D("1.15428"))

    def test_be_invalid_when_offset_not_below_trigger(self):
        st = ProtectionState(self.pos.position_id, be=BreakEvenRule(D(10), D(10)))
        self.apply(st, self.move(200), "m-00000001")
        self.assertIs(st.be_status.state, RuleState.ERROR)

    def test_trailing_and_be_conflict_never_worsens(self):
        st = ProtectionState(self.pos.position_id, be=BreakEvenRule(D(100), D(10)),
                             trailing=TrailingRule(D(500), D(250), D(10)))
        prop = self.apply(st, self.move(724), "m-00000001")
        self.assertEqual(prop.source, "trailing")                  # lepszy niż BE (+474 > +10)
        self.assertEqual(self.b.positions()[0].sl, D("1.15912"))
        self.apply(st, self.move(800), "m-00000002")
        sl_after = self.b.positions()[0].sl
        self.assertEqual(sl_after, D("1.15988"))
        self.assertIsNone(self.apply(st, self.move(600), "m-00000003"))   # cena spada: SL bez zmian
        self.assertEqual(self.b.positions()[0].sl, sl_after)
        self.assertIs(st.be_status.state, RuleState.SATISFIED)
        with self.assertRaises(ValueError):
            st.manual(self.b.positions()[0], D("1.15500"))
        worse = st.manual(self.b.positions()[0], D("1.15500"), acknowledge_worse=True)
        self.assertTrue(worse.worsens)

    def test_rejected_modification_is_error_not_protected_and_not_retried(self):
        st = ProtectionState(self.pos.position_id, be=BreakEvenRule(D(100), D(10)))
        self.b.script.append(ScriptStep(Behaviour.REJECT, "Odrzucone"))
        self.apply(st, self.move(150), "m-00000001")
        self.assertIs(st.be_status.state, RuleState.ERROR)
        self.assertEqual(self.b.positions()[0].sl, D("1.14438"))
        self.assertIsNone(self.apply(st, self.move(160), "m-00000002"))    # identyczny cel nie jest ponawiany

    def test_protected_only_after_confirmed_sl(self):
        b, clock = broker()
        OrderService(b, clock).submit(open_req())
        pos = b.positions()[0]
        self.assertEqual(protection_view(pos, self.spec, FxTable(), "USD", False).status, "UNPROTECTED")
        self.assertEqual(protection_view(pos, self.spec, FxTable(), "USD", True).status, "CHANGE_PENDING")
        view = protection_view(self.pos, self.spec, FxTable(), "USD", False)
        self.assertEqual(view.status, "PROTECTED")
        self.assertEqual(view.pnl_at_sl_account, D("-100.00000"))

    def test_uncertain_modification_waits(self):
        st = ProtectionState(self.pos.position_id, be=BreakEvenRule(D(100), D(10)))
        self.b.script.append(ScriptStep(Behaviour.TIMEOUT_AFTER_EXECUTION))
        self.apply(st, self.move(150), "m-00000001")
        self.assertIs(st.be_status.state, RuleState.UNCERTAIN)
        self.assertIsNone(st.evaluate(self.b.positions()[0], self.spec, D("1.16"), D("1.16008"), True))
        rec = self.svc.reconcile("m-00000001")
        st.mark_outcome(rec.state.value, rec.message, self.b.positions()[0])
        self.assertIs(st.be_status.state, RuleState.CONFIRMED)

    def test_stale_quote_pauses_evaluation(self):
        st = ProtectionState(self.pos.position_id, trailing=TrailingRule(D(500), D(250)))
        q = self.move(900)
        self.assertIsNone(st.evaluate(self.b.positions()[0], self.spec, q.bid, q.ask, False))

    def test_sl_hit_closes_position_in_simulator(self):
        self.move(-1100)
        self.assertEqual(self.b.positions(), [])


if __name__ == "__main__":
    unittest.main()
