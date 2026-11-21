import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from ..config import load_config
from ..security import redact
from ..service import DashboardService

WEB = Path(__file__).resolve().parents[1] / 'web'


def create_app(config=None, service=None, start_polling=True):
    service = service or DashboardService(config or load_config())

    @asynccontextmanager
    async def lifespan(app):
        if start_polling:
            service.task = asyncio.create_task(service.loop())
        yield
        if service.task:
            service.task.cancel()
            with suppress(asyncio.CancelledError):
                await service.task

    app = FastAPI(title='AstralJet — Obserwatorium', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.dashboard = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])

    @app.middleware('http')
    async def policy(request: Request, call_next):
        if request.method != 'GET':
            response = JSONResponse({'detail': 'Panel udostępnia wyłącznie odczyt'}, status_code=405, headers={'Allow': 'GET'})
        else:
            response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(Exception)
    async def safe_error(request, exc):
        return JSONResponse({'detail': 'Błąd panelu; brak ujawniania danych źródłowych'}, status_code=503)

    @app.get('/api/health')
    async def health():
        snap = service.view()
        return redact(dict(service='astraljet-dashboard', pid=os.getpid(), read_only=True,
                           status='degraded' if service.error or snap['account']['state'] != 'CONFIRMED' else 'ok',
                           generated_at=snap['generated_at']))

    @app.get('/api/summary')
    async def summary():
        return service.view()

    def section(key):
        async def endpoint():
            snap = service.view()
            return {'snapshot_id': snap['snapshot_id'], 'generated_at': snap['generated_at'], 'data': snap[key]}
        return endpoint

    for key in ('bots', 'positions', 'risk', 'arena', 'funding', 'schedule', 'alpaca'):
        app.add_api_route('/api/' + key, section(key), methods=['GET'])

    @app.get('/api/roles')
    async def roles_view():
        from ..collectors import roles
        return redact(await asyncio.to_thread(roles.collect))

    @app.get('/')
    async def index():
        return FileResponse(WEB / 'index.html', media_type='text/html')

    @app.get('/app.js')
    async def js():
        return FileResponse(WEB / 'app.js', media_type='application/javascript')

    @app.get('/styles.css')
    async def css():
        return FileResponse(WEB / 'styles.css', media_type='text/css')

    return app
