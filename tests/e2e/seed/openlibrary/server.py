"""A fixture server with the Open Library paths that the browser tests read.

Open Library is not reachable from the test container. ``docker-compose.e2e.yml``
runs this server next to Home Assistant and sets the 2 environment variables of
``openlibrary_client.openlibrary_urls`` to its URL. Only the browser tests use
it; the Home Assistant code has no test path.

A request for ``/<path>`` returns the file ``<this directory>/<path>``, with the
query string left out. ``/search/authors.json`` always finds nothing.
``/search.json`` returns ``search/title/<slug>.json`` for a title that has a file,
where the slug is the title in lower case with a hyphen for each space. Else it
finds nothing. Each other path returns 404, as Open Library does for an unknown ISBN.

3 POST paths act as the write paths of Open Library for a send:

* ``/account/login`` takes the fixture S3 keys and sets a ``session`` cookie.
  Other keys get 401.
* ``/books/add`` needs that cookie and redirects to the edit page of the fixture
  edition ``OL9000001M``, as for a new book.
* ``/books/<key>/add-cover`` takes the upload and replies with a page.
"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
PORT = 8080
# The S3 keys that the browser tests type. They are not real keys.
ACCESS = "E2E-ACCESS"
SECRET = "E2E-SECRET"
SESSION = '"/people/e2e_reader,2026-10-11T00:00:00,fixture"'
NEW_EDITION = "/books/OL9000001M/Field_Notes/edit?mode=add-work"


class Handler(BaseHTTPRequestHandler):
    """Serve the fixture files. Nothing outside ROOT is served."""

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path.lstrip("/")
        if path == "search.json":
            title = (parse_qs(parts.query).get("title") or [""])[0]
            slug = "-".join(title.lower().split())
            found = f"search/title/{slug}.json"
            if slug.replace("-", "").isalnum() and (ROOT / found).is_file():
                path = found
        target = (ROOT / path).resolve()
        if ROOT not in target.parents or not target.is_file() or target.suffix == ".py":
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reply(self, status: int, headers: dict[str, str] | None = None) -> None:
        body = b"<html><body>fixture</body></html>"
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        signed_in = "session=" in (self.headers.get("Cookie") or "")
        if path == "/account/login":
            try:
                keys = json.loads(body or b"{}")
            except ValueError:
                keys = {}
            if keys.get("access") == ACCESS and keys.get("secret") == SECRET:
                self._reply(200, {"Set-Cookie": f"session={SESSION}; Path=/"})
            else:
                self._reply(401)
        elif path == "/books/add":
            self._reply(303, {"Location": NEW_EDITION} if signed_in else None)
        elif path.startswith("/books/") and path.endswith("/add-cover"):
            self._reply(200 if signed_in else 403)
        else:
            self._reply(404)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[openlibrary-fixture] {format % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
