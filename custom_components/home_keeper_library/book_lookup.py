"""The background queue that fills book details from Open Library.

A book that the library saved with ``needs_details: true`` goes in this queue: a
scan whose lookup failed, or a book from a CSV import. The worker reads Open
Library for the book (by ISBN, else by title and author), fills the empty fields
and downloads the cover. A network failure tries again later, at most 3 times,
with a longer wait each time. A book that Open Library does not have keeps
``needs_details: true``, and the user adds the details.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import LOOKUP_BACKOFF_S, LOOKUP_MAX_TRIES, ORIGIN
from .covers import async_store_openlibrary_cover
from .models import LibraryError
from .openlibrary_client import OpenLibraryError

if TYPE_CHECKING:
    from .coordinator import LibraryCoordinator

_LOGGER = logging.getLogger(__name__)


class BookLookup:
    """A queue of book ids, and 1 worker that looks them up."""

    def __init__(self, hass: HomeAssistant, coordinator: LibraryCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued: set[str] = set()
        self._tries: dict[str, int] = {}
        self._timers: list[Callable[[], None]] = []
        self._worker: asyncio.Task[None] | None = None
        self._started = False

    @callback
    def async_start(self) -> None:
        """Let the queue start a worker. A worker runs only while the queue has ids."""
        self._started = True
        if not self._queue.empty():
            self._start_worker()

    @callback
    def _start_worker(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        self._worker = self._coordinator.entry.async_create_background_task(
            self._hass, self._run(), "home_keeper_library book lookup"
        )

    @callback
    def async_stop(self) -> None:
        """Stop the worker and the retry timers."""
        self._started = False
        for cancel in self._timers:
            cancel()
        self._timers.clear()
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None

    @callback
    def async_enqueue(self, book_id: str) -> None:
        """Look up a book soon."""
        if book_id in self._queued:
            return
        self._queued.add(book_id)
        self._queue.put_nowait(book_id)
        if self._started:
            self._start_worker()

    async def async_join(self) -> None:
        """Wait until the queue is empty. Retries that wait on a timer do not count."""
        await self._queue.join()

    async def _run(self) -> None:
        while not self._queue.empty():
            book_id = self._queue.get_nowait()
            self._queued.discard(book_id)
            try:
                await self._lookup(book_id)
            except Exception:
                _LOGGER.exception("The lookup of book %s failed", book_id)
            finally:
                self._queue.task_done()

    async def _lookup(self, book_id: str) -> None:
        book = self._coordinator.store.state["books"].get(book_id)
        if book is None or not book.get("needs_details"):
            return
        try:
            draft = await self.async_find(book)
        except OpenLibraryError as err:
            self._retry_later(book_id, err)
            return
        self._tries.pop(book_id, None)
        if draft is None:
            return
        await self.async_apply(book_id, draft)

    async def async_find(self, book: dict[str, Any]) -> dict[str, Any] | None:
        """The Open Library draft of a book, by ISBN, else by title and author."""
        client = self._coordinator.client
        if book.get("isbn13"):
            return await client.async_lookup_isbn(book["isbn13"])
        title = str(book.get("title") or "")
        if not title:
            return None
        return await client.async_search(title, list(book.get("authors") or []))

    async def async_apply(self, book_id: str, draft: dict[str, Any]) -> None:
        """Fill a book from a draft and download its cover."""
        try:
            await self._coordinator.store.fill_book(book_id, draft, origin=ORIGIN)
        except LibraryError:
            return
        try:
            await async_store_openlibrary_cover(self._hass, self._coordinator, book_id)
        except OpenLibraryError as err:
            _LOGGER.debug("No cover for book %s: %s", book_id, err)

    def _retry_later(self, book_id: str, err: Exception) -> None:
        tries = self._tries.get(book_id, 0) + 1
        self._tries[book_id] = tries
        if tries >= LOOKUP_MAX_TRIES:
            _LOGGER.info("Open Library lookup of book %s failed: %s", book_id, err)
            self._tries.pop(book_id, None)
            return
        delay = LOOKUP_BACKOFF_S[min(tries - 1, len(LOOKUP_BACKOFF_S) - 1)]

        @callback
        def _again(_now: Any) -> None:
            self.async_enqueue(book_id)

        self._timers.append(async_call_later(self._hass, delay, _again))
