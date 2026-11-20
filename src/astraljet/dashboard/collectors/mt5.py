"""Jedyny adapter SDK; jawna lista odczytów i gate przed każdym odczytem."""
import json
import math
import os
import subprocess
import sys
from datetime import timedelta
from zoneinfo import ZoneInfo
from ..config import MAGIC, load_config
from ..models import datum, missing, utcnow
from ..security import redact


class GateError(ValueError):
    pass


def gate(sdk, config):
    if config.demo_login is None:
        raise GateError('ZABLOKOWANE: brak lokalnej konfiguracji rachunku DEMO')
    account = sdk.account_info()
    if account is None:
        raise GateError('Brak odczytu konta')
    if account.login in config.forbidden_logins:
        raise GateError('LIVE — zablokowane')
    if account.login != config.demo_login or account.trade_mode != sdk.ACCOUNT_TRADE_MODE_DEMO or account.server != config.server:
        raise GateError('ZABLOKOWANE: konto nie-demo lub niezgodny serwer')
    return account


def fnum(obj, key):
    value = float(getattr(obj, key))
    if not math.isfinite(value):
        raise ValueError('Nieprawidłowa liczba')
    return value


def failure(message):
    return {k: missing('MT5 DEMO', message) for k in ('account', 'terminal', 'positions', 'history')}


def equity_curve(sdk, account, now, ttl, max_points=400):
    """Krzywa salda z pełnej historii deali (w tym wpłaty) + bieżące equity; DD% od szczytu. Tylko odczyt."""
    from datetime import datetime, timezone
    # Czas deali MT5 jest w strefie serwera; zapas +1 dzień, aby nie gubić ostatnich deali.
    deals = sdk.history_deals_get(datetime(2015, 1, 1, tzinfo=timezone.utc), now + timedelta(days=1))
    if deals is None or len(deals) > 100000:
        return missing('MT5 / historia equity', 'Brak pełnej historii deali')
    seen, events = set(), []
    for d in deals:
        if d.ticket in seen:
            continue
        seen.add(d.ticket)
        amount = sum(fnum(d, k) for k in ('profit', 'commission', 'swap', 'fee'))
        if amount:
            events.append((int(d.time), amount, int(d.type) in (2, 3, 6), int(d.type) == 2 and str(d.comment).lower().startswith('reset balance')))
    events.sort()
    # Reset salda demo zaczyna nową erę rachunku: krzywa i szczyt liczone od ostatniego resetu.
    resets = [i for i, e in enumerate(events) if e[3]]
    begin = resets[-1] if resets else 0
    reset_at = events[begin][0] if resets else None
    balance, peak, max_dd, pts = sum(e[1] for e in events[:begin]), None, 0.0, []
    flows = 0
    for t, amount, cashflow, _reset in events[begin:]:
        balance += amount
        if _reset:
            peak = None
        if cashflow:
            flows += 1
            # Wpłata/wypłata przesuwa szczyt o tę samą kwotę: DD liczy tylko wynik handlu.
            peak = None if peak is None else peak + amount
        if balance <= 0:
            continue
        peak = balance if peak is None or peak <= 0 else max(peak, balance)
        dd = (balance - peak) / peak * 100
        max_dd = min(max_dd, dd)
        pts.append(dict(t=t, balance=round(balance, 2), equity=round(balance, 2), dd_pct=round(dd, 3)))
    equity = fnum(account, 'equity')
    if peak:
        peak = max(peak, equity)
        dd = (equity - peak) / peak * 100
        max_dd = min(max_dd, dd)
        pts.append(dict(t=int(now.timestamp()), balance=round(fnum(account, 'balance'), 2), equity=round(equity, 2), dd_pct=round(dd, 3), current=True))
    if not pts:
        return missing('MT5 / historia equity', 'Brak deali z saldem')
    if len(pts) > max_points:
        step = len(pts) / (max_points - 1)
        keep = sorted({int(i * step) for i in range(max_points - 1)} | {len(pts) - 1})
        worst = min(range(len(pts)), key=lambda i: pts[i]['dd_pct'])
        pts = [pts[i] for i in sorted(set(keep) | {worst})]
    diff = round(balance - fnum(account, 'balance'), 2)
    value = dict(points=pts, start=pts[0]['t'], peak=round(peak, 2), max_dd_pct=round(max_dd, 3),
                 current_dd_pct=pts[-1]['dd_pct'], deals=len(events) - begin, cash_flows=flows, reset_at=reset_at, balance_check_diff=diff)
    ok = abs(diff) < 0.05
    return datum(value, 'MT5 / historia equity', now, ttl, now=now, uncertain=not ok,
                 error=None if ok else 'Suma deali nie zgadza się z saldem konta')


def read_sdk(sdk, config, now=None):
    now = now or utcnow()
    try:
        if not sdk.initialize(config.terminal_path, timeout=5000):
            return failure('Brak połączenia z uruchomionym terminalem')
        account = gate(sdk, config)
        terminal = sdk.terminal_info()
        if terminal is None or not terminal.connected:
            return failure('Terminal bez połączenia')
        gate(sdk, config)
        positions = sdk.positions_get()
        if positions is None:
            return failure('Nie udało się odczytać pozycji')
        gate(sdk, config)
        start = (now.astimezone(ZoneInfo('Europe/Warsaw')) - timedelta(days=config.history_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        deals = sdk.history_deals_get(start, now)
        if deals is None:
            history = None
        elif len(deals) > 100000:
            history = None
        else:
            history = list(deals)
        # Spójność konta jest ponownie kontrolowana po całym odczycie.
        final_account = gate(sdk, config)
        final_terminal = sdk.terminal_info()
        if final_terminal is None or not final_terminal.connected:
            return failure('Terminal utracił połączenie podczas odczytu')
        ttl = config.freshness['mt5']
        account_data = {k: fnum(final_account, k) for k in ('balance', 'equity', 'margin', 'margin_free', 'profit')}
        account_data.update(login=config.demo_login, server=config.server, currency=str(final_account.currency), mode='DEMO')
        pos = []
        for p in positions:
            pos.append(dict(ticket=int(p.ticket), symbol=str(p.symbol), direction='Kupno' if p.type == 0 else 'Sprzedaż',
                            volume=fnum(p, 'volume'), entry=fnum(p, 'price_open'), sl=fnum(p, 'sl'), tp=fnum(p, 'tp'),
                            profit=fnum(p, 'profit'), swap=fnum(p, 'swap'), magic=int(p.magic), bot=MAGIC.get(p.magic, 'other')))
        history_ds = missing('MT5 / historia', 'Brak pełnego odczytu historii')
        if history is not None:
            ownership = {}
            for d in history:
                if d.magic in MAGIC and d.position_id:
                    ownership.setdefault(d.position_id, set()).add(MAGIC[d.magic])
            normalized = []
            tickets = set()
            for d in history:
                if d.ticket in tickets or d.type not in (0, 1):
                    continue
                tickets.add(d.ticket)
                owners = ownership.get(d.position_id, set())
                bot = MAGIC.get(d.magic)
                if bot is None and len(owners) == 1:
                    bot = next(iter(owners))
                normalized.append(dict(ticket=int(d.ticket), position_id=int(d.position_id), magic=int(d.magic),
                                       bot=bot or 'other', time=int(d.time), amount=sum(fnum(d, k) for k in ('profit', 'commission', 'swap', 'fee'))))
            history_ds = datum(dict(deals=normalized, start=start.isoformat(), end=now.isoformat(),
                                    unassigned=sum(d['bot'] == 'other' for d in normalized),
                                    coverage='Transakcje kupna/sprzedaży z zaksięgowanymi kosztami w podanym oknie; bez wpłat i wypłat'),
                               'MT5 / historia', now, ttl, now=now)
        try:
            curve_ds = equity_curve(sdk, final_account, now, ttl)
            gate(sdk, config)
        except GateError:
            raise
        except Exception:
            curve_ds = missing('MT5 / historia equity', 'Błąd odczytu historii equity')
        return dict(account=datum(account_data, 'MT5 / konto', now, ttl, now=now),
                    terminal=datum(dict(connected=True, algo_trading=bool(final_terminal.trade_allowed)), 'MT5 / terminal', now, ttl, now=now),
                    positions=datum(pos, 'MT5 / pozycje', now, ttl, now=now), history=history_ds, historical_equity=curve_ds)
    except GateError as exc:
        return failure(str(exc))
    except Exception:
        return failure('Błąd odczytu MT5; szczegóły źródła nie są ujawniane')
    finally:
        sdk.shutdown()


def worker(config):
    try:
        import psutil
        import MetaTrader5 as sdk
        if not select_terminal(config, psutil.process_iter(['name', 'exe'])):
            return failure('Brak jednoznacznego, uruchomionego terminala DEMO')
        return read_sdk(sdk, config)
    except Exception:
        return failure('Adapter MT5 niedostępny')


def select_terminal(config, processes):
    """True tylko gdy działa dokładnie jeden terminal pod ścieżką DEMO i nie jest to ścieżka zabroniona (LIVE).

    Inne terminale (np. LIVE w osobnej instalacji) mogą działać obok; panel się z nimi nie łączy.
    Pusta ścieżka oznacza brak terminala DEMO na tym komputerze.
    """
    if not config.terminal_path:
        return False
    norm = lambda p: os.path.normcase(os.path.realpath(p))
    expected = norm(config.terminal_path)
    if any(norm(p) == expected for p in config.forbidden_terminal_paths):
        return False
    matches = 0
    for process in processes:
        info = getattr(process, 'info', process)
        if (info.get('name') or '').lower() == 'terminal64.exe' and info.get('exe') and norm(info['exe']) == expected:
            matches += 1
    return matches == 1


def collect(config, run=subprocess.run):
    if not config.mt5_enabled:
        return failure('Odczyt MT5 wyłączony w konfiguracji panelu')
    try:
        args = [sys.executable, '-B', '-m', 'astraljet.dashboard.collectors.mt5']
        result = run(args, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode or len(result.stdout) > 16 * 1024 * 1024:
            return failure('Proces odczytu MT5 nie zwrócił danych')
        return json.loads(result.stdout.decode('utf-8'))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return failure('Timeout lub brak procesu odczytu MT5')


if __name__ == '__main__':
    print(json.dumps(redact(worker(load_config())), ensure_ascii=True, allow_nan=False))
