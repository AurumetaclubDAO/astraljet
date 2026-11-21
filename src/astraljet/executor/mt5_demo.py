"""Adapter zleceń MetaTrader 5 wyłącznie dla rachunku DEMO (próba łączności i blokad, 21.11.2026).

Zgoda Karola: „Tak, testuj zlecenia” (konto DEMO), „Tak, pisz próbę”. Prawdziwe zlecenie wysyła tylko
skrypt scripts/demo_order_probe.py uruchomiony przez Karola.

Blokady:
- twarda lista wywołań SDK (OrderSDK); poza nią PermissionError;
- bramka konta przed order_check, przed order_send i po order_send: trade_mode DEMO, numer i serwer
  z lokalnej konfiguracji (poza Git), terminal połączony i z włączonym Algo Trading.
  Rachunek inny niż DEMO = odmowa i wyłącznik awaryjny środowiska;
- każda intencja przechodzi przez ExecutorGuard.authorize (mandat BROKER_DEMO, autoryzacja Karola,
  instrument, limity, lease, kill switch, brak nierozstrzygniętych realizacji);
- zapis „write-ahead”: intencja trafia do bazy ze stanem uncertain PRZED order_send; do potwierdzenia
  wyniku blokuje każde nowe zlecenie w środowisku (bramka: unresolved_execution);
- duplikat klucza, sygnału albo intencji nie wysyła zlecenia;
- brak pętli ponowień: jedno order_send na intencję.
Numer rachunku, saldo i serwer nie trafiają do zdarzeń ani wyników.

Bramka rachunku stoi także przed każdym odczytem pozycji i historii (reconcile, positions).

Znane ograniczenie uzgodnienia: bez wyniku order_send intencję rozpoznajemy po komentarzu, który broker
może skrócić lub nadpisać. Dlatego deal z magic adaptera, którego nie da się przypisać do żadnej znanej
intencji, zostawia wynik w stanie uncertain (do ręcznego sprawdzenia), a nie rejected.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import canonical_json
from astraljet.infrastructure.database import Database

from .guard import GROSS_LIMIT_KEY, ExecutorGuard, _iso, gross_exposure_limit
from .paper import DUPLICATE_INTENT, _receipt_from_row
from .ports import ExecutionReceipt, FrozenContext, Health, OrderIntent, PositionSnapshot

ALLOWED_CALLS = frozenset({
    "initialize", "shutdown", "last_error", "account_info", "terminal_info", "symbol_info",
    "symbol_info_tick", "order_check", "order_send", "positions_get", "history_deals_get",
})
RETCODE_DONE = 10009
RETCODE_DONE_PARTIAL = 10010
PROBE_MAGIC = 2026112101


class OrderSDK:
    """Przepuszcza tylko ALLOWED_CALLS i stałe (WIELKIE_LITERY).

    order_check i order_send sprawdzają sam słownik zlecenia, niezależnie od bramki wykonawcy:
    tylko natychmiastowa transakcja, symbol z listy, wolumen równy najmniejszemu lotowi, magic próby,
    kupno bez ticketu albo sprzedaż z ticketem pozycji (rachunek hedge: sprzedaż bez ticketu otworzyłaby
    drugą pozycję). Wszystko inne to PermissionError bez wywołania SDK.
    """

    REQUEST_KEYS = frozenset({"action", "symbol", "volume", "type", "price", "deviation", "magic", "comment",
                              "type_time", "type_filling", "position"})

    def __init__(self, sdk, *, symbols: tuple[str, ...] = (), magic: int = PROBE_MAGIC) -> None:
        self._sdk = sdk
        self._symbols = frozenset(symbols)
        self._magic = magic

    def validate_request(self, request: dict) -> None:
        sdk = self._sdk
        if not isinstance(request, dict) or set(request) - self.REQUEST_KEYS:
            raise PermissionError("Zlecenie zawiera pola spoza dozwolonej listy.")
        if request.get("action") != sdk.TRADE_ACTION_DEAL:
            raise PermissionError("Dozwolona jest tylko natychmiastowa transakcja (TRADE_ACTION_DEAL).")
        if request.get("symbol") not in self._symbols:
            raise PermissionError("Symbol spoza mandatu.")
        if request.get("magic") != self._magic:
            raise PermissionError("Zlecenie bez magic próby.")
        info = sdk.symbol_info(request["symbol"])
        if info is None or _num(request.get("volume")) != _num(info.volume_min):
            raise PermissionError("Wolumen musi być równy najmniejszemu lotowi symbolu.")
        kind, position = request.get("type"), request.get("position")
        if kind == sdk.ORDER_TYPE_BUY and position is None:
            return
        if kind == sdk.ORDER_TYPE_SELL and isinstance(position, int) and position > 0:
            return
        raise PermissionError("Dozwolone: kupno bez ticketu albo sprzedaż zamykająca wskazaną pozycję.")

    def order_check(self, request):
        self.validate_request(request)
        return self._sdk.order_check(request)

    def order_send(self, request):
        self.validate_request(request)
        return self._sdk.order_send(request)

    def __getattr__(self, name: str):
        if name.isupper() or name in ALLOWED_CALLS:
            return getattr(self._sdk, name)
        raise PermissionError(f"Adapter DEMO nie wywołuje MetaTrader5.{name}")


@dataclass(frozen=True, slots=True)
class DemoAccountRule:
    """Lokalna (poza Git) definicja jedynego rachunku, na który wolno wysłać zlecenie."""

    label: str  # etykieta w mandacie (account_id), bez numeru rachunku
    login: int
    server: str


def _comment(intent_id: str) -> str:
    return "AJ-" + hashlib.sha256(intent_id.encode("utf-8")).hexdigest()[:12]


def _num(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Niepoprawna liczba z terminala.") from exc
    if not result.is_finite():
        raise ValidationError("Niepoprawna liczba z terminala.")
    return result


class MT5DemoAdapter:
    def __init__(
        self,
        database: Database,
        guard: ExecutorGuard,
        sdk: object,
        rule: DemoAccountRule,
        *,
        symbols: tuple[str, ...],
        environment: ExecutionEnvironment = ExecutionEnvironment.BROKER_DEMO,
        magic: int = PROBE_MAGIC,
        deviation_points: int = 50,
    ) -> None:
        # Adapter nie ma ścieżki dla rachunku innego niż DEMO.
        if environment is not ExecutionEnvironment.BROKER_DEMO:
            raise ValidationError("MT5DemoAdapter działa wyłącznie w środowisku BROKER_DEMO.")
        if "demo" not in rule.server.casefold():
            raise ValidationError("Wskazany serwer nie jest serwerem DEMO.")
        if not symbols:
            raise ValidationError("Adapter wymaga jawnej listy symboli.")
        self.database = database
        self.guard = guard
        self.sdk = OrderSDK(sdk, symbols=symbols, magic=magic)
        self.rule = rule
        self.magic = magic
        self.deviation_points = deviation_points

    # ---------- bramka rachunku ----------

    def _account_problem(self) -> tuple[str, str, bool] | None:
        """(komunikat, kod, czy to rachunek REAL) albo None, gdy wolno zlecać."""
        account = self.sdk.account_info()
        if account is None:
            return "Brak odczytu rachunku.", "demo_account_unreadable", False
        if account.trade_mode != self.sdk.ACCOUNT_TRADE_MODE_DEMO:
            return "Terminal nie jest zalogowany na rachunek DEMO.", "not_demo_account", True
        if account.login != self.rule.login or account.server != self.rule.server:
            return "Terminal jest zalogowany na inny rachunek DEMO niż wskazany.", "demo_account_mismatch", False
        terminal = self.sdk.terminal_info()
        if terminal is None or not terminal.connected:
            return "Terminal bez połączenia z serwerem.", "terminal_disconnected", False
        if terminal.trade_allowed is not True:
            return "Algo Trading w terminalu jest wyłączone.", "algo_trading_disabled", False
        return None

    def ensure_demo(self, context: FrozenContext, stage: str) -> None:
        self.require_demo(context.environment_id, context.worker_id, stage)

    def require_demo(self, environment_id: str, actor: str, stage: str) -> None:
        """Bramka rachunku przed każdym zleceniem ORAZ przed każdym odczytem pozycji i historii."""
        problem = self._account_problem()
        if problem is None:
            return
        message, code, real = problem
        if real:
            # Wykrycie LIVE: rozłączenie i trwały wyłącznik awaryjny (zdejmuje go tylko Karol).
            try:
                self.sdk.shutdown()
            except Exception:  # noqa: BLE001 - rozłączenie nie może zablokować zapisu wyłącznika
                pass
            self.guard.activate_kill_switch(
                environment_id,
                reason=f"Rachunek inny niż DEMO wykryty ({stage}).",
                idempotency_key=f"mt5-demo-not-demo:{environment_id}",
                now=datetime.now(timezone.utc),
            )
        raise self.guard.deny_execution(
            f"{message} Etap: {stage}.", code, "Zaloguj terminal na wskazany rachunek DEMO; nie wysyłaj zlecenia.",
            environment_id=environment_id, actor=actor,
        )

    def health(self, mandate: object) -> Health:
        if mandate.environment is not ExecutionEnvironment.BROKER_DEMO:
            return Health(ExecutionResultState.REJECTED, "Mandat nie dotyczy BROKER_DEMO.")
        if mandate.account_id != self.rule.label:
            return Health(ExecutionResultState.REJECTED, "Mandat wskazuje inny rachunek DEMO.")
        problem = self._account_problem()
        if problem:
            return Health(ExecutionResultState.REJECTED, problem[0])
        return Health(ExecutionResultState.ACCEPTED, "Rachunek DEMO potwierdzony.")

    # ---------- wycena i wolumen ----------

    def _volume(self, context: FrozenContext, intent: OrderIntent, info) -> Decimal:
        """Ilość intencji jest w jednostkach instrumentu; wolumen MT5 = ilość / wielkość kontraktu."""
        contract = _num(info.trade_contract_size)
        step, vmin, vmax = _num(info.volume_step), _num(info.volume_min), _num(info.volume_max)
        if contract <= 0 or step <= 0:
            raise self.guard.deny_execution("Niepoprawne parametry symbolu.", "symbol_parameters_invalid",
                                            "Sprawdź symbol w terminalu.", environment_id=context.environment_id,
                                            actor=context.worker_id)
        volume = intent.quantity / contract
        if volume < vmin or volume > vmax or volume % step != 0:
            raise self.guard.deny_execution(
                "Ilość nie odpowiada dozwolonemu wolumenowi symbolu.", "volume_not_allowed",
                "Podaj ilość będącą wielokrotnością kroku wolumenu, nie mniejszą niż minimum.",
                environment_id=context.environment_id, actor=context.worker_id)
        return volume

    def _gross_after(self, intent: OrderIntent, closing: bool) -> Decimal:
        """Łączna ekspozycja brutto rachunku po zleceniu, z pozycji i cen terminala."""
        positions = self.sdk.positions_get()
        if positions is None:
            raise ValidationError("Brak odczytu pozycji.")
        gross = Decimal("0")
        for p in positions:
            info = self.sdk.symbol_info(p.symbol)
            if info is None:
                raise ValidationError("Brak parametrów symbolu otwartej pozycji.")
            gross += abs(_num(p.volume)) * _num(info.trade_contract_size) * _num(p.price_current)
        if not closing:
            gross += intent.quantity * intent.reference_price
        return gross

    # ---------- zlecenie ----------

    def submit_intent(
        self,
        context: FrozenContext,
        intent: OrderIntent,
        *,
        idempotency_key: str,
        now: datetime,
        position_ticket: int | None = None,
    ) -> ExecutionReceipt:
        if len(idempotency_key) < 8:
            raise ValidationError("Klucz idempotencji intencji jest za krótki.")
        with self.database.connect() as connection:
            duplicate = connection.execute(
                "SELECT * FROM execution_intents WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        if duplicate:
            return _receipt_from_row(duplicate)
        actor = context.worker_id

        def deny(message: str, code: str, action: str):
            return self.guard.deny_execution(message, code, action, environment_id=context.environment_id, actor=actor)

        if context.environment is not ExecutionEnvironment.BROKER_DEMO or context.mandate.account_id != self.rule.label:
            raise deny("Adapter MT5 przyjmuje wyłącznie mandat BROKER_DEMO dla wskazanego rachunku.",
                       "wrong_adapter", "Użyj mandatu BROKER_DEMO.")
        self.guard.authorize(context=context, intent=intent, now=now)
        with self.database.connect() as connection:
            early = self._duplicate_denial(connection, context, intent)
        if early:  # duplikat rozpoznany przed jakimkolwiek odczytem terminala
            raise deny(*early)
        self.ensure_demo(context, "przed zleceniem")

        info = self.sdk.symbol_info(intent.instrument)
        if info is None or not info.visible:
            raise deny("Symbol niedostępny w Market Watch.", "symbol_unavailable", "Dodaj symbol ręcznie w terminalu.")
        volume = self._volume(context, intent, info)
        closing = position_ticket is not None
        if not closing and intent.side != "buy":
            # Rachunek hedge: sprzedaż bez ticketu nie zamyka kupna, tylko otwiera przeciwną pozycję.
            raise deny("Sprzedaż jest dozwolona tylko jako zamknięcie wskazanej pozycji (ticket).",
                       "sell_without_position", "Podaj ticket zamykanej pozycji.")
        if closing:
            held = self.sdk.positions_get(ticket=position_ticket)
            if not held or held[0].symbol != intent.instrument or int(held[0].magic) != self.magic:
                raise deny("Zamykana pozycja nie istnieje albo nie należy do wykonawcy.", "position_not_owned",
                           "Uzgodnij pozycje przed zamknięciem.")
            pos = held[0]
            expected_side = "sell" if pos.type == self.sdk.POSITION_TYPE_BUY else "buy"
            if intent.side != expected_side or _num(pos.volume) != volume:
                raise deny("Zamknięcie musi mieć przeciwną stronę i pełny wolumen pozycji.", "close_mismatch",
                           "Popraw intencję zamknięcia.")
        limit = gross_exposure_limit(context.mandate.limits)  # poprawność sprawdziła bramka
        if limit is not None and not closing and self._gross_after(intent, closing) > limit:
            raise deny("Po zleceniu łączna ekspozycja rachunku przekroczyłaby limit mandatu.",
                       "gross_exposure_exceeded", "Zmniejsz zlecenie; nie zwiększaj limitu bez decyzji Karola.")

        tick = self.sdk.symbol_info_tick(intent.instrument)
        if tick is None or not tick.ask or not tick.bid:
            raise deny("Brak bieżącej ceny symbolu.", "price_unavailable", "Sprawdź notowania w terminalu.")
        price = tick.ask if intent.side == "buy" else tick.bid
        request = {
            "action": self.sdk.TRADE_ACTION_DEAL,
            "symbol": intent.instrument,
            "volume": float(volume),
            "type": self.sdk.ORDER_TYPE_BUY if intent.side == "buy" else self.sdk.ORDER_TYPE_SELL,
            "price": price,
            "deviation": self.deviation_points,
            "magic": self.magic,
            "comment": _comment(intent.intent_id),
            "type_time": self.sdk.ORDER_TIME_GTC,
            "type_filling": self._filling(info),
        }
        if closing:
            request["position"] = int(position_ticket)
        try:
            self.sdk.validate_request(request)  # granica SDK, niezależnie od bramki
        except PermissionError as exc:
            raise deny(f"Zlecenie odrzucone na granicy SDK: {exc}", "request_not_allowed", "Popraw intencję.") from exc

        external_reference = f"MT5D-{intent.intent_id}"
        created_at = _iso(now)
        denial = None
        with self.database.transaction() as connection:
            if connection.execute("SELECT 1 FROM execution_intents WHERE idempotency_key = ?",
                                  (idempotency_key,)).fetchone():
                denial = DUPLICATE_INTENT
            else:
                denial = self._duplicate_denial(connection, context, intent)
            if denial is None:
                connection.execute(
                    "INSERT INTO execution_signal_claims(environment_id, signal_id, intent_id, idempotency_key, claimed_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (context.environment_id, intent.signal_id, intent.intent_id, idempotency_key, created_at))
                # Write-ahead: do potwierdzenia wyniku stan uncertain blokuje kolejne zlecenia.
                connection.execute(
                    """INSERT INTO execution_intents(idempotency_key, intent_id, environment_id, mandate_id, state,
                       external_reference, payload_json, response_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 'uncertain', ?, ?, ?, ?, ?)""",
                    (idempotency_key, intent.intent_id, context.environment_id, context.mandate.record_id,
                     external_reference, canonical_json(intent), canonical_json({"stage": "write_ahead"}),
                     created_at, created_at))
        if denial:
            raise deny(*denial)
        return self._send(context, request, idempotency_key, external_reference, now)

    @staticmethod
    def _duplicate_denial(connection, context, intent):
        if connection.execute(
                "SELECT 1 FROM execution_signal_claims WHERE environment_id = ? AND signal_id = ?",
                (context.environment_id, intent.signal_id)).fetchone():
            return ("Ten sygnał został już wykorzystany w tym środowisku.", "duplicate_signal",
                    "Nie wykonuj sygnału ponownie; utwórz nowy sygnał z nową przyczyną.")
        if connection.execute(
                "SELECT 1 FROM execution_signal_claims WHERE environment_id = ? AND intent_id = ?",
                (context.environment_id, intent.intent_id)).fetchone():
            return DUPLICATE_INTENT
        return None

    def _send(self, context, request, idempotency_key, external_reference, now):
        """Jedno order_send na intencję. Wszystko poza potwierdzonym wykonaniem zostaje uncertain."""
        def not_sent(stage, exc):
            # Przed wysłaniem nic nie poszło do brokera: wynik pewny (rejected), potem odmowa.
            self._finish(context, idempotency_key, external_reference, ExecutionResultState.REJECTED,
                         {"stage": stage, "error": getattr(exc, "blocker", type(exc).__name__)}, now,
                         "Zlecenia nie wysłano.")
            raise exc

        try:
            self.ensure_demo(context, "przed order_check")
            check = self.sdk.order_check(request)
        except Exception as exc:  # noqa: BLE001
            not_sent("order_check", exc)
        if check is None or int(check.retcode) != 0:
            return self._finish(context, idempotency_key, external_reference, ExecutionResultState.REJECTED,
                                {"stage": "order_check", "retcode": None if check is None else int(check.retcode)},
                                now, "order_check odrzucił zlecenie; nie wysłano.")
        try:
            self.ensure_demo(context, "przed order_send")
        except Exception as exc:  # noqa: BLE001
            not_sent("przed order_send", exc)
        price = request["price"]
        try:
            result = self.sdk.order_send(request)
        except Exception as exc:  # noqa: BLE001 - błąd połączenia: wynik nieznany
            result, error = None, type(exc).__name__
        else:
            error = None
        try:
            self.ensure_demo(context, "po order_send")
        finally:
            if result is not None and int(result.retcode) == RETCODE_DONE:
                state, message = ExecutionResultState.ACCEPTED, "Zlecenie DEMO wykonane."
                response = {"stage": "order_send", "retcode": int(result.retcode), "order": int(result.order),
                            "deal": int(result.deal), "requested_price": float(price),
                            "fill_price": float(result.price), "volume": float(result.volume)}
            else:
                # Brak wyniku, błąd połączenia albo kod inny niż wykonanie: uzgodnienie po magic i tickecie.
                state, message = ExecutionResultState.UNCERTAIN, "Wynik order_send niepotwierdzony; wymaga uzgodnienia."
                response = {"stage": "order_send", "retcode": None if result is None else int(result.retcode),
                            "order": None if result is None else int(getattr(result, "order", 0) or 0) or None,
                            "error": error, "requested_price": float(price)}
            receipt = self._finish(context, idempotency_key, external_reference, state, response, now, message)
        return receipt

    def _filling(self, info) -> int:
        mode = int(getattr(info, "filling_mode", 0))
        if mode & 1:
            return self.sdk.ORDER_FILLING_FOK
        if mode & 2:
            return self.sdk.ORDER_FILLING_IOC
        return self.sdk.ORDER_FILLING_RETURN

    def _finish(self, context, idempotency_key, external_reference, state, response, now, message):
        stamp = _iso(now)
        with self.database.transaction() as connection:
            if state is not ExecutionResultState.UNCERTAIN:
                connection.execute(
                    "UPDATE execution_intents SET state = ?, response_json = ?, updated_at = ? WHERE idempotency_key = ?",
                    (state.value, canonical_json(response), stamp, idempotency_key))
            else:
                connection.execute(
                    "UPDATE execution_intents SET response_json = ?, updated_at = ? WHERE idempotency_key = ?",
                    (canonical_json(response), stamp, idempotency_key))
            self.guard.audit_event(
                event_type=f"executor.mt5_demo_{state.value}", outcome=state.value, actor=context.worker_id,
                reason=message, payload={"environment_id": context.environment_id, "external_reference": external_reference,
                                         **{k: v for k, v in response.items() if k in ("stage", "retcode")}},
                idempotency_key=f"executor-event:{idempotency_key}:{state.value}", connection=connection)
        return ExecutionReceipt(state, external_reference.removeprefix("MT5D-"), external_reference, message)

    # ---------- uzgodnienie ----------

    def response(self, idempotency_key: str) -> dict:
        import json
        with self.database.connect() as connection:
            row = connection.execute("SELECT response_json FROM execution_intents WHERE idempotency_key = ?",
                                     (idempotency_key,)).fetchone()
        return json.loads(row["response_json"]) if row else {}

    def reconcile(self, external_reference: str, *, idempotency_key: str, now: datetime,
                  since: datetime) -> ExecutionReceipt:
        """Rozstrzyga intencję w stanie uncertain po dealach z magic i komentarzem intencji. Nie wysyła zleceń."""
        if len(idempotency_key) < 8:
            raise ValidationError("Klucz uzgodnienia jest za krótki.")
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM execution_intents WHERE external_reference = ?",
                                     (external_reference,)).fetchone()
        if row is None:
            raise ValidationError("Nie znaleziono referencji.")
        comment = _comment(row["intent_id"])
        order_ticket = self.response(row["idempotency_key"]).get("order")
        self.require_demo(row["environment_id"], "reconciler", "przed odczytem historii")
        deals = self.sdk.history_deals_get(since, now)
        if deals is None:
            return ExecutionReceipt(ExecutionResultState.UNCERTAIN, row["intent_id"], external_reference,
                                    "Brak odczytu historii; stan pozostaje nierozstrzygnięty.")
        own = [d for d in deals if int(d.magic) == self.magic]
        if order_ticket:  # pierwszy klucz: ticket zlecenia z wyniku order_send i magic
            found = [d for d in own if int(getattr(d, "order", 0) or 0) == int(order_ticket)]
        else:  # bez wyniku order_send: komentarz intencji (pomocniczo; broker może go skrócić)
            found = [d for d in own if str(d.comment) == comment]
        if not found:
            # Ograniczenie: komentarz może zostać zmieniony przez brokera. Deal z magic adaptera, którego
            # nie da się przypisać do żadnej znanej intencji, zostawia wynik nierozstrzygnięty.
            known = self._known_orders()
            unassigned = [d for d in own if int(getattr(d, "order", 0) or 0) not in known]
            if unassigned:
                return ExecutionReceipt(ExecutionResultState.UNCERTAIN, row["intent_id"], external_reference,
                                        "W historii jest deal z magic wykonawcy bez przypisanej intencji; "
                                        "stan pozostaje nierozstrzygnięty (sprawdź ręcznie).")
        result = ExecutionResultState.ACCEPTED if found else ExecutionResultState.REJECTED
        stamp = _iso(now)
        with self.database.transaction() as connection:
            connection.execute("UPDATE execution_intents SET state = ?, updated_at = ? WHERE external_reference = ?",
                               (result.value, stamp, external_reference))
            connection.execute(
                "INSERT INTO execution_reconciliations(idempotency_key, external_reference, result_state, reconciled_at)"
                " VALUES (?, ?, ?, ?)", (idempotency_key, external_reference, result.value, stamp))
            self.guard.audit_event(
                event_type="executor.mt5_demo_reconciled", outcome=result.value, actor="reconciler",
                reason="Uzgodniono intencję z historią deali DEMO.",
                payload={"external_reference": external_reference, "deals_found": len(found)},
                idempotency_key=f"executor-event:{idempotency_key}", connection=connection)
        return ExecutionReceipt(result, row["intent_id"], external_reference,
                                "Znaleziono deal intencji." if found else "Brak deala intencji: zlecenie nie zostało wykonane.")

    def _known_orders(self) -> set[int]:
        import json
        with self.database.connect() as connection:
            rows = connection.execute("SELECT response_json FROM execution_intents").fetchall()
        known = set()
        for row in rows:
            order = json.loads(row["response_json"] or "{}").get("order")
            if order:
                known.add(int(order))
        return known

    def positions(self, environment_id: str) -> PositionSnapshot:
        self.require_demo(environment_id, "positions-reader", "przed odczytem pozycji")
        rows = self.sdk.positions_get() or []
        own: dict[str, Decimal] = {}
        for p in rows:
            if int(p.magic) == self.magic:
                sign = 1 if p.type == self.sdk.POSITION_TYPE_BUY else -1
                info = self.sdk.symbol_info(p.symbol)
                own[p.symbol] = own.get(p.symbol, Decimal("0")) + sign * _num(p.volume) * _num(info.trade_contract_size)
        return PositionSnapshot(environment_id, {k: str(v.normalize()) for k, v in own.items() if v != 0})


__all__ = ["MT5DemoAdapter", "DemoAccountRule", "OrderSDK", "ALLOWED_CALLS", "PROBE_MAGIC", "GROSS_LIMIT_KEY"]
