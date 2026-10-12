"""Experimental, offline BTC/ETH model with an explicit frozen-EXP CLI adapter.

Returns unqualified model output, never RUN, approval, mandate or broker orders.
The legacy backtest command and worker do not route here automatically.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from types import MappingProxyType
from typing import Any, Sequence

from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.validation import canonical_json, sha256_text
from astraljet.lab.data_quality import MarketBar
from astraljet.lab.portfolio_ledger import MATH, QUANTITY_QUANTUM, Portfolio, Weights, finite, rebalance_spot


D = Decimal
ENGINE_VERSION = 'astraljet-weekly-experimental-0.1'
TARGETS = MappingProxyType({
    'risk_off': Weights(D('.35'), D('.10'), D('.55')),
    'rebuild_1': Weights(D('.525'), D('.15'), D('.325')),
    'risk_on': Weights(D('.70'), D('.20'), D('.10')),
})
BENCHMARK = Weights(D('.80'), D('.20'), D(0))


@dataclass(frozen=True, slots=True)
class WeeklyProtocol:
    start: str
    in_sample_end: str
    out_of_sample_start: str
    end: str
    ma_window: int = 200
    slope_lookback: int = 20
    initial_equity: Decimal = D(100)

    def validate(self) -> tuple[date, date, date, date]:
        try:
            dates = tuple(date.fromisoformat(s) for s in (
                self.start, self.in_sample_end, self.out_of_sample_start, self.end,
            ))
        except (ValueError, TypeError) as exc:
            raise ValidationError('Protokół wymaga dat YYYY-MM-DD.') from exc
        start, is_end, oos_start, end = dates
        if (any(s != d.isoformat() for s, d in zip((self.start, self.in_sample_end, self.out_of_sample_start, self.end), dates))
                or not start <= is_end < oos_start <= end or oos_start != is_end + timedelta(days=1)
                or (end - start).days > 36525):
            raise ValidationError('Niepoprawny, nieciągły lub nakładający się zakres IS/OOS.')
        if (type(self.ma_window) is not int or not 2 <= self.ma_window <= 10000
                or type(self.slope_lookback) is not int or not 1 <= self.slope_lookback <= 10000):
            raise ValidationError('Niepoprawne okna SMA i nachylenia.')
        finite(self.initial_equity, positive=True)
        return dates


@dataclass(frozen=True, slots=True)
class CostScenario:
    name: str
    cost_bps: Decimal
    extra_delay_days: int = 0

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError('Scenariusz wymaga nazwy.')
        finite(self.cost_bps)
        if self.cost_bps >= 10000 or type(self.extra_delay_days) is not int or self.extra_delay_days not in (0, 1):
            raise ValidationError('Nieobsługiwany koszt lub opóźnienie scenariusza.')


def _source_hash() -> str:
    package = Path(__file__).resolve().parents[1]
    files = ('lab/weekly_portfolio.py', 'lab/portfolio_ledger.py', 'lab/data_quality.py',
             'domain/validation.py', 'domain/errors.py')
    return sha256_text(canonical_json({name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                                     for name in files}))


def weekly_engine_fingerprint() -> str:
    if _source_hash() != _LOADED_CODE_HASH:
        raise DomainBlockedError('Pliki silnika zmieniły się po załadowaniu. Uruchom nowy proces.', blocker='loaded_code_changed')
    return _LOADED_CODE_HASH


def next_weekly_state(previous: str | None, positive: bool) -> str:
    if previous not in (None, 'risk_off', 'rebuild_1', 'risk_on') or type(positive) is not bool:
        raise ValidationError('Niepoprawny stan lub warunek tygodniowy.')
    if not positive:
        return 'risk_off'
    return 'risk_on' if previous in ('rebuild_1', 'risk_on') else 'rebuild_1'


def _daily_bars(bars: Sequence[MarketBar], start: date, end: date) -> tuple[list[date], list[dict[str, MarketBar]]]:
    grouped: dict[date, dict[str, MarketBar]] = {}
    for bar in bars:
        if bar.instrument not in ('BTCUSD', 'ETHUSD'):
            raise ValidationError('Model obsługuje wyłącznie jawne BTCUSD i ETHUSD.')
        try:
            stamp = datetime.fromisoformat(bar.timestamp.replace('Z', '+00:00'))
            if stamp.utcoffset() != timedelta(0) or stamp.time().isoformat() != '00:00:00':
                raise ValueError('UTC daily start required')
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError('Wymagane dzienne świece 00:00 UTC.') from exc
        day = stamp.date()
        if not start <= day <= end:
            raise ValidationError('Przekaż dokładnie zakres protokołu, łącznie z warm-up.')
        for value in (bar.open, bar.high, bar.low, bar.close):
            finite(value, positive=True)
        if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
            raise ValidationError('Niespójne OHLC.')
        daily = grouped.setdefault(day, {})
        if bar.instrument in daily:
            raise ValidationError('Zduplikowana świeca; nie nadpisujemy obserwacji.')
        daily[bar.instrument] = bar
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if set(grouped) != set(dates) or any(set(grouped[d]) != {'BTCUSD', 'ETHUSD'} for d in dates):
        raise DomainBlockedError('Brak dziennej świecy lub instrumentu.', blocker='daily_calendar_gap')
    return dates, [grouped[d] for d in dates]


def _metrics(rows: list[dict], first: int, last: int, initial: Decimal) -> dict:
    if first > last:
        return {'status': 'not_observed', 'days': 0, 'net_return': None, 'max_drawdown': None,
                'annualized_return': None}
    selected = rows[first:last + 1]
    # Prior CLOSE, not current OPEN: OOS includes its first overnight move.
    baseline = D(rows[first - 1]['equity_close']) if first else initial
    final = D(selected[-1]['equity_close'])
    peak, drawdown = baseline, D(0)
    for row in selected:
        value = D(row['equity_close'])
        peak = max(peak, value)
        drawdown = max(drawdown, (peak - value) / peak)
    return {
        'status': 'measured_model_only', 'days': len(selected),
        'start': selected[0]['date'], 'end': selected[-1]['date'],
        'initial_equity': str(baseline), 'final_equity': str(final),
        'net_return': str(final / baseline - 1),
        'annualized_return': str((final / baseline) ** (D('365.25') / len(selected)) - 1),
        'max_drawdown': str(drawdown), 'drawdown_basis': 'daily_close_and_segment_baseline',
        'total_cost': str(sum((D(r['cost']) for r in selected), D(0))),
        'executed_notional': str(sum((D(r['executed_notional']) for r in selected), D(0))),
        'number_of_rebalances': sum(r['rebalance_executed'] for r in selected),
        'mean_gross_exposure_at_close': str(sum((D(r['gross_exposure']) for r in selected), D(0)) / len(selected)),
        'profit_factor': None, 'profit_factor_reason': 'portfolio_rebalance_not_closed_trade_accounting',
    }


def simulate_weekly(
    bars: Sequence[MarketBar], *, protocol: WeeklyProtocol, scenario: CostScenario,
    expected_code_hash: str,
) -> dict[str, Any]:
    """Deterministic proposal mechanics; no read of DATA files and no record writes."""
    code_hash = weekly_engine_fingerprint()
    if expected_code_hash != code_hash:
        raise DomainBlockedError('Hash kodu nie odpowiada przypiętej implementacji.', blocker='engine_hash_mismatch')
    start, is_end, oos_start, end = protocol.validate()
    scenario.validate()
    dates, daily = _daily_bars(bars, start, end)
    minimum_index = protocol.ma_window - 1 + protocol.slope_lookback
    first_signal = next((i for i, day in enumerate(dates) if i >= minimum_index and day.weekday() == 6), None)
    delay = 1 + scenario.extra_delay_days
    if first_signal is None or first_signal + delay >= len(dates):
        raise DomainBlockedError('Za mało danych na tygodniowy sygnał i wykonanie.', blocker='insufficient_history')
    first_execution = first_signal + delay
    with localcontext(MATH):
        portfolios = {name: Portfolio(protocol.initial_equity) for name in ('strategy', 'benchmark')}
        rows: dict[str, list[dict]] = {'strategy': [], 'benchmark': []}
        orders: list[dict] = []
        signals: list[dict] = []
        unfilled: list[dict] = []
        pending: dict[int, dict] = {}
        state: str | None = None
        held_state = 'cash'
        closes: list[Decimal] = []
        benchmark_dates = {first_execution}
        # Fixed calendar instruction needs no market signal. Apply the same
        # additional execution delay, without moving the initial allocation.
        for i, day in enumerate(dates):
            if day.day == 1 and i > first_execution:
                effective = i + scenario.extra_delay_days
                if effective < len(dates):
                    benchmark_dates.add(effective)
                else:
                    unfilled.append({'portfolio': 'benchmark', 'scheduled_date': day.isoformat(), 'reason': 'no_next_bar_for_execution'})
        for i, day in enumerate(dates):
            prices = (daily[i]['BTCUSD'].open, daily[i]['ETHUSD'].open)
            closing = (daily[i]['BTCUSD'].close, daily[i]['ETHUSD'].close)
            target_signal = pending.pop(i, None)
            for name in ('strategy', 'benchmark'):
                portfolio = portfolios[name]
                opening_equity = portfolio.equity(*prices)
                target = TARGETS[target_signal['state']] if name == 'strategy' and target_signal else None
                if name == 'benchmark' and i in benchmark_dates:
                    target = BENCHMARK
                cost, turnover, executed = D(0), D(0), False
                if target is not None:
                    rebalance = rebalance_spot(portfolio, btc_price=prices[0], eth_price=prices[1],
                                               target=target, cost_bps=scenario.cost_bps)
                    portfolio = rebalance.portfolio
                    portfolios[name] = portfolio
                    cost, turnover, executed = rebalance.total_cost, rebalance.executed_notional, bool(rebalance.fills)
                    if name == 'strategy':
                        held_state = target_signal['state']
                    orders.append({
                        'portfolio': name, 'execution_date': day.isoformat(),
                        'signal_bar_date': target_signal['bar_date'] if name == 'strategy' else None,
                        'reason': target_signal['state'] if name == 'strategy' else 'calendar_80_20',
                        'target': asdict(target), 'equity_before': str(rebalance.equity_before),
                        'equity_after': str(rebalance.equity_after), 'cost': str(cost),
                        'executed_notional': str(turnover), 'fills': [asdict(fill) for fill in rebalance.fills],
                    })
                value = portfolio.equity(*closing)
                if not value.is_finite() or value <= 0:
                    raise ValidationError('Niepoprawna wartość portfela; model przerwany.')
                rows[name].append({
                    'date': day.isoformat(), 'equity_open_before_orders': str(opening_equity),
                    'equity_close': str(value), 'cash': str(portfolio.cash),
                    'btc_units': str(portfolio.btc_units), 'eth_units': str(portfolio.eth_units),
                    'gross_exposure': str((value - portfolio.cash) / value),
                    'cost': str(cost), 'executed_notional': str(turnover),
                    'rebalance_executed': executed, 'state': held_state if name == 'strategy' else ('80_20' if i >= first_execution else 'cash'),
                })
            closes.append(closing[0])
            if i >= minimum_index and day.weekday() == 6:
                sma = sum(closes[i - protocol.ma_window + 1:i + 1], D(0)) / protocol.ma_window
                earlier_end = i - protocol.slope_lookback
                earlier_sma = sum(closes[earlier_end - protocol.ma_window + 1:earlier_end + 1], D(0)) / protocol.ma_window
                positive = closes[i] > sma and sma > earlier_sma
                following = next_weekly_state(state, positive)
                signal = {'bar_date': day.isoformat(), 'positive': positive, 'state': following,
                          'previous_state': state, 'sma': str(sma), 'earlier_sma': str(earlier_sma),
                          'close': str(closes[i]), 'changed': following != state}
                signals.append(signal)
                if following != state:
                    if i + delay < len(dates):
                        pending[i + delay] = signal
                    else:
                        unfilled.append({'portfolio': 'strategy', **signal, 'reason': 'no_next_bar_for_execution'})
                state = following
        split = (oos_start - start).days
        metrics = {name: {
            'in_sample': _metrics(history, first_execution, split - 1, protocol.initial_equity),
            'out_of_sample': _metrics(history, max(split, first_execution), len(dates) - 1, protocol.initial_equity),
            'full': _metrics(history, first_execution, len(dates) - 1, protocol.initial_equity),
        } for name, history in rows.items()}
        # Canonicalize Decimal fields once: output is plain, serializable JSON.
        output = json.loads(canonical_json({'signals': signals, 'orders': orders, 'unfilled': unfilled,
                                           'daily': rows, 'metrics': metrics}))
        input_hash = sha256_text(canonical_json({
            'bars': [asdict(day[symbol]) for day in daily for symbol in ('BTCUSD', 'ETHUSD')],
            'protocol': asdict(protocol), 'scenario': asdict(scenario), 'code_hash': code_hash,
        }))
        if weekly_engine_fingerprint() != code_hash:
            raise DomainBlockedError('Kod zmienił się podczas obliczeń.', blocker='engine_hash_mismatch')
        return {
            'engine_version': ENGINE_VERSION, 'engine_hash': code_hash, 'input_hash': input_hash,
            'output_hash': sha256_text(canonical_json(output)), 'python_version': platform.python_version(),
            'status': 'OFFLINE_UNQUALIFIED', 'execution_authorized': False, 'run_record_created': False,
            'protocol': json.loads(canonical_json(asdict(protocol))),
            'scenario': json.loads(canonical_json(asdict(scenario))),
            'quantity_quantum': str(QUANTITY_QUANTUM), 'decimal_precision': MATH.prec,
            'limitations': ['Brak potwierdzenia przewagi, mandatu i statusu nietkniętego OOS.',
                'Next-open to uproszczenie dostępności danych i realizacji; opóźnienie jest scenariuszem.',
                'Stały koszt USD-equivalent i precyzja jednostek nie odtwarzają pełnej specyfikacji brokera.',
                'Model offline; tylko jawny adapter weekly-offline. Legacy backtest i worker pozostają oddzielne.'],
            **output,
        }


_LOADED_CODE_HASH = _source_hash()
