from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astraljet.domain.enums import StrategyStatus, TechnicalStatus
from astraljet.domain.records import StrategyRecord, record_content_hash
from astraljet.domain.validation import new_record_id, utc_now


REQUIRED_FIELDS = (
    "instruments",
    "venue",
    "timeframe",
    "signal_timing",
    "execution_timing",
    "entry_rule",
    "exit_rule",
    "sizing_rule",
    "cost_model",
    "constraints",
    "missing_data_policy",
    "benchmark",
    "allowed_parameters",
)

AMBIGUOUS_PHRASES = (
    "pogorszenie struktury",
    "struktury trendu",
    "średnia rośnie",
    "2–3 transz",
    "2-3 transz",
    "według uznania",
    "uznaniowo",
    "w razie potrzeby",
    "itp.",
)


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    instruments: tuple[str, ...]
    venue: str
    timeframe: str
    signal_timing: str
    execution_timing: str
    entry_rule: str
    exit_rule: str
    sizing_rule: str
    cost_model: str
    constraints: tuple[str, ...]
    missing_data_policy: str
    benchmark: str
    allowed_parameters: dict[str, int | float | str]
    source_adaptation: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "StrategyDefinition":
        normalized = dict(values)
        normalized["instruments"] = tuple(normalized.get("instruments") or ())
        normalized["constraints"] = tuple(normalized.get("constraints") or ())
        normalized["allowed_parameters"] = dict(normalized.get("allowed_parameters") or {})
        normalized.setdefault("source_adaptation", "")
        return cls(**normalized)


def validate_definition(definition: StrategyDefinition) -> tuple[str, ...]:
    values = definition.as_dict()
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        value = values[field_name]
        if value is None or value == "" or value == () or value == {}:
            errors.append(f"missing_{field_name}")

    for field_name in ("entry_rule", "exit_rule", "sizing_rule"):
        value = str(values[field_name]).lower()
        if any(phrase in value for phrase in AMBIGUOUS_PHRASES):
            errors.append(f"ambiguous_{field_name}")

    normalized_cost = definition.cost_model.strip().lower()
    if normalized_cost in {"unknown", "nieznany", "brak", "0", "zero"}:
        errors.append("unknown_cost_model")
    return tuple(dict.fromkeys(errors))


def create_strategy(
    *,
    candidate_id: str,
    definition: StrategyDefinition,
    owner: str,
) -> StrategyRecord:
    errors = validate_definition(definition)
    ready = not errors
    now = utc_now()
    payload = {"candidate_id": candidate_id, **definition.as_dict()}
    limitations = (
        ("Źródłowa strategia nie jest potwierdzonym wynikiem ani rekomendacją.",)
        + ((definition.source_adaptation,) if definition.source_adaptation else ())
        + tuple(f"Brak/blokada: {error}" for error in errors)
    )
    return StrategyRecord(
        record_id=new_record_id("STRAT"),
        version=1,
        owner=owner,
        created_at=now,
        technical_status=TechnicalStatus.COMPLETED if ready else TechnicalStatus.BLOCKED,
        content_hash=record_content_hash(payload),
        limitations=limitations,
        candidate_id=candidate_id,
        instruments=definition.instruments,
        venue=definition.venue,
        timeframe=definition.timeframe,
        signal_timing=definition.signal_timing,
        execution_timing=definition.execution_timing,
        entry_rule=definition.entry_rule,
        exit_rule=definition.exit_rule,
        sizing_rule=definition.sizing_rule,
        cost_model=definition.cost_model,
        constraints=definition.constraints,
        missing_data_policy=definition.missing_data_policy,
        benchmark=definition.benchmark,
        allowed_parameters=definition.allowed_parameters,
        source_adaptation=definition.source_adaptation,
        strategy_status=StrategyStatus.READY if ready else StrategyStatus.NEEDS_INPUT,
    )
