"""The Open Library client: HTTP reads for the pure parser in ``openlibrary.py``.

* The client uses the shared aiohttp session of Home Assistant and sends a
  User-Agent with the repository URL, as Open Library asks.
* Each request has a timeout of 10 seconds.
* At most 1 request goes to a host each second. A simple async limiter makes
  the next request wait.
* A lookup that finds no book is kept as a miss for 24 hours, in memory, so the
  same ISBN does not go to Open Library again in that time.
* 2 environment variables can replace the base URLs (``openlibrary_urls``).
  Only the browser test setup sets them, to point at a fixture server.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any, TypedDict
from urllib.parse import urlencode, urlsplit

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import openlibrary
from .const import (
    OPENLIBRARY_COVERS_URL,
    OPENLIBRARY_COVERS_URL_ENV,
    OPENLIBRARY_MIN_INTERVAL_S,
    OPENLIBRARY_MISS_TTL_S,
    OPENLIBRARY_TIMEOUT_S,
    OPENLIBRARY_URL,
    OPENLIBRARY_URL_ENV,
    PANEL_VERSION,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
_MAX_AUTHORS = 3
_MAX_COVER_BYTES = 10 * 1024 * 1024


class OpenLibraryUrls(TypedDict, total=False):
    """The base URL overrides of the client."""

    base_url: str
    covers_url: str


def openlibrary_urls(env: Mapping[str, str]) -> OpenLibraryUrls:
    """The ``base_url`` and ``covers_url`` overrides that *env* sets.

    An empty or missing variable keeps the default URL.
    """
    out: OpenLibraryUrls = {}
    if url := env.get(OPENLIBRARY_URL_ENV, "").strip().rstrip("/"):
        out["base_url"] = url
    if url := env.get(OPENLIBRARY_COVERS_URL_ENV, "").strip().rstrip("/"):
        out["covers_url"] = url
    return out


class OpenLibraryError(Exception):
    """Open Library could not be read: a network error, a timeout or a 5xx."""


class PostReply(TypedDict):
    """The parts of a POST reply that the writer reads."""

    status: int
    location: str | None
    cookies: dict[str, str]


class OpenLibraryClient:
    """Reads books and covers from Open Library."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        base_url: str = OPENLIBRARY_URL,
        covers_url: str = OPENLIBRARY_COVERS_URL,
        min_interval: float = OPENLIBRARY_MIN_INTERVAL_S,
    ) -> None:
        self._hass = hass
        self._base = base_url
        self._covers = covers_url
        self._min_interval = min_interval
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}
        self._misses: dict[str, float] = {}
        self._headers = {"User-Agent": USER_AGENT.format(version=PANEL_VERSION)}

    async def _wait_turn(self, host: str) -> None:
        """Wait until the host can take the next request."""
        delay = self._last.get(host, 0.0) + self._min_interval - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self._last[host] = time.monotonic()

    @property
    def base_url(self) -> str:
        """The base URL of Open Library."""
        return self._base

    async def async_post(
        self,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        cookie: str | None = None,
    ) -> PostReply:
        """POST to *path* below the base URL, with no redirect.

        The reply gives the status, the ``Location`` header and the cookies that
        Open Library sets. The same limit of 1 request a second holds. Raise
        :class:`OpenLibraryError` on a network error, a timeout or a 5xx.
        """
        url = f"{self._base}{path}"
        host = urlsplit(url).netloc
        lock = self._locks.setdefault(host, asyncio.Lock())
        session = async_get_clientsession(self._hass)
        headers = dict(self._headers)
        if cookie:
            headers["Cookie"] = cookie
        async with lock:
            await self._wait_turn(host)
            try:
                async with session.post(
                    url,
                    json=json,
                    data=data,
                    headers=headers,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=OPENLIBRARY_TIMEOUT_S),
                ) as response:
                    if response.status >= 500:
                        raise OpenLibraryError(f"HTTP {response.status}")
                    return {
                        "status": response.status,
                        "location": response.headers.get("Location"),
                        # The value as the server sent it, quotes included, so
                        # it goes back unchanged in the Cookie header.
                        "cookies": {
                            name: morsel.coded_value
                            for name, morsel in response.cookies.items()
                        },
                    }
            except (TimeoutError, aiohttp.ClientError) as err:
                raise OpenLibraryError(str(err)) from err

    async def async_get_json(self, path: str) -> Any:
        """GET the JSON at *path* below the base URL, or None for a 404."""
        return await self._request(f"{self._base}{path}")

    async def _request(self, url: str, *, binary: bool = False) -> Any:
        """GET *url*. Return the JSON or the bytes, or None for a 404."""
        host = urlsplit(url).netloc
        lock = self._locks.setdefault(host, asyncio.Lock())
        session = async_get_clientsession(self._hass)
        async with lock:
            await self._wait_turn(host)
            try:
                async with session.get(
                    url,
                    headers=self._headers,
                    timeout=aiohttp.ClientTimeout(total=OPENLIBRARY_TIMEOUT_S),
                ) as response:
                    if response.status == 404:
                        return None
                    if response.status >= 400:
                        raise OpenLibraryError(f"HTTP {response.status}")
                    if binary:
                        data = await response.read()
                        return data[:_MAX_COVER_BYTES]
                    return await response.json(content_type=None)
            except (TimeoutError, aiohttp.ClientError, ValueError) as err:
                raise OpenLibraryError(str(err)) from err

    def _is_miss(self, key: str) -> bool:
        expires = self._misses.get(key)
        if expires is None:
            return False
        if expires < time.monotonic():
            del self._misses[key]
            return False
        return True

    def _remember_miss(self, key: str) -> None:
        self._misses[key] = time.monotonic() + OPENLIBRARY_MISS_TTL_S

    def forget_miss(self, isbn13: str | None) -> None:
        """Forget the miss of an ISBN, so the next lookup asks Open Library again."""
        if isbn13:
            self._misses.pop(f"isbn:{isbn13}", None)

    async def async_lookup_isbn(self, isbn13: str) -> dict[str, Any] | None:
        """The book draft of an ISBN, or None if Open Library has no edition.

        Raise :class:`OpenLibraryError` if Open Library cannot be read.
        """
        key = f"isbn:{isbn13}"
        if self._is_miss(key):
            return None
        edition = await self._request(openlibrary.edition_url(self._base, isbn13))
        if not isinstance(edition, dict):
            self._remember_miss(key)
            return None
        draft = await self._draft(edition)
        if not draft.get("isbn13"):
            draft["isbn13"] = isbn13
        return draft

    async def async_lookup_edition(self, edition_key: str) -> dict[str, Any] | None:
        """The book draft of an edition key ``OL…M``, or None if there is none.

        Raise :class:`OpenLibraryError` if Open Library cannot be read.
        """
        edition = await self._request(f"{self._base}/books/{edition_key}.json")
        if not isinstance(edition, dict) or not str(edition.get("key", "")).startswith(
            "/books/"
        ):
            return None
        return await self._draft(edition)

    async def _draft(self, edition: dict[str, Any]) -> dict[str, Any]:
        """The draft of an edition document, with its work and its authors."""
        work = None
        if work_key := openlibrary.work_key(edition):
            found = await self._request(openlibrary.work_url(self._base, work_key))
            work = found if isinstance(found, dict) else None
        authors = []
        for author_key in openlibrary.author_keys(edition, work)[:_MAX_AUTHORS]:
            found = await self._request(openlibrary.author_url(self._base, author_key))
            if isinstance(found, dict):
                authors.append(found)
        return openlibrary.parse_edition(edition, work, authors)

    async def async_search(
        self, title: str, authors: list[str]
    ) -> dict[str, Any] | None:
        """The best search match for a title and author, or None."""
        key = f"search:{title.casefold()}|{(authors or [''])[0].casefold()}"
        if self._is_miss(key):
            return None
        query = {"title": title, "limit": "5"}
        if authors:
            query["author"] = authors[0]
        result = await self._request(f"{self._base}/search.json?{urlencode(query)}")
        match = openlibrary.best_match(openlibrary.parse_search(result), title, authors)
        if match is None:
            self._remember_miss(key)
        return match

    async def async_cover(self, cover_id: int) -> bytes | None:
        """The bytes of the large cover image, or None if it has none."""
        data = await self._request(
            openlibrary.cover_image_url(self._covers, cover_id), binary=True
        )
        return data if isinstance(data, bytes) and data else None
