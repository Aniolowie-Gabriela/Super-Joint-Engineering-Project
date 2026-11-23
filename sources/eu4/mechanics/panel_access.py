"""Dostęp do lokalnego panelu z przeglądarki uruchomionej przez Atlas EU4."""

import secrets
from threading import Lock
from time import monotonic

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


LAUNCH_PATH = "/_atlas/launch/"
LAUNCH_TIMEOUT = 120
REOPEN = "Otwórz Atlas EU4 z menu Start lub uruchom plik Uruchom-EU4.cmd."
REOPEN_HTML = f"""<!doctype html>
<html lang="pl">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atlas EU4</title>
<h1>Atlas EU4</h1>
<p>{REOPEN}</p>
</html>"""


class PanelAccess:
    def __init__(self):
        self._session = secrets.token_urlsafe(32)
        self._launch_tickets = {}
        self._lock = Lock()

    def launch_url(self, host, port):
        ticket = secrets.token_urlsafe(32)
        now = monotonic()
        with self._lock:
            self._launch_tickets = {key: expires for key, expires in self._launch_tickets.items()
                                    if expires > now}
            self._launch_tickets[ticket] = now + LAUNCH_TIMEOUT
        return f"http://{host}:{port}{LAUNCH_PATH}{ticket}"

    def response(self, request):
        """Zwróć odpowiedź uruchomienia lub odmowy, albo None dla otwartego panelu."""
        path = request.url.path
        cookie = f"atlas_eu4_{request.url.port or 80}"
        if request.method == "GET" and path.startswith(LAUNCH_PATH):
            ticket = path.removeprefix(LAUNCH_PATH)
            with self._lock:
                expires = self._launch_tickets.pop(ticket, 0)
            if expires > monotonic():
                response = RedirectResponse("/", status_code=303, headers={"Referrer-Policy": "no-referrer"})
                response.set_cookie(cookie, self._session, httponly=True, samesite="strict")
                return response
            return HTMLResponse(REOPEN_HTML, status_code=403, headers={"Referrer-Policy": "no-referrer"})

        session = request.cookies.get(cookie, "")
        if session.isascii() and secrets.compare_digest(session, self._session):
            return None
        if path == "/":
            return HTMLResponse(REOPEN_HTML, status_code=403)
        return JSONResponse({"detail": REOPEN}, status_code=403)
