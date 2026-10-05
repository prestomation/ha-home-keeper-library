"""A fixture server with the Open Library paths that the browser tests read.

Open Library is not reachable from the test container. ``docker-compose.e2e.yml``
runs this server next to Home Assistant and sets the 2 environment variables of
``openlibrary_client.openlibrary_urls`` to its URL. Only the browser tests use
it; the Home Assistant code has no test path.

A request for ``/<path>`` returns the file ``<this directory>/<path>``, with the
query string left out. ``/search.json`` always finds nothing. Each other path
returns 404, as Open Library does for an unknown ISBN.
"""

from __future__ import annotations

import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PORT = 8080


class Handler(BaseHTTPRequestHandler):
    """Serve the fixture files. Nothing outside ROOT is served."""

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.lstrip("/")
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

    def log_message(self, format: str, *args: object) -> None:
        print(f"[openlibrary-fixture] {format % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
