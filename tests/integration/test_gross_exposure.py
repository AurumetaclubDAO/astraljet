"""Limit łącznej ekspozycji brutto mandatu (luka z planu D3, zlecenie koordynatora 20.11.2026).

Limit `max_gross_exposure` liczy sumę wartości bezwzględnych pozycji we wszystkich
instrumentach środowiska PO zleceniu. Ceny pozostałych pozycji pochodzą z `FrozenContext.marks`
(cena zaobserwowana razem z danymi sygnału, w chwili `data_observed_at`); instrument zlecenia
wyceniany jest ceną referencyjną zlecenia. Brak ceny oznacza odmowę, nie domysł.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal

from astraljet.application.mandates import MandateRequest, create_mandate
from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError
from astraljet.executor.demo import DemoAdapter
from astraljet.executor.paper import PaperExecutor

from tests.executor_support import allowed_risk
from tests.integration.test_tq_lessons import NOW, ExecutorCase, order


class GrossExposureCase(ExecutorCase):
    def setUp(self) -> None:
        super().setUp()
        self.executor = PaperExecutor(self.database, self.guard)
        self.counter = 0

    def with_limit(self, value: object) -> object:
        return dataclasses.replace(self.mandate, limits={**self.mandate.limits, "max_gross_exposure": value})

    def submit(self, intent, *, mandate_record=None, marks=None) -> ExecutionResultState:
        self.counter += 1
        ctx = dataclasses.replace(self.ctx(mandate_record=mandate_record), marks=marks or {})
        return self.executor.submit_intent(ctx, intent, idempotency_key=f"gross-{self.counter:04d}", now=NOW).state

    def position(self) -> dict[str, str]:
        return self.executor.positions(self.environment_id).quantities


class GrossLimitAcrossInstruments(GrossExposureCase):
    def test_second_instrument_is_refused_when_portfolio_would_exceed_limit(self) -> None:
        limited = self.with_limit("15000")
        self.assertIs(self.submit(order("G-BTC", quantity="9", price="1000"), mandate_record=limited),
                      ExecutionResultState.ACCEPTED)
        blocker = self.blocker(lambda: self.submit(order("G-ETH", instrument="ETHUSD", quantity="9", price="1000"),
                                                   mandate_record=limited, marks={"BTCUSD": Decimal("1000")}))
        self.assertEqual("gross_exposure_exceeded", blocker)
        self.assertEqual({"BTCUSD": "9"}, self.position())
        self.assertEqual(["gross_exposure_exceeded"], self.blocked_events())

    def test_order_inside_limit_is_accepted(self) -> None:
        limited = self.with_limit("15000")
        self.submit(order("G-BTC", quantity="9", price="1000"), mandate_record=limited)
        self.assertIs(self.submit(order("G-ETH", instrument="ETHUSD", quantity="6", price="1000"),
                                  mandate_record=limited, marks={"BTCUSD": Decimal("1000")}),
                      ExecutionResultState.ACCEPTED)
        self.assertEqual({"BTCUSD": "9", "ETHUSD": "6"}, self.position())

    def test_other_positions_are_valued_at_their_mark_not_at_entry(self) -> None:
        limited = self.with_limit("15000")
        self.submit(order("G-BTC", quantity="9", price="1000"), mandate_record=limited)
        # BTC podrożał: 9 * 1200 = 10800, plus 5 ETH po 1000 = 15800 > 15000.
        self.assertEqual("gross_exposure_exceeded", self.blocker(lambda: self.submit(
            order("G-ETH", instrument="ETHUSD", quantity="5", price="1000"),
            mandate_record=limited, marks={"BTCUSD": Decimal("1200")})))

    def test_short_position_counts_as_absolute_value(self) -> None:
        limits = {**self.mandate.limits, "allow_short": True, "max_gross_exposure": "15000"}
        limited = dataclasses.replace(self.mandate, limits=limits)
        self.submit(order("G-SHORT", side="sell", quantity="9", price="1000"), mandate_record=limited)
        self.assertEqual({"BTCUSD": "-9"}, self.position())
        self.assertEqual("gross_exposure_exceeded", self.blocker(lambda: self.submit(
            order("G-ETH", instrument="ETHUSD", quantity="7", price="1000"),
            mandate_record=limited, marks={"BTCUSD": Decimal("1000")})))


class MissingPriceIsRefusal(GrossExposureCase):
    def test_missing_mark_for_other_position_is_refused(self) -> None:
        limited = self.with_limit("50000")
        self.submit(order("G-BTC", quantity="1", price="1000"), mandate_record=limited)
        self.assertEqual("gross_exposure_price_missing", self.blocker(lambda: self.submit(
            order("G-ETH", instrument="ETHUSD", quantity="1", price="1000"), mandate_record=limited)))
        self.assertEqual({"BTCUSD": "1"}, self.position())
        self.assertEqual(["gross_exposure_price_missing"], self.blocked_events())

    def test_invalid_mark_is_treated_as_missing(self) -> None:
        limited = self.with_limit("50000")
        self.submit(order("G-BTC", quantity="1", price="1000"), mandate_record=limited)
        for number, bad in enumerate((Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), "abc", None)):
            with self.subTest(mark=bad):
                self.assertEqual("gross_exposure_price_missing", self.blocker(lambda: self.submit(
                    order(f"G-ETH-{number}", instrument="ETHUSD", quantity="1", price="1000"),
                    mandate_record=limited, marks={"BTCUSD": bad})))

    def test_order_instrument_needs_no_mark_and_flat_positions_need_none(self) -> None:
        limited = self.with_limit("50000")
        self.submit(order("G-BTC-1", quantity="2", price="1000"), mandate_record=limited)
        self.submit(order("G-BTC-2", side="sell", quantity="2", price="1000"), mandate_record=limited)
        # BTC ma ilość 0: nie wymaga ceny. Zlecenie na BTC wyceniane jest własną ceną referencyjną.
        self.assertIs(self.submit(order("G-ETH", instrument="ETHUSD", quantity="1", price="1000"),
                                  mandate_record=limited), ExecutionResultState.ACCEPTED)
        self.assertIs(self.submit(order("G-ETH-2", instrument="ETHUSD", quantity="1", price="1100"),
                                  mandate_record=limited), ExecutionResultState.ACCEPTED)


class ReducingOrderPassesAboveLimit(GrossExposureCase):
    def setUp(self) -> None:
        super().setUp()
        # Portfel 18000 zbudowany pod mandatem bez limitu łącznego (zachowanie jak dotąd).
        self.submit(order("G-BTC", quantity="9", price="1000"))
        self.submit(order("G-ETH", instrument="ETHUSD", quantity="9", price="1000"))
        self.limited = self.with_limit("15000")

    def test_reducing_order_passes_even_without_marks(self) -> None:
        self.assertIs(self.submit(order("G-ETH-SELL", instrument="ETHUSD", side="sell", quantity="2", price="1000"),
                                  mandate_record=self.limited), ExecutionResultState.ACCEPTED)
        self.assertEqual({"BTCUSD": "9", "ETHUSD": "7"}, self.position())

    def test_increasing_order_is_refused_while_above_limit(self) -> None:
        self.assertEqual("gross_exposure_exceeded", self.blocker(lambda: self.submit(
            order("G-BTC-MORE", quantity="1", price="1000"),
            mandate_record=self.limited, marks={"ETHUSD": Decimal("1000")})))



class FlipIsNotReduction(GrossExposureCase):
    def test_flip_through_zero_to_larger_size_is_judged_by_limit(self) -> None:
        self.submit(order("G-BTC", quantity="9", price="1000"))
        self.submit(order("G-ETH", instrument="ETHUSD", quantity="4", price="1000"))
        limits = {**self.mandate.limits, "allow_short": True, "max_gross_exposure": "13500"}
        flipping = dataclasses.replace(self.mandate, limits=limits)
        # ETH 4 -> -5: pozycja rośnie co do wielkości; portfel 9000 + 5000 = 14000 > 13500.
        self.assertEqual("gross_exposure_exceeded", self.blocker(lambda: self.submit(
            order("G-ETH-FLIP", instrument="ETHUSD", side="sell", quantity="9", price="1000"),
            mandate_record=flipping, marks={"BTCUSD": Decimal("1000")})))
        self.assertEqual({"BTCUSD": "9", "ETHUSD": "4"}, self.position())


class LimitWithoutKeyBehavesAsBefore(GrossExposureCase):
    def test_mandate_without_gross_limit_accepts_portfolio_above_single_limit(self) -> None:
        self.assertIs(self.submit(order("G-BTC", quantity="9", price="1000")), ExecutionResultState.ACCEPTED)
        self.assertIs(self.submit(order("G-ETH", instrument="ETHUSD", quantity="9", price="1000")),
                      ExecutionResultState.ACCEPTED)
        self.assertEqual({"BTCUSD": "9", "ETHUSD": "9"}, self.position())


class InvalidGrossLimit(GrossExposureCase):
    def test_broken_gross_limit_is_invalid_limits(self) -> None:
        for value in ("NaN", "0", "-1", "abc", None, True, "Infinity", "-Infinity", ""):
            with self.subTest(value=value):
                self.assertEqual("invalid_limits", self.blocker(lambda: self.guard.authorize(
                    context=self.ctx(mandate_record=self.with_limit(value)), intent=order("G-OK"), now=NOW)))


class MandateCannotExceedRisk(ExecutorCase):
    def request(self, limits: dict[str, object]) -> MandateRequest:
        return MandateRequest(
            authorized_by="Karol", strategy_id="STRAT-12345678", strategy_version=1, code_hash="B" * 64,
            environment=ExecutionEnvironment.PAPER_CONTINUOUS, environment_id="paper-test", account_id=None,
            instruments=("BTCUSD", "ETHUSD"), limits=limits,
            starts_at="2025-01-02T00:00:00Z", expires_at="2025-12-30T00:00:00Z",
            stop_conditions=("kill switch",), max_data_age_seconds=60,
        )

    def test_gross_limit_must_fit_risk_decision(self) -> None:
        base = {"max_notional": "10000", "max_position_quantity": "10"}
        risk = dataclasses.replace(allowed_risk(), limits={**base, "max_gross_exposure": "15000"})
        record = create_mandate(risk_decision=risk, request=self.request({**base, "max_gross_exposure": "15000"}),
                                owner="Karol")
        self.assertEqual("15000", record.limits["max_gross_exposure"])
        for asked, allowed in (("15001", "15000"), ("15000", None)):
            with self.subTest(asked=asked, allowed=allowed):
                risk_limits = dict(base) if allowed is None else {**base, "max_gross_exposure": allowed}
                with self.assertRaises(DomainBlockedError) as caught:
                    create_mandate(risk_decision=dataclasses.replace(allowed_risk(), limits=risk_limits),
                                   request=self.request({**base, "max_gross_exposure": asked}), owner="Karol")
                self.assertEqual("mandate_limits_exceed_risk", caught.exception.blocker)


class DuplicateIntentIsCleanRefusal(GrossExposureCase):
    def test_same_intent_id_under_new_key_and_signal_is_refused_with_audit(self) -> None:
        self.submit(order("G-TWICE", signal_id="SIG-1"))
        self.assertEqual("duplicate_intent", self.blocker(lambda: self.submit(order("G-TWICE", signal_id="SIG-2"))))
        self.assertEqual({"BTCUSD": "1"}, self.position())
        self.assertEqual(["duplicate_intent"], self.blocked_events())


class DemoDoesNotIgnoreGrossLimit(ExecutorCase):
    environment = ExecutionEnvironment.BROKER_DEMO
    environment_id = "demo-test"
    account_id = "DEMO-001"

    def test_demo_adapter_refuses_mandate_with_gross_limit_it_cannot_value(self) -> None:
        adapter = DemoAdapter(self.database, self.guard, confirmed_demo_account="DEMO-001")
        limited = dataclasses.replace(self.mandate, limits={**self.mandate.limits, "max_gross_exposure": "15000"})
        self.assertEqual("gross_exposure_unsupported", self.blocker(lambda: adapter.submit_intent(
            self.ctx(mandate_record=limited), order("G-DEMO"), idempotency_key="gross-demo-1", now=NOW)))
        self.assertEqual([], self.intents())
