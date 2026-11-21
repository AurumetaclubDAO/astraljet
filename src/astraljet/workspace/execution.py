"""Serwis żądań: dziennik, idempotencja, niepewność i uzgodnienie z brokerem.

Zasady (konstytucja VI):
- żądanie jest zapisywane trwale PRZED przekazaniem do adaptera,
- ten sam `request_id` nigdy nie jest wysyłany drugi raz,
- timeout daje UNCERTAIN; ponowienie wymaga NOWEGO żądania i jest dozwolone dopiero,
  gdy uzgodnienie wykaże brak poprzedniego (NOT_FOUND) albo odrzucenie,
- adapter inny niż SIMULATED jest w tej wersji blokowany (brak aktywacji DEMO/LIVE),
- lokalny kill switch blokuje nowe otwarcia, ale nie zamknięcia i ochronę.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol

from .market import DataMode, utc
from .model import AccountSnapshot, Deal, OrderRequest, Position, RequestKind, RequestState
from .simulator import AdapterTimeout, AdapterUnavailable, BrokerOrderStatus


class ExecutionBlocked(Exception):
    pass


class BrokerAdapter(Protocol):
    mode: DataMode

    def send(self, request: OrderRequest) -> BrokerOrderStatus: ...

    def lookup(self, request_id: str) -> BrokerOrderStatus | None: ...

    def positions(self) -> list[Position]: ...

    def history(self) -> list[Deal]: ...

    def account(self) -> AccountSnapshot: ...


def guard_adapter_mode(adapter: BrokerAdapter) -> None:
    """Jedyna dozwolona ścieżka w tej wersji: SIMULATED. DEMO/LIVE wymagają osobnego
    adaptera, odrębnej konfiguracji rachunku i datowanej aktywacji właściciela."""
    mode = getattr(adapter, "mode", None)
    if mode is not DataMode.SIMULATED:
        raise ExecutionBlocked(
            f"Adapter w trybie {mode}: obsługa DEMO/LIVE nie jest aktywna w Workspace v0.1. "
            "Wymaga osobnego adaptera, konfiguracji rachunku i aktywacji właściciela."
        )


@dataclass(slots=True)
class RequestRecord:
    request: OrderRequest
    state: RequestState
    sent_at: str | None = None
    updated_at: str = ""
    message: str = ""
    broker: dict | None = None
    transmissions: int = 0
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "state": self.state.value,
            "sent_at": self.sent_at,
            "updated_at": self.updated_at,
            "message": self.message,
            "broker": self.broker,
            "transmissions": self.transmissions,
            "history": list(self.history),
            "retry_allowed": self.state in RETRY_ALLOWED,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RequestRecord":
        return cls(
            request=OrderRequest.from_dict(data["request"]),
            state=RequestState(data["state"]),
            sent_at=data.get("sent_at"),
            updated_at=data.get("updated_at", ""),
            message=data.get("message", ""),
            broker=data.get("broker"),
            transmissions=data.get("transmissions", 0),
            history=list(data.get("history", [])),
        )


RETRY_ALLOWED = {RequestState.REJECTED, RequestState.NOT_FOUND, RequestState.NOT_SENT}


class OrderService:
    def __init__(
        self,
        adapter: BrokerAdapter,
        now: Callable[[], datetime],
        journal_path: Path | None = None,
        absent_grace_s: float = 0.0,
    ) -> None:
        guard_adapter_mode(adapter)
        self.adapter = adapter
        self.now = now
        self.journal_path = journal_path
        self.absent_grace_s = absent_grace_s
        self.records: dict[str, RequestRecord] = {}
        self.kill_switch = False
        self.kill_reason = ""
        if journal_path is not None and journal_path.exists():
            self._load()

    # --- dziennik ---------------------------------------------------------
    def _load(self) -> None:
        data = json.loads(self.journal_path.read_text(encoding="utf-8"))
        self.kill_switch = bool(data.get("kill_switch", False))
        self.kill_reason = data.get("kill_reason", "")
        for item in data.get("records", []):
            record = RequestRecord.from_dict(item)
            self.records[record.request.request_id] = record

    def _persist(self) -> None:
        if self.journal_path is None:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kill_switch": self.kill_switch,
            "kill_reason": self.kill_reason,
            "records": [r.to_dict() for r in self.records.values()],
        }
        tmp = self.journal_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.journal_path)

    def _set(self, record: RequestRecord, state: RequestState, message: str, broker: BrokerOrderStatus | None = None) -> None:
        stamp = utc(self.now()).isoformat()
        record.state = state
        record.message = message
        record.updated_at = stamp
        if broker is not None:
            record.broker = broker.to_dict()
        record.history.append({"at": stamp, "state": state.value, "message": message})

    # --- operacje ---------------------------------------------------------
    def set_kill_switch(self, active: bool, reason: str) -> None:
        self.kill_switch = active
        self.kill_reason = reason
        self._persist()

    def submit(self, request: OrderRequest) -> RequestRecord:
        existing = self.records.get(request.request_id)
        if existing is not None:
            return existing  # deduplikacja: nigdy drugi send tego samego request_id
        record = RequestRecord(request=request, state=RequestState.SENT)
        self.records[request.request_id] = record
        if self.kill_switch and request.kind is RequestKind.OPEN:
            self._set(record, RequestState.NOT_SENT, f"Kill switch Workspace aktywny: {self.kill_reason}")
            self._persist()
            return record
        self._set(record, RequestState.SENT, "Zapisano przed przekazaniem do adaptera.")
        record.sent_at = record.updated_at
        record.transmissions += 1
        self._persist()
        try:
            status = self.adapter.send(request)
        except AdapterUnavailable as exc:
            self._set(record, RequestState.NOT_SENT, str(exc))
        except AdapterTimeout as exc:
            self._set(record, RequestState.UNCERTAIN,
                      f"{exc} Wynik nieznany: nie ponawiać; wymagane uzgodnienie stanu.")
        else:
            self._apply_status(record, status)
        self._persist()
        return record

    def _apply_status(self, record: RequestRecord, status: BrokerOrderStatus) -> None:
        self._set(record, status.state, status.message, status)

    def reconcile(self, request_id: str) -> RequestRecord:
        record = self.records[request_id]
        if record.state.terminal:
            return record
        try:
            status = self.adapter.lookup(request_id)
        except AdapterUnavailable as exc:
            record.history.append({"at": utc(self.now()).isoformat(), "state": record.state.value,
                                   "message": f"Uzgodnienie nieudane: {exc}"})
            self._persist()
            return record
        if status is not None:
            self._apply_status(record, status)
        elif record.state in (RequestState.UNCERTAIN, RequestState.SENT):
            sent = datetime.fromisoformat(record.sent_at) if record.sent_at else self.now()
            if utc(self.now()) - utc(sent) >= timedelta(seconds=self.absent_grace_s):
                self._set(record, RequestState.NOT_FOUND,
                          "Uzgodnienie: broker nie zna tego żądania. Wolno utworzyć NOWE żądanie świadomie.")
        self._persist()
        return record

    def reconcile_all(self) -> list[RequestRecord]:
        return [self.reconcile(rid) for rid, r in list(self.records.items()) if not r.state.terminal]

    def open_issues(self) -> list[RequestRecord]:
        return [r for r in self.records.values() if r.state in (RequestState.UNCERTAIN, RequestState.SENT)]

    def retry_allowed(self, request_id: str) -> bool:
        return self.records[request_id].state in RETRY_ALLOWED
