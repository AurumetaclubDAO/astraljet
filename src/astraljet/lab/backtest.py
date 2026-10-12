from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Sequence

from astraljet.domain.enums import EvidenceType, RunOutcome, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import (
    DataRecord,
    ExperimentRecord,
    RunRecord,
    StrategyRecord,
    record_content_hash,
)
from astraljet.domain.validation import new_record_id, utc_now

from .data_quality import MarketBar


@dataclass(frozen=True, slots=True)
class TrendTarget:
    signal_index: int
    effective_index: int
    regime: Literal["risk_on", "risk_reduced"]
    close: Decimal
    moving_average: Decimal


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def generate_trend_targets(
    closes: Sequence[Decimal],
    *,
    ma_window: int,
    slope_lookback: int,
) -> list[TrendTarget]:
    if ma_window < 2 or slope_lookback < 1:
        raise ValidationError("Okno SMA musi być >=2, a slope_lookback >=1.")
    targets: list[TrendTarget] = []
    active_regime: str | None = None
    first_index = ma_window - 1 + slope_lookback
    for index in range(first_index, len(closes)):
        current_ma = _mean(closes[index - ma_window + 1 : index + 1])
        earlier_end = index - slope_lookback
        earlier_ma = _mean(closes[earlier_end - ma_window + 1 : earlier_end + 1])
        regime = (
            "risk_on"
            if closes[index] > current_ma and current_ma > earlier_ma
            else "risk_reduced"
        )
        if active_regime is None and regime == "risk_reduced":
            continue
        if regime != active_regime:
            targets.append(
                TrendTarget(
                    signal_index=index,
                    effective_index=index + 1,
                    regime=regime,
                    close=closes[index],
                    moving_average=current_ma,
                )
            )
            active_regime = regime
    return targets


def apply_turnover_cost(
    *,
    equity: Decimal,
    one_way_turnover: Decimal,
    cost_bps: Decimal | None,
) -> tuple[Decimal, Decimal]:
    if cost_bps is None:
        raise DomainBlockedError(
            "Brak modelu kosztów; koszt nie może zostać przyjęty jako zero.",
            blocker="unknown_cost_model",
            owner="Karol",
            allowed_next_action="Zapisz model kosztów w STRAT i EXP.",
        )
    if equity < 0 or not Decimal("0") <= one_way_turnover <= Decimal("1") or cost_bps < 0:
        raise ValidationError("Niepoprawne dane kosztu lub obrotu.")
    cost = equity * one_way_turnover * cost_bps / Decimal("10000")
    return cost, equity - cost


def resolve_intrabar_exit(
    *,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    stop: Decimal,
    target: Decimal,
    policy: str | None,
) -> tuple[str, Decimal] | None:
    if not low <= open_price <= high or stop >= target:
        raise ValidationError("Niepoprawna świeca albo poziomy stop/target.")
    stop_hit = low <= stop
    target_hit = high >= target
    if stop_hit and target_hit:
        if policy is None:
            raise DomainBlockedError(
                "Stop i cel wystąpiły w tej samej świecy bez reguły kolejności.",
                blocker="ambiguous_intrabar_order",
                owner="Karol",
                allowed_next_action="Zamroź konserwatywną politykę realizacji w EXP.",
            )
        if policy == "stop_first":
            return "stop", stop
        if policy == "target_first":
            return "target", target
        raise ValidationError("Nieznana polityka kolejności świecy.")
    if stop_hit:
        return "stop", stop
    if target_hit:
        return "target", target
    return None


def calculate_profit_factor(
    closed_trade_results: Iterable[Decimal],
) -> tuple[Decimal | None, str | None]:
    results = list(closed_trade_results)
    if not results:
        return None, "no_closed_trades"
    gross_profit = sum((value for value in results if value > 0), Decimal("0"))
    gross_loss = -sum((value for value in results if value < 0), Decimal("0"))
    if gross_loss == 0:
        return None, "no_losses"
    return gross_profit / gross_loss, None


def _decimal_parameter(strategy: StrategyRecord, name: str) -> Decimal:
    if name not in strategy.allowed_parameters:
        raise DomainBlockedError(
            f"STRAT nie zawiera parametru {name}.",
            blocker=f"missing_parameter_{name}",
            owner=strategy.owner,
            allowed_next_action="Utwórz kompletną nową wersję STRAT.",
        )
    try:
        return Decimal(str(strategy.allowed_parameters[name]))
    except Exception as exc:
        raise ValidationError(f"Parametr {name} nie jest liczbą dziesiętną.") from exc


def _integer_parameter(strategy: StrategyRecord, name: str) -> int:
    value = _decimal_parameter(strategy, name)
    if value != value.to_integral_value():
        raise ValidationError(f"Parametr {name} musi być liczbą całkowitą.")
    return int(value)


def _weights_for_regime(strategy: StrategyRecord, regime: str) -> dict[str, Decimal]:
    if len(strategy.instruments) != 2:
        raise DomainBlockedError(
            "Silnik BTC/ETH wymaga dokładnie dwóch instrumentów.",
            blocker="unsupported_instrument_count",
        )
    prefix = "risk_on" if regime == "risk_on" else "risk_reduced"
    btc_weight = _decimal_parameter(strategy, f"{prefix}_btc_weight")
    eth_weight = _decimal_parameter(strategy, f"{prefix}_eth_weight")
    cash_weight = Decimal("1") - btc_weight - eth_weight
    weights = {
        strategy.instruments[0]: btc_weight,
        strategy.instruments[1]: eth_weight,
        "CASH": cash_weight,
    }
    if any(value < 0 or value > 1 for value in weights.values()):
        raise ValidationError("Wagi strategii muszą należeć do przedziału 0–1 i sumować się do 1.")
    return weights


def _maximum_drawdown(values: Sequence[Decimal]) -> Decimal:
    peak = values[0]
    maximum = Decimal("0")
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            maximum = max(maximum, (peak - value) / peak)
    return maximum


def _criteria_pass(metrics: dict[str, object], criteria: dict[str, object]) -> bool:
    results: list[bool] = []
    for name, expected in criteria.items():
        if name == "max_drawdown_lte":
            results.append(Decimal(str(metrics["max_drawdown"])) <= Decimal(str(expected)))
        elif name == "min_rebalances_gte":
            results.append(int(metrics["number_of_rebalances"]) >= int(expected))
        elif name == "net_return_gte":
            results.append(Decimal(str(metrics["net_return"])) >= Decimal(str(expected)))
        else:
            raise DomainBlockedError(
                f"Silnik nie obsługuje kryterium {name}.",
                blocker="unsupported_criterion",
            )
    return all(results)


def _as_decimal_text(value: Decimal) -> str:
    return format(value, "f")


def run_backtest(
    *,
    strategy: StrategyRecord,
    data: DataRecord,
    experiment: ExperimentRecord,
    bars: Sequence[MarketBar],
    owner: str,
    engine_version: str = "astraljet-backtest-0.1.0",
) -> RunRecord:
    if (experiment.strategy_id, experiment.strategy_version) != (
        strategy.record_id,
        strategy.version,
    ):
        raise DomainBlockedError("EXP wskazuje inną wersję STRAT.", blocker="strategy_version_mismatch")
    if (experiment.data_id, experiment.data_version) != (data.record_id, data.version):
        raise DomainBlockedError("EXP wskazuje inną wersję DATA.", blocker="data_version_mismatch")
    if experiment.cost_model != strategy.cost_model or data.cost_model != strategy.cost_model:
        raise DomainBlockedError("Modele kosztów nie są zgodne.", blocker="cost_mismatch")

    parameters = strategy.allowed_parameters
    ma_window = _integer_parameter(strategy, "ma_window")
    slope_lookback = _integer_parameter(strategy, "slope_lookback")
    cost_bps = _decimal_parameter(strategy, "cost_bps")
    initial_equity = _decimal_parameter(strategy, "initial_equity")
    if initial_equity <= 0:
        raise ValidationError("Kapitał początkowy musi być dodatni.")

    selected = [
        bar
        for bar in bars
        if experiment.in_sample[0] <= bar.timestamp <= experiment.out_of_sample[1]
    ]
    grouped: dict[str, dict[str, MarketBar]] = {}
    for bar in selected:
        grouped.setdefault(bar.timestamp, {})[bar.instrument] = bar
    timestamps = sorted(grouped)
    if not timestamps:
        raise DomainBlockedError("Brak danych w zakresie EXP.", blocker="empty_experiment_range")
    required = set(strategy.instruments)
    for timestamp in timestamps:
        if set(grouped[timestamp]) != required:
            raise DomainBlockedError(
                f"Niekompletny przekrój instrumentów w {timestamp}.",
                blocker="data_alignment_gap",
            )

    btc = strategy.instruments[0]
    closes = [grouped[timestamp][btc].close for timestamp in timestamps]
    targets = generate_trend_targets(
        closes,
        ma_window=ma_window,
        slope_lookback=slope_lookback,
    )
    target_by_index = {
        target.effective_index: target
        for target in targets
        if target.effective_index < len(timestamps)
    }
    rejected_signals = tuple(
        {
            "signal_timestamp": timestamps[target.signal_index],
            "regime": target.regime,
            "reason": "no_next_bar_for_execution",
        }
        for target in targets
        if target.effective_index >= len(timestamps)
    )

    started_at = utc_now()
    weights = {instrument: Decimal("0") for instrument in strategy.instruments}
    weights["CASH"] = Decimal("1")
    equity = initial_equity
    previous_closes: dict[str, Decimal] | None = None
    trades: list[dict[str, object]] = []
    exposure: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    total_cost = Decimal("0")

    for index, timestamp in enumerate(timestamps):
        daily = grouped[timestamp]
        if previous_closes is not None:
            overnight_factor = weights["CASH"] + sum(
                weights[instrument] * daily[instrument].open / previous_closes[instrument]
                for instrument in strategy.instruments
            )
            equity *= overnight_factor

        target = target_by_index.get(index)
        if target is not None:
            new_weights = _weights_for_regime(strategy, target.regime)
            turnover = sum(
                abs(new_weights[name] - weights[name]) for name in (*strategy.instruments, "CASH")
            ) / Decimal("2")
            cost, equity_after_cost = apply_turnover_cost(
                equity=equity,
                one_way_turnover=turnover,
                cost_bps=cost_bps,
            )
            trades.append(
                {
                    "execution_timestamp": timestamp,
                    "signal_timestamp": timestamps[target.signal_index],
                    "regime": target.regime,
                    "one_way_turnover": _as_decimal_text(turnover),
                    "cost": _as_decimal_text(cost),
                    "weights_before": {name: _as_decimal_text(value) for name, value in weights.items()},
                    "weights_after": {
                        name: _as_decimal_text(value) for name, value in new_weights.items()
                    },
                }
            )
            total_cost += cost
            equity = equity_after_cost
            weights = new_weights

        intraday_factor = weights["CASH"] + sum(
            weights[instrument] * daily[instrument].close / daily[instrument].open
            for instrument in strategy.instruments
        )
        equity *= intraday_factor
        previous_closes = {
            instrument: daily[instrument].close for instrument in strategy.instruments
        }
        exposure.append(
            {
                "timestamp": timestamp,
                "weights": {name: _as_decimal_text(value) for name, value in weights.items()},
            }
        )
        equity_curve.append({"timestamp": timestamp, "equity": _as_decimal_text(equity)})

    equity_values = [Decimal(str(point["equity"])) for point in equity_curve]
    maximum_drawdown = _maximum_drawdown(equity_values)
    net_return = equity / initial_equity - Decimal("1")
    profit_factor, profit_factor_reason = calculate_profit_factor([])
    metrics: dict[str, object] = {
        "initial_equity": _as_decimal_text(initial_equity),
        "final_equity": _as_decimal_text(equity),
        "net_return": _as_decimal_text(net_return),
        "max_drawdown": _as_decimal_text(maximum_drawdown),
        "total_cost": _as_decimal_text(total_cost),
        "number_of_rebalances": len(trades),
        "profit_factor": None if profit_factor is None else _as_decimal_text(profit_factor),
        "profit_factor_reason": profit_factor_reason,
        "win_rate": None,
        "win_rate_reason": "not_applicable_portfolio_rebalance",
    }
    outcome = RunOutcome.PASSED if _criteria_pass(metrics, experiment.criteria) else RunOutcome.FAILED_CRITERIA
    input_hash = record_content_hash(
        {
            "strategy_hash": strategy.content_hash,
            "data_hash": data.content_hash,
            "plan_hash": experiment.plan_hash,
            "engine_version": engine_version,
            "parameters": parameters,
        }
    )
    output_hash = record_content_hash(
        {
            "trades": trades,
            "rejected_signals": rejected_signals,
            "exposure": exposure,
            "equity_curve": equity_curve,
            "metrics": metrics,
            "outcome": outcome.value,
        }
    )
    completed_at = utc_now()
    reproduction = {
        "input_hash": input_hash,
        "output_hash": output_hash,
        "engine_version": engine_version,
        "data_provider": data.provider,
        "evidence_strength": (
            "test_only" if "fixture" in data.provider.lower() else "historical_unverified"
        ),
        "command": f"astraljet run backtest --experiment-id {experiment.record_id}",
    }
    content_hash = record_content_hash(
        {"input_hash": input_hash, "output_hash": output_hash, "outcome": outcome.value}
    )
    return RunRecord(
        record_id=new_record_id("RUN"),
        version=1,
        owner=owner,
        created_at=completed_at,
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=content_hash,
        limitations=(
            "BACKTEST nie jest prognozą ani gwarancją wyniku.",
            "Fixture syntetyczny sprawdza mechanikę, nie przewagę rynkową."
            if reproduction["evidence_strength"] == "test_only"
            else "Dane historyczne i model kosztów wymagają niezależnej weryfikacji.",
        ),
        experiment_id=experiment.record_id,
        experiment_version=experiment.version,
        evidence_type=EvidenceType.BACKTEST,
        started_at=started_at,
        completed_at=completed_at,
        engine_version=engine_version,
        trades=tuple(trades),
        rejected_signals=rejected_signals,
        total_cost=_as_decimal_text(total_cost),
        exposure=tuple(exposure),
        equity_curve=tuple(equity_curve),
        errors=(),
        metrics=metrics,
        reproduction=reproduction,
        run_outcome=outcome,
        input_hash=input_hash,
    )
