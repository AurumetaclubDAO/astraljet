import asyncio
from datetime import timedelta
from urllib.parse import quote
import httpx
from .config import PAPER_URL
from .models import Bar, Quote, now


class BrokerError(RuntimeError):
    pass


class UnknownOrder(BrokerError):
    pass


class Broker:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.http = httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, transport=transport,
            headers={'APCA-API-KEY-ID': settings.alpaca_api_key_id.get_secret_value(),
                     'APCA-API-SECRET-KEY': settings.alpaca_api_secret_key.get_secret_value()})

    async def close(self):
        await self.http.aclose()

    async def request(self, method, path, *, data=False, params=None, body=None, missing_ok=False):
        if not self.settings.paper_only or self.settings.alpaca_trading_base_url != PAPER_URL:
            raise BrokerError('PAPER guard')
        if not path.startswith('/') or '://' in path or '..' in path:
            raise BrokerError('Niepoprawna ścieżka')
        if data and method != 'GET':
            raise BrokerError('Dane: tylko odczyt')
        if method != 'GET' and not self.settings.execute_orders:
            raise BrokerError('DRY RUN: broker mutation zabronione')
        base = 'https://data.alpaca.markets' if data else PAPER_URL
        for attempt in range(3 if method == 'GET' else 1):
            try:
                r = await self.http.request(method, base+path, params=params, json=body)
            except httpx.TransportError as exc:
                if method != 'GET':
                    raise UnknownOrder('Nieznany wynik operacji brokera') from exc
                if attempt == 2:
                    raise BrokerError('Błąd sieci Alpaca') from exc
                await asyncio.sleep(0.5 * 2**attempt)
                continue
            if r.status_code == 404 and missing_ok:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                if method != 'GET':
                    raise UnknownOrder(f'Nieznany wynik HTTP {r.status_code}')
                if attempt < 2:
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
            if not 200 <= r.status_code < 300:
                raise BrokerError(f'Alpaca HTTP {r.status_code}; {method} {path}')
            if r.status_code == 204:
                return None
            try:
                return r.json()
            except ValueError as exc:
                if method != 'GET':
                    raise UnknownOrder('Niepoprawna odpowiedź zlecenia') from exc
                raise BrokerError('Niepoprawny JSON Alpaca') from exc
        raise BrokerError('Odczyt nieudany')

    async def account(self):
        return await self.request('GET', '/v2/account')

    async def positions(self):
        return await self.request('GET', '/v2/positions')

    async def orders(self):
        rows = await self.request('GET', '/v2/orders', params={'status':'open','limit':500})
        if not isinstance(rows, list) or len(rows) >= 500:
            raise BrokerError('Niekompletna lista orders')
        return rows

    async def asset(self, symbol, kind):
        route = '/v2/options/contracts/' if kind == 'option' else '/v2/assets/'
        return await self.request('GET', route+quote(symbol, safe=''))

    async def clock(self):
        return await self.request('GET', '/v2/clock')

    async def calendar(self, start, end):
        return await self.request('GET', '/v2/calendar', params={'start':str(start),'end':str(end)})

    async def by_client_id(self, cid):
        return await self.request('GET','/v2/orders:by_client_order_id',params={'client_order_id':cid},missing_ok=True)

    async def submit(self, payload):
        # Never blindly retry a POST, including after a timeout and 404 reconciliation.
        existing = await self.by_client_id(payload['client_order_id'])
        if existing is not None:
            return existing
        try:
            return await self.request('POST','/v2/orders',body=payload)
        except UnknownOrder:
            existing = await self.by_client_id(payload['client_order_id'])
            if existing is not None:
                return existing
            raise

    async def quote(self, symbol, kind, feed=None):
        if kind == 'crypto':
            path = '/v1beta3/crypto/us/latest/quotes'
            params = {'symbols':symbol}
        elif kind == 'option':
            path = '/v1beta1/options/quotes/latest'
            params = {'symbols':symbol,'feed':self.settings.options_feed}
        else:
            path = '/v2/stocks/quotes/latest'
            params = {'symbols':symbol,'feed':feed or self.settings.stock_feed}
        result = await self.request('GET', path, data=True, params=params)
        value = Quote.model_validate(result['quotes'][symbol])
        age = (now()-value.t).total_seconds()
        if not -5 <= age <= self.settings.max_quote_age_seconds:
            raise BrokerError('Nieaktualne kwotowanie')
        return value

    async def bars(self, symbol, kind, minutes=5, feed=None):
        path = '/v1beta3/crypto/us/bars' if kind == 'crypto' else '/v2/stocks/bars'
        timeframe = f'{minutes}Min' if minutes < 60 else f'{minutes//60}Hour'
        params = {'symbols':symbol,'timeframe':timeframe,'limit':1000,'sort':'desc',
                  'start':(now()-timedelta(minutes=minutes*130+1440*4)).isoformat()}
        if kind != 'crypto':
            params['feed'] = feed or self.settings.stock_feed
            params['adjustment'] = 'raw'
        result = await self.request('GET',path,data=True,params=params)
        bars = sorted((Bar.model_validate(b) for b in result.get('bars',{}).get(symbol,[])),key=lambda b:b.t)
        bars = [b for b in bars if b.t+timedelta(minutes=minutes) <= now()]
        if len(bars)<35 or (now()-bars[-1].t).total_seconds()>minutes*60+120:
            raise BrokerError(f'Brak aktualnych zamkniętych świec {minutes}m')
        if len({b.t for b in bars}) != len(bars):
            raise BrokerError('Duplikaty świec')
        if kind=='crypto' and any((b.t-a.t).total_seconds()!=minutes*60 for a,b in zip(bars[-35:-1],bars[-34:])):
            raise BrokerError('Luki w ostatnich świecach crypto')
        return bars[-130:]
