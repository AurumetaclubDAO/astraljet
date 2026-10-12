from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from astraljet.domain.enums import DataStatus, StrategyStatus, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import DataRecord, ExperimentRecord, StrategyRecord, record_content_hash
from astraljet.domain.validation import new_record_id, utc_now, validate_sha256, validate_utc


@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    code_hash: str
    hypothesis: str
    in_sample: tuple[str, str]
    out_of_sample: tuple[str, str]
    allowed_variants: tuple[dict[str, object], ...]
    criteria: dict[str, object]
    budget: str
    seed: int
    metrics: tuple[str, ...]
    tolerance: dict[str, str]
    stop_rules: tuple[str, ...]


def _validate_definition(definition: ExperimentDefinition) -> None:
    validate_sha256(definition.code_hash)
    if not definition.hypothesis.strip():
        raise ValidationError("EXP wymaga hipotezy zapisanej przed wynikiem.")
    if len(definition.in_sample) != 2 or len(definition.out_of_sample) != 2:
        raise ValidationError("EXP wymaga zakresów in-sample i out-of-sample.")
    for timestamp in (*definition.in_sample, *definition.out_of_sample):
        validate_utc(timestamp)
    if definition.in_sample[0] > definition.in_sample[1]:
        raise ValidationError("Zakres in-sample jest odwrócony.")
    if definition.out_of_sample[0] > definition.out_of_sample[1]:
        raise ValidationError("Zakres out-of-sample jest odwrócony.")
    if definition.in_sample[1] >= definition.out_of_sample[0]:
        raise ValidationError("Out-of-sample musi zaczynać się po in-sample.")
    if not definition.allowed_variants:
        raise ValidationError("EXP wymaga jawnej listy dozwolonych wariantów.")
    if not definition.criteria or not definition.metrics or not definition.stop_rules:
        raise ValidationError("EXP wymaga kryteriów, metryk i reguł przerwania.")
    if any(metric not in definition.tolerance for metric in definition.metrics):
        raise ValidationError("Każda metryka EXP wymaga tolerancji odtworzenia.")
    try:
        budget = Decimal(definition.budget)
    except InvalidOperation as exc:
        raise ValidationError("Budżet EXP musi być liczbą dziesiętną.") from exc
    if budget < 0:
        raise ValidationError("Budżet EXP nie może być ujemny.")


def freeze_experiment(
    *,
    strategy: StrategyRecord,
    data: DataRecord,
    definition: ExperimentDefinition,
    owner: str,
) -> ExperimentRecord:
    if strategy.strategy_status is not StrategyStatus.READY:
        raise DomainBlockedError(
            "STRAT nie jest kompletna.",
            blocker="strategy_not_ready",
            owner=strategy.owner,
            allowed_next_action="Uzupełnij STRAT i utwórz nową wersję.",
        )
    if data.data_status is not DataStatus.READY:
        raise DomainBlockedError(
            "DATA nie jest gotowa.",
            blocker="data_not_ready",
            owner=data.owner,
            allowed_next_action="Popraw DATA i utwórz nową wersję.",
        )
    if set(strategy.instruments) != set(data.instruments):
        raise DomainBlockedError("Instrumenty STRAT i DATA są różne.", blocker="instrument_mismatch")
    if strategy.venue != data.venue or strategy.timeframe != data.timeframe:
        raise DomainBlockedError("Venue lub timeframe STRAT i DATA są różne.", blocker="market_mismatch")
    if strategy.cost_model != data.cost_model:
        raise DomainBlockedError("Model kosztów STRAT i DATA jest różny.", blocker="cost_mismatch")

    _validate_definition(definition)
    if dict(strategy.allowed_parameters) not in [dict(item) for item in definition.allowed_variants]:
        raise DomainBlockedError(
            "Parametry STRAT nie są dozwolonym wariantem EXP.",
            blocker="variant_not_preregistered",
        )
    frozen_at = utc_now()
    plan_payload = {
        "strategy_id": strategy.record_id,
        "strategy_version": strategy.version,
        "strategy_hash": strategy.content_hash,
        "data_id": data.record_id,
        "data_version": data.version,
        "data_hash": data.content_hash,
        **asdict(definition),
        "cost_model": strategy.cost_model,
        "frozen_at": frozen_at,
    }
    plan_hash = record_content_hash(plan_payload)
    return ExperimentRecord(
        record_id=new_record_id("EXP"),
        version=1,
        owner=owner,
        created_at=frozen_at,
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=plan_hash,
        limitations=(
            "Zamrożenie EXP nie potwierdza przewagi strategii.",
            "Zmiana STRAT, DATA, kodu lub planu wymaga nowej wersji EXP.",
        ),
        strategy_id=strategy.record_id,
        strategy_version=strategy.version,
        data_id=data.record_id,
        data_version=data.version,
        code_hash=definition.code_hash,
        hypothesis=definition.hypothesis,
        in_sample=definition.in_sample,
        out_of_sample=definition.out_of_sample,
        allowed_variants=definition.allowed_variants,
        criteria=definition.criteria,
        budget=definition.budget,
        seed=definition.seed,
        metrics=definition.metrics,
        tolerance=definition.tolerance,
        stop_rules=definition.stop_rules,
        cost_model=strategy.cost_model,
        frozen_at=frozen_at,
        plan_hash=plan_hash,
    )
