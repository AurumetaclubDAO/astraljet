from dataclasses import dataclass, field
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[3]
# Numery rachunków są tylko w lokalnym, pomijanym przez Git pliku (repozytorium jest publiczne).
ACCOUNTS_FILE = ROOT / '.runtime' / 'dashboard' / 'accounts.toml'
HOST = '127.0.0.1'
PORT = 8877
TASKS = ('TQ-HORMUZ-Demo', 'TQ-HORMUZ-Signal', 'TQ-TECHVOL-Demo', 'TQ-XASSET-Demo',
         'TQ-ALTSPEC-Demo', 'TQ-MRRSI2-Demo', 'TQ-TPB-Demo', 'SHADOW-VB-Daily', 'TQ-Arena-Refresh', 'TQ-FundingOI-Collector')
BOTS = (
    ('tq-hormuz', 'HORMUZ', 'TQ-HORMUZ', 'TQ-HORMUZ-Demo', (2026101301,)),
    ('tq-tech-vol', 'TECH VOL', 'TQ-TECH-VOL', 'TQ-TECHVOL-Demo', (2026101303,)),
    ('tq-xasset-lag', 'XASSET LAG', 'TQ-XASSET-LAG', 'TQ-XASSET-Demo', (2026101304,)),
    ('tq-alt-spec', 'ALT SPEC', 'TQ-ALT-SPEC', 'TQ-ALTSPEC-Demo', (2026101305,)),
    ('tq-long-hold', 'LONG HOLD', 'TQ-LONG-HOLD', None, (2026093002, 20261002)),
    ('tq-vb', 'v-B', 'TQ-VB', None, (2026101302,)),
    ('tq-mr-rsi2', 'MR-RSI2', 'TQ-MR-RSI2', 'TQ-MRRSI2-Demo', (2026101606,)),
    ('tq-tpb', 'TPB', 'TQ-TPB', 'TQ-TPB-Demo', (2026101607,)),
)
# Strict site schema (observatory ingest) accepts exactly these six bot cards until redeploy.
SITE_BOT_IDS = ('tq-hormuz', 'tq-tech-vol', 'tq-xasset-lag', 'tq-alt-spec', 'tq-long-hold', 'tq-vb')
MAGIC = {magic: b[0] for b in BOTS for magic in b[4]}


@dataclass(frozen=True)
class Config:
    desktop: Path = Path(r'C:\Users\karol\Desktop')
    terminal_path: str = r'C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe'
    server: str = 'VantageMarkets-Demo'
    refresh_seconds: int = 45
    history_days: int = 30
    mt5_enabled: bool = True
    # Brak numeru DEMO oznacza blokadę każdego odczytu MT5 (fail-closed).
    demo_login: int | None = None
    forbidden_logins: tuple = ()
    schedule_enabled: bool = True
    freshness: dict = field(default_factory=lambda: dict(mt5=90, schedule=90, runner=1200, arena=1200, funding=1800, shadow=108000, config=90))

    def __post_init__(self):
        if not 30 <= self.refresh_seconds <= 60 or not 1 <= self.history_days <= 90:
            raise ValueError('Niepoprawny interwał')
        if any(not isinstance(x, (float, int)) or x <= 0 for x in self.freshness.values()):
            raise ValueError('Niepoprawny próg wieku')
        if self.demo_login is not None and (type(self.demo_login) is not int or self.demo_login <= 0):
            raise ValueError('Niepoprawny numer rachunku DEMO')
        if any(type(x) is not int or x <= 0 for x in self.forbidden_logins):
            raise ValueError('Niepoprawny zabroniony numer rachunku')
        if self.demo_login is not None and self.demo_login in self.forbidden_logins:
            raise ValueError('Rachunek DEMO nie może być na liście zabronionych')


def load_config():
    p = ROOT / 'dashboard_config.toml'
    with p.open('rb') as stream:
        data = tomllib.load(stream)
    defaults = Config()
    data['desktop'] = Path(data.get('desktop', defaults.desktop))
    data['freshness'] = defaults.freshness | data.get('freshness', {})
    data.pop('demo_login', None)
    data.pop('forbidden_logins', None)
    data.update(load_accounts())
    return Config(**data)


def load_accounts(path=ACCOUNTS_FILE):
    """Czyta lokalny plik z numerami rachunków; brak pliku = brak dozwolonego rachunku."""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open('rb') as stream:
        raw = tomllib.load(stream)
    return {'demo_login': raw.get('demo_login'), 'forbidden_logins': tuple(raw.get('forbidden_logins', ()))}
