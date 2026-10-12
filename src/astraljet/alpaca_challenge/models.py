import re
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator


def now():
    return datetime.now(timezone.utc)


def occ(symbol):
    match = re.fullmatch(r'([A-Z]{1,6})(\d{6})([CP])(\d{8})', symbol)
    if not match:
        raise ValueError('Niepoprawny OCC option symbol')
    expiry = datetime.strptime(match[2], '%y%m%d').date()
    return {'underlying': match[1], 'expiry': expiry, 'type': match[3], 'strike': int(match[4])/1000}


class Signal(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    timestamp: AwareDatetime
    strategy_id: Literal['ORB_RETEST', 'MOMENTUM', 'CRYPTO_BREAKOUT']
    symbol: str = Field(pattern=r'^[A-Z0-9/]{1,24}$')
    asset_type: Literal['equity', 'crypto', 'option']
    direction: Literal['LONG', 'SHORT'] = 'LONG'
    setup_grade: Literal['A+', 'A', 'B', 'C', 'NO TRADE']
    entry_type: Literal['limit', 'market'] = 'limit'
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    max_loss_usd: float = Field(gt=0)
    qty: float | None = Field(default=None, gt=0)
    confidence_components: dict[str, float] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=2000)
    position_intent: Literal['buy_to_open', 'sell_to_close'] = 'buy_to_open'
    time_in_force: Literal['day', 'gtc', 'ioc'] = 'day'
    extended_hours: bool = False

    @model_validator(mode='after')
    def validate_structure(self):
        if self.asset_type == 'crypto' and (self.direction != 'LONG' or '/' not in self.symbol):
            raise ValueError('Crypto wyłącznie LONG i symbol BASE/QUOTE')
        if self.asset_type == 'option':
            occ(self.symbol)
            if self.direction != 'LONG' or (self.qty is not None and not self.qty.is_integer()):
                raise ValueError('Opcje: tylko całkowita liczba long premium')
        if self.direction == 'LONG' and not self.stop_loss < self.entry_price < self.take_profit:
            raise ValueError('LONG: SL < entry < TP')
        if self.direction == 'SHORT' and not self.take_profit < self.entry_price < self.stop_loss:
            raise ValueError('SHORT: TP < entry < SL')
        return self


class Bar(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    t: AwareDatetime
    o: float = Field(gt=0)
    h: float = Field(gt=0)
    l: float = Field(gt=0)
    c: float = Field(gt=0)
    v: float = Field(ge=0)
    vw: float | None = None

    @model_validator(mode='after')
    def ohlc(self):
        if self.l>min(self.o,self.c) or self.h<max(self.o,self.c) or self.h<self.l:
            raise ValueError('Niepoprawne OHLC')
        return self


class Quote(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    t: AwareDatetime
    bp: float = Field(gt=0)
    ap: float = Field(gt=0)

    @model_validator(mode='after')
    def spread(self):
        if self.ap < self.bp:
            raise ValueError('Crossed quote')
        return self

    @property
    def spread_bps(self):
        return (self.ap-self.bp)/((self.ap+self.bp)/2)*10000
