"""Lokalny serwer Trade Workspace (SIMULATED). Biblioteka standardowa, bez FastAPI.

Oddzielny od read-only Obserwatorium (port 8877). Nasłuchuje wyłącznie na 127.0.0.1.
POST /api/action przyjmuje akcje tylko dla symulowanej sesji i wymaga nagłówka
`X-Astra-Workspace: SIMULATED` oraz JSON (ochrona przed żądaniami z innych stron).

Uruchomienie:  python -m astraljet.workspace  (domyślnie http://127.0.0.1:8878/)
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .session import WorkspaceSession

HOST = "127.0.0.1"
PORT = 8878
WEB = Path(__file__).resolve().parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "application/javascript; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8")}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value))


def make_handler(session: WorkspaceSession, allowed_hosts: set[str]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AstraWorkspace/0.1"

        def log_message(self, fmt: str, *args: object) -> None:  # cichy log
            pass

        def _headers(self, status: int, ctype: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._send_json(421, {"detail": "Niedozwolony host"})
            path = self.path.split("?", 1)[0]
            if path == "/api/state":
                return self._send_json(200, session.snapshot())
            if path in STATIC:
                name, ctype = STATIC[path]
                body = (WEB / name).read_bytes()
                self._headers(200, ctype, len(body))
                self.wfile.write(body)
                return
            self._send_json(404, {"detail": "Nie znaleziono"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._send_json(421, {"detail": "Niedozwolony host"})
            if self.path != "/api/action":
                return self._send_json(404, {"detail": "Nie znaleziono"})
            if self.headers.get("X-Astra-Workspace") != "SIMULATED":
                return self._send_json(403, {"detail": "Brak nagłówka X-Astra-Workspace: SIMULATED"})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._send_json(415, {"detail": "Wymagany JSON"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > 65536:
                return self._send_json(413, {"detail": "Za duże żądanie"})
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                action = str(data.get("action", ""))
                params = data.get("params") or {}
                if not isinstance(params, dict):
                    raise ValueError("params musi być obiektem")
                result = session.act(action, params)
            except (ValueError, KeyError, TypeError) as exc:
                return self._send_json(400, {"detail": str(exc), "state": session.snapshot()})
            self._send_json(200, {"result": result, "state": session.snapshot()})

        def do_PUT(self) -> None:  # noqa: N802
            self._send_json(405, {"detail": "Metoda niedozwolona"})

        do_DELETE = do_PATCH = do_PUT

    return Handler


def serve(host: str = HOST, port: int = PORT, session: WorkspaceSession | None = None) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Workspace nasłuchuje wyłącznie na adresie lokalnym.")
    session = session or WorkspaceSession()
    hosts: set[str] = set()
    server = ThreadingHTTPServer((host, port), make_handler(session, hosts))
    bound = server.server_address[1]
    hosts.update({f"127.0.0.1:{bound}", f"localhost:{bound}"})
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Astra Trade Workspace (SIMULATED)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    server = serve(port=args.port, session=WorkspaceSession(seed=args.seed))
    print(f"Astra Trade Workspace (SIMULATED): http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
