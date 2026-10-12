from pathlib import Path
import math
from typing import Literal
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
PAPER_URL = 'https://paper-api.alpaca.markets'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore', frozen=True, hide_input_in_errors=True)
    paper_only: bool = True
    alpaca_trading_base_url: str = PAPER_URL
    execute_orders: bool = False
    alpaca_api_key_id: SecretStr = SecretStr('')
    alpaca_api_secret_key: SecretStr = SecretStr('')
    executor_bearer_token: SecretStr = SecretStr('')
    challenge_db: Path = ROOT / '.runtime/alpaca/challenge.sqlite3'
    starting_equity: float = 1000
    challenge_days: int = 7
    max_risk_per_trade_usd: float = 150
    max_daily_loss_usd: float = 250
    max_total_drawdown_usd: float = 450
    max_open_positions: int = 3
    max_position_notional_usd: float = 700
    max_correlated_notional_usd: float = 700
    max_spread_bps: float = 35
    max_quote_age_seconds: int = 60
    max_signal_age_seconds: int = 90
    scanner_interval_seconds: int = 60
    monitor_interval_seconds: int = 5
    time_stop_minutes: int = 120
    orb_minutes: Literal[5, 15, 30] = 15
    allow_equity_short: bool = False
    allow_extended_hours: bool = False
    stock_feed: Literal['iex', 'sip'] = 'iex'
    options_feed: Literal['opra'] = 'opra'
    scanner_autostart: bool = True
    equities: str = 'NVDA,AMD,COIN,MSTR,PLTR,TSLA,SPY,QQQ,IWM'
    crypto: str = 'BTC/USD,ETH/USD,SOL/USD,AVAX/USD'

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # API keys and all deployment settings come from .env, never ambient env.
        return init_settings, dotenv_settings

    @model_validator(mode='after')
    def guard(self):
        if not self.paper_only or self.alpaca_trading_base_url != PAPER_URL:
            raise ValueError('PAPER ONLY: odmowa startu; wymagany dokładny endpoint Paper')
        if len(self.executor_bearer_token.get_secret_value()) < 32 or self.executor_bearer_token.get_secret_value().startswith('UZUPELNIJ'):
            raise ValueError('EXECUTOR_BEARER_TOKEN musi mieć co najmniej 32 znaki')
        for name in ('starting_equity', 'challenge_days', 'max_risk_per_trade_usd', 'max_daily_loss_usd',
                     'max_total_drawdown_usd', 'max_open_positions', 'max_position_notional_usd',
                     'max_correlated_notional_usd', 'scanner_interval_seconds', 'monitor_interval_seconds',
                     'max_spread_bps','max_quote_age_seconds','max_signal_age_seconds','time_stop_minutes'):
            if not math.isfinite(getattr(self,name)) or getattr(self, name) <= 0:
                raise ValueError(f'{name} musi być dodatnie')
        return self
