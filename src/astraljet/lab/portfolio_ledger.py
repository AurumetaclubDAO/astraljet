"""Pure spot portfolio ledger; no broker, persistence, leverage or cash injection."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_DOWN, localcontext

from astraljet.domain.errors import ValidationError


D = Decimal
QUANTITY_QUANTUM = D('1e-24')  # numerical precision, NOT a broker lot-size rule
MATH = Context(prec=80)


def finite(value: Decimal, *, positive: bool = False) -> None:
    if (not isinstance(value, Decimal) or not value.is_finite()
            or value < 0 or (positive and value == 0)):
        raise ValidationError('Wymagana jest skończona, nieujemna liczba Decimal.')
    # Bound numerical input scale; no silent loss of arbitrary precision.
    if value and (abs(value.adjusted()) > 18 or value.as_tuple().exponent < -24):
        raise ValidationError('Liczba przekracza obsługiwaną precyzję modelu.')


@dataclass(frozen=True, slots=True)
class Weights:
    btc: Decimal
    eth: Decimal
    cash: Decimal

    def validate(self) -> None:
        with localcontext(MATH):
            for value in (self.btc, self.eth, self.cash):
                finite(value)
            if self.btc + self.eth + self.cash != 1:
                raise ValidationError('Wagi muszą sumować się dokładnie do 1.')


@dataclass(frozen=True, slots=True)
class Portfolio:
    cash: Decimal
    btc_units: Decimal = D(0)
    eth_units: Decimal = D(0)

    def equity(self, btc_price: Decimal, eth_price: Decimal) -> Decimal:
        with localcontext(MATH):
            return self.cash + self.btc_units * btc_price + self.eth_units * eth_price


@dataclass(frozen=True, slots=True)
class Fill:
    instrument: str
    side: str
    quantity: Decimal
    price: Decimal
    notional: Decimal
    cost: Decimal


@dataclass(frozen=True, slots=True)
class Rebalance:
    portfolio: Portfolio
    fills: tuple[Fill, ...]
    equity_before: Decimal
    equity_after: Decimal
    executed_notional: Decimal
    total_cost: Decimal


def rebalance_spot(
    portfolio: Portfolio, *, btc_price: Decimal, eth_price: Decimal,
    target: Weights, cost_bps: Decimal,
) -> Rebalance:
    """Post-cost targets, cost per executed risky leg, sells before buys.

    Solve E_after + fee * sum(abs(target_i * E_after - old_notional_i))
    = E_before. The function is strictly increasing for fee < 100%.
    Use a conservative lower bound then floor units to 24 decimal places;
    numerical residue remains real cash, never borrowed or silently forgiven.
    """
    target.validate()
    finite(btc_price, positive=True)
    finite(eth_price, positive=True)
    finite(cost_bps)
    if cost_bps >= 10000:
        raise ValidationError('Koszt musi być mniejszy niż 100% nominału.')
    for value in (portfolio.cash, portfolio.btc_units, portfolio.eth_units):
        # Cash from earlier fills can have more than 24 fractional digits.
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValidationError('Niedozwolona gotówka lub krótka pozycja w ledgerze.')
    with localcontext(MATH):
        before = portfolio.equity(btc_price, eth_price)
        if before <= 0 or before > D('1e18'):
            raise ValidationError('Wartość portfela musi być dodatnia i mieścić się w modelu.')
        rate = cost_bps / 10000
        values = (portfolio.btc_units * btc_price, portfolio.eth_units * eth_price)
        weights = (target.btc, target.eth)
        residue = QUANTITY_QUANTUM * (btc_price + eth_price) + before * D('1e-32')
        if all(abs(w * before - old) <= residue for w, old in zip(weights, values)):
            return Rebalance(portfolio, (), before, before, D(0), D(0))
        low, high = D(0), before
        for _ in range(160):
            middle = (low + high) / 2
            cost = rate * sum((abs(w * middle - old) for w, old in zip(weights, values)), D(0))
            if middle + cost <= before:
                low = middle
            else:
                high = middle
        # Reserve far below unit-reporting tolerance, but above arithmetic noise.
        post_cost_target = max(D(0), low - before * D('1e-36'))
        units = tuple((w * post_cost_target / price).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
                      for w, price in zip(weights, (btc_price, eth_price)))
        fills: list[Fill] = []
        for symbol, previous, following, price in zip(
            ('BTCUSD', 'ETHUSD'), (portfolio.btc_units, portfolio.eth_units), units,
            (btc_price, eth_price),
        ):
            delta = following - previous
            if delta:
                notional = abs(delta) * price
                fills.append(Fill(symbol, 'buy' if delta > 0 else 'sell', abs(delta), price,
                                  notional, notional * rate))
        fills.sort(key=lambda fill: (fill.side != 'sell', fill.instrument))
        cash = portfolio.cash
        for fill in fills:
            cash += fill.notional if fill.side == 'sell' else -fill.notional
            cash -= fill.cost
            if cash < 0:
                raise ValidationError('Rebalans wymagałby ujemnej gotówki; model przerwany.')
        following = Portfolio(cash, *units)
        after = following.equity(btc_price, eth_price)
        total_cost = sum((fill.cost for fill in fills), D(0))
        if abs(before - total_cost - after) > max(D(1), before) * D('1e-40'):
            raise ValidationError('Naruszony bilans jednostek, gotówki i kosztów.')
        return Rebalance(following, tuple(fills), before, after,
                         sum((fill.notional for fill in fills), D(0)), total_cost)
