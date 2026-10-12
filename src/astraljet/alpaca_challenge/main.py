import secrets
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import Settings
from .models import Signal
from .service import Service
from .broker import BrokerError
from .strategies import WEIGHTS


def create_app(settings=None, broker=None):
    settings=settings or Settings()
    service=Service(settings,broker)

    @asynccontextmanager
    async def lifespan(app):
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    app=FastAPI(title='Astra / Alpaca Paper Challenge',version='1.0.0',lifespan=lifespan)
    app.state.service=service
    security=HTTPBearer(auto_error=False)

    async def auth(credentials: HTTPAuthorizationCredentials=Depends(security)):
        if credentials is None or not secrets.compare_digest(credentials.credentials.encode(),settings.executor_bearer_token.get_secret_value().encode()):
            raise HTTPException(401,'Unauthorized',headers={'WWW-Authenticate':'Bearer'})

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        errors=[{'loc':list(e['loc']),'type':e['type'],'msg':e['msg']} for e in exc.errors()]
        service.journal.audit('api.invalid',{'path':request.url.path,'errors':errors})
        return JSONResponse(status_code=422,content={'detail':errors})

    @app.exception_handler(BrokerError)
    async def broker_error(request,exc):
        service.fail('api',exc)
        return JSONResponse(status_code=503,content={'detail':str(exc)})

    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        return JSONResponse(status_code=409,content={'detail':str(exc)})

    @app.get('/health')
    async def health():
        return {'service':'astra-alpaca-challenge','pid':os.getpid(),'status':'ok' if service.ready else 'degraded','paper_only':True,
                'execute_orders':settings.execute_orders,'broker_reconciled':service.ready,
                'scanner_running':service.scanning,'last_scan':service.last_scan,
                'kill_switch':service.journal.get('kill_switch',False),'last_error':service.last_error}

    from fastapi import APIRouter
    api=APIRouter(prefix='/v1',dependencies=[Depends(auth)])

    @api.get('/account')
    async def account():
        raw=await service.broker.account()
        return {k:raw.get(k) for k in ('status','currency','equity','cash','buying_power','options_buying_power','trading_blocked','account_blocked')}

    @api.get('/positions')
    async def positions():
        return await service.broker.positions()

    @api.get('/orders')
    async def orders():
        return {'broker':await service.broker.orders(),'journal':service.journal.rows('orders')}

    @api.get('/signals')
    async def signals():
        return service.journal.rows('signals')

    @api.get('/audit')
    async def audit():
        return service.journal.rows('audit')

    @api.get('/challenge')
    async def challenge_state():
        return await service.state()

    @api.get('/strategies')
    async def strategies():
        return {'strategies':['ORB_RETEST','MOMENTUM','CRYPTO_BREAKOUT'],
                'filters':['relative_strength','market_regime'],'weights':WEIGHTS,
                'thresholds':{'A+':95,'A':85,'B':70},'automatic_grades':['A+','A'],
                'options':'long premium through API; underlying strategy verified',
                'trailing':'V1.1; SL/TP/break-even/time-stop active'}

    @api.get('/scanner/status')
    async def scanner_status():
        return {'running':service.scanning,'last_scan':service.last_scan or service.journal.get('scanner_last_scan'),
                'last_error':service.last_error,'crypto':settings.crypto,'equities':settings.equities}

    @api.post('/signals')
    async def signal(s:Signal):
        return await service.submit(s)

    @api.post('/scanner/start')
    async def scanner_start():
        service.scanning=True
        service.journal.audit('scanner.start',{})
        return {'running':True}

    @api.post('/scanner/stop')
    async def scanner_stop():
        service.scanning=False
        service.journal.audit('scanner.stop',{})
        return {'running':False}

    @api.post('/kill-switch/on')
    async def kill_on():
        async with service.lock:
            service.kill(True,'API')
        return {'kill_switch':True}

    @api.post('/kill-switch/off')
    async def kill_off():
        await service.reconcile()
        async with service.lock:
            state=service.journal.get('challenge',{})
            if state.get('daily_loss',0)>=settings.max_daily_loss_usd or state.get('drawdown',0)>=settings.max_total_drawdown_usd:
                raise ValueError('Risk limits still breached')
            service.kill(False,'API')
        return {'kill_switch':False}

    @api.post('/flatten')
    async def flatten():
        return await service.flatten()

    app.include_router(api)

    @app.get('/',response_class=HTMLResponse)
    async def dashboard():
        return '''<!doctype html><html lang="pl"><meta charset="utf-8"><title>Astra Paper</title>
        <style>body{background:#111820;color:#e4e8ee;font:16px system-ui;max-width:1000px;margin:40px auto}button,input{padding:10px;margin:5px}pre{white-space:pre-wrap;background:#202b36;padding:20px}h1{color:#dfb15f}</style>
        <h1>Astra / Alpaca Paper Challenge</h1><p>Panel lokalny • Paper only • stan bezpośrednio z API</p>
        <input id="token" type="password" placeholder="Executor Bearer Token" autocomplete="off">
        <button onclick="refresh()">Odśwież</button><button onclick="action('kill-switch/on')">Kill switch ON</button>
        <button onclick="action('flatten')">Flatten</button><pre id="view">Wprowadź token. Nie jest zapisywany.</pre>
        <script>async function api(p,m='GET'){let r=await fetch('/v1/'+p,{method:m,headers:{Authorization:'Bearer '+document.getElementById('token').value}});return r.json()}
        async function refresh(){let result={};for(let p of ['challenge','positions','scanner/status'])result[p]=await api(p);document.getElementById('view').textContent=JSON.stringify(result,null,2)}
        async function action(p){if(p==='flatten'&&!confirm('Anulować zlecenia i zamknąć pozycje Paper? W dry-run tylko plan.'))return;document.getElementById('view').textContent=JSON.stringify(await api(p,'POST'),null,2)}</script></html>'''
    return app
