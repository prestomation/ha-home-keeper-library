"""The Open Library client: HTTP reads for the pure parser in ``openlibrary.py``.

* The client uses the shared aiohttp session of Home Assistant and sends a
  User-Agent with the repository URL, as Open Library asks.
* Each request has a timeout of 10 seconds.
* At most 1 request goes to a host each second. A simple async limiter makes
  the next request wait.
* A lookup that finds no book is kept as a miss for 24 hours, in memory, so the
  same ISBN does not go to Open Library again in that time.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import openlibrary
from .const import (
    OPENLIBRARY_COVERS_URL,
    OPENLIBRARY_MIN_INTERVAL_S,
    OPENLIBRARY_MISS_TTL_S,
    OPENLIBRARY_TIMEOUT_S,
    OPENLIBRARY_URL,
    PANEL_VERSION,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
_MAX_AUTHORS = 3
_MAX_COVER_BYTES = 10 * 1024 * 1024


class OpenLibraryError(Exception):
    """Open Library could not be read: a network error, a timeout or a 5xx."""


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
        work = None
        if work_key := openlibrary.work_key(edition):
            found = await self._request(openlibrary.work_url(self._base, work_key))
            work = found if isinstance(found, dict) else None
        authors = []
        for author_key in openlibrary.author_keys(edition, work)[:_MAX_AUTHORS]:
            found = await self._request(openlibrary.author_url(self._base, author_key))
            if isinstance(found, dict):
                authors.append(found)
        draft = openlibrary.parse_edition(edition, work, authors)
        if not draft.get("isbn13"):
            draft["isbn13"] = isbn13
        return draft

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
