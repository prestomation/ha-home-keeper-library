"""The library store: the 1 write path for library data.

Every change goes through a method of :class:`LibraryStore`. Each method checks
the input with the pure ``models`` functions, changes the document, saves it,
fires the bus events of the change and then tells the listeners (the
coordinator, the ``subscribe`` command and the syncs). Entities, the tab and the
card read the document and never write it.

``revision`` goes up by 1 on each change. The ``subscribe`` websocket command
sends it, and the client then reads ``get_state`` again.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import events, models
from .const import (
    EVENT_BOOK_ADDED,
    EVENT_BOOK_FINISHED,
    EVENT_BOOK_REMOVED,
    EVENT_BOOK_UPDATED,
    EVENT_BOOKCASE_ADDED,
    EVENT_BOOKCASE_REMOVED,
    EVENT_BOOKCASE_UPDATED,
    EVENT_COPY_ADDED,
    EVENT_COPY_MOVED,
    EVENT_COPY_REMOVED,
    EVENT_COPY_UPDATED,
    EVENT_IMPORT_COMPLETED,
    EVENT_LOAN_OVERDUE,
    EVENT_LOAN_REMOVED,
    EVENT_LOAN_RETURNED,
    EVENT_LOAN_STARTED,
    EVENT_LOAN_UPDATED,
    EVENT_PERSON_SETTINGS_UPDATED,
    EVENT_READING_CHANGED,
    EVENT_READING_UPDATED,
    EVENT_ROOM_ADDED,
    EVENT_ROOM_REMOVED,
    EVENT_ROOM_UPDATED,
    EVENT_SETTINGS_UPDATED,
    EVENT_SHELF_ADDED,
    EVENT_SHELF_REMOVED,
    EVENT_SHELF_UPDATED,
    EVENT_WISHLIST_ADDED,
    EVENT_WISHLIST_REMOVED,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
)
from .models import LibraryError
from .wishlist import SyncPlan

_LOGGER = logging.getLogger(__name__)

Event = tuple[str, dict[str, Any]]


class _LibraryStorage(Store[dict[str, Any]]):
    """The storage file, with the migration hook."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the document in the current version.

        Version 1.1 is the first version. ``models.normalize_state`` adds each
        missing section, so a new section needs no migration step.
        """
        return models.normalize_state(old_data)


def today() -> str:
    """Today in the time zone of Home Assistant, as ``YYYY-MM-DD``."""
    return dt_util.now().date().isoformat()


def now() -> str:
    """The time now, aware, in ISO 8601."""
    return dt_util.now().isoformat()


class LibraryStore:
    """Loads, saves and changes the library document, and fires the events."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._storage = _LibraryStorage(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
        )
        self.state: dict[str, Any] = models.empty_state()
        self.revision = 0
        self._listeners: list[Callable[[], None]] = []
        # The cover files that a change made unused. ``covers.py`` deletes them.
        self.on_cover_released: Callable[[str], None] | None = None

    async def load(self) -> None:
        """Load the document, or start an empty one."""
        self.state = models.normalize_state(await self._storage.async_load())

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call *listener* after each change. Return a callable that removes it."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def async_notify(self) -> None:
        """Tell the listeners about a change outside the document, such as the
        currency option. The revision goes up."""
        self.revision += 1
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("A library store listener failed")

    @callback
    def async_settings_updated(
        self, changed_fields: list[str], currency: str, *, origin: str | None = None
    ) -> None:
        """Fire ``settings_updated`` for a change of the entry options.

        The options are on the config entry, not in the document, so there is
        nothing to save. The listeners hear about the change.
        """
        payload = events.settings_event_data(changed_fields, currency, origin)
        self.hass.bus.async_fire(EVENT_SETTINGS_UPDATED, payload)
        self.async_notify()

    async def _commit(self, fired: list[Event]) -> None:
        """Save, fire the events and tell the listeners."""
        await self._storage.async_save(self.state)
        self.revision += 1
        for name, data in fired:
            self.hass.bus.async_fire(name, data)
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("A library store listener failed")

    # ── Lookups ──────────────────────────────────────────────────────────────

    def _get(self, section: str, key: str, record_id: str) -> dict[str, Any]:
        record = self.state[section].get(record_id)
        if record is None:
            raise LibraryError(f"{key}_not_found", id=record_id)
        return dict(record)

    def room(self, room_id: str) -> dict[str, Any]:
        """The room, or ``room_not_found``."""
        return self._get("rooms", "room", room_id)

    def bookcase(self, bookcase_id: str) -> dict[str, Any]:
        """The bookcase, or ``bookcase_not_found``."""
        return self._get("bookcases", "bookcase", bookcase_id)

    def shelf(self, shelf_id: str) -> dict[str, Any]:
        """The shelf, or ``shelf_not_found``."""
        return self._get("shelves", "shelf", shelf_id)

    def book(self, book_id: str) -> dict[str, Any]:
        """The book, or ``book_not_found``."""
        return self._get("books", "book", book_id)

    def copy(self, copy_id: str) -> dict[str, Any]:
        """The copy, or ``copy_not_found``."""
        return self._get("copies", "copy", copy_id)

    def loan(self, loan_id: str) -> dict[str, Any]:
        """The loan, or ``loan_not_found``."""
        return self._get("loans", "loan", loan_id)

    def check_shelf(self, shelf_id: str | None) -> str | None:
        """*shelf_id* if it is None or a known shelf, else ``shelf_not_found``."""
        if shelf_id:
            self.shelf(shelf_id)
        return shelf_id or None

    def reading_row(self, person_id: str, book_id: str) -> dict[str, Any] | None:
        """The reading row of a person for a book."""
        row = (self.state["reading"].get(person_id) or {}).get(book_id)
        return dict(row) if row else None

    # ── Rooms, bookcases and shelves ─────────────────────────────────────────

    async def add_room(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Add a room."""
        room = models.build_room(data, order=models.next_order(self.state["rooms"]))
        self.state["rooms"][room["id"]] = room
        await self._commit([(EVENT_ROOM_ADDED, events.room_event_data(room, origin))])
        return dict(room)

    async def update_room(
        self, room_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change a room."""
        updated, changed = models.update_location("room", self.room(room_id), data)
        if not changed:
            return updated
        self.state["rooms"][room_id] = updated
        payload = events.location_changed_data(
            events.room_event_data(updated, origin), changed
        )
        await self._commit([(EVENT_ROOM_UPDATED, payload)])
        return dict(updated)

    async def add_bookcase(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Add a bookcase to a room."""
        self.room(str(data.get("room_id")))
        order = models.next_order(self.state["bookcases"], room_id=data["room_id"])
        bookcase = models.build_bookcase(data, order=order)
        self.state["bookcases"][bookcase["id"]] = bookcase
        fired = [(EVENT_BOOKCASE_ADDED, events.bookcase_event_data(bookcase, origin))]
        await self._commit(fired)
        return dict(bookcase)

    async def update_bookcase(
        self, bookcase_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change a bookcase. A new ``room_id`` moves it to another room."""
        if "room_id" in data:
            self.room(str(data["room_id"]))
        updated, changed = models.update_location(
            "bookcase", self.bookcase(bookcase_id), data
        )
        if not changed:
            return updated
        self.state["bookcases"][bookcase_id] = updated
        payload = events.location_changed_data(
            events.bookcase_event_data(updated, origin), changed
        )
        await self._commit([(EVENT_BOOKCASE_UPDATED, payload)])
        return dict(updated)

    async def add_shelf(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Add a shelf to a bookcase."""
        self.bookcase(str(data.get("bookcase_id")))
        order = models.next_order(
            self.state["shelves"], bookcase_id=data["bookcase_id"]
        )
        shelf = models.build_shelf(data, order=order)
        self.state["shelves"][shelf["id"]] = shelf
        await self._commit(
            [(EVENT_SHELF_ADDED, events.shelf_event_data(shelf, origin))]
        )
        return dict(shelf)

    async def update_shelf(
        self, shelf_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change a shelf. A new ``bookcase_id`` moves it to another bookcase."""
        if "bookcase_id" in data:
            self.bookcase(str(data["bookcase_id"]))
        updated, changed = models.update_location("shelf", self.shelf(shelf_id), data)
        if not changed:
            return updated
        self.state["shelves"][shelf_id] = updated
        payload = events.location_changed_data(
            events.shelf_event_data(updated, origin), changed
        )
        await self._commit([(EVENT_SHELF_UPDATED, payload)])
        return dict(updated)

    def _remove_shelf(
        self, shelf_id: str, fired: list[Event], origin: str | None
    ) -> None:
        """Remove a shelf and move its copies to no shelf. No save."""
        shelf = self.state["shelves"].pop(shelf_id)
        for copy in self.state["copies"].values():
            if copy.get("shelf_id") != shelf_id:
                continue
            copy["shelf_id"] = None
            book = self.state["books"].get(copy["book_id"], {"id": copy["book_id"]})
            fired.append(
                (
                    EVENT_COPY_MOVED,
                    events.copy_moved_event_data(book, copy, shelf_id, origin),
                )
            )
        fired.append((EVENT_SHELF_REMOVED, events.shelf_event_data(shelf, origin)))

    def _remove_bookcase(
        self, bookcase_id: str, fired: list[Event], origin: str | None
    ) -> None:
        """Remove a bookcase with its shelves. No save."""
        for shelf_id in [
            s["id"]
            for s in self.state["shelves"].values()
            if s.get("bookcase_id") == bookcase_id
        ]:
            self._remove_shelf(shelf_id, fired, origin)
        bookcase = self.state["bookcases"].pop(bookcase_id)
        fired.append(
            (EVENT_BOOKCASE_REMOVED, events.bookcase_event_data(bookcase, origin))
        )

    async def delete_room(
        self, room_id: str, *, force: bool = False, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a room. A room with bookcases needs *force*."""
        room = self.room(room_id)
        children = [
            b["id"]
            for b in self.state["bookcases"].values()
            if b.get("room_id") == room_id
        ]
        if children and not force:
            raise LibraryError("room_not_empty", count=len(children))
        fired: list[Event] = []
        for bookcase_id in children:
            self._remove_bookcase(bookcase_id, fired, origin)
        del self.state["rooms"][room_id]
        fired.append((EVENT_ROOM_REMOVED, events.room_event_data(room, origin)))
        await self._commit(fired)
        return room

    async def delete_bookcase(
        self, bookcase_id: str, *, force: bool = False, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a bookcase. A bookcase with shelves needs *force*."""
        bookcase = self.bookcase(bookcase_id)
        count = sum(
            1
            for s in self.state["shelves"].values()
            if s.get("bookcase_id") == bookcase_id
        )
        if count and not force:
            raise LibraryError("bookcase_not_empty", count=count)
        fired: list[Event] = []
        self._remove_bookcase(bookcase_id, fired, origin)
        await self._commit(fired)
        return bookcase

    async def delete_shelf(
        self, shelf_id: str, *, force: bool = False, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a shelf. A shelf with copies needs *force*."""
        shelf = self.shelf(shelf_id)
        count = sum(
            1 for c in self.state["copies"].values() if c.get("shelf_id") == shelf_id
        )
        if count and not force:
            raise LibraryError("shelf_not_empty", count=count)
        fired: list[Event] = []
        self._remove_shelf(shelf_id, fired, origin)
        await self._commit(fired)
        return shelf

    # ── Books ────────────────────────────────────────────────────────────────

    async def add_book(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> tuple[dict[str, Any], bool]:
        """Add a book. Return ``(book, existing)``.

        If the ISBN-13 of the new book matches a stored book, the store adds no
        book and returns the stored one with ``existing`` True.
        """
        book = models.build_book(data, now=now())
        if found := models.find_book_by_isbn(self.state, book["isbn13"]):
            return dict(found), True
        self.state["books"][book["id"]] = book
        await self._commit([(EVENT_BOOK_ADDED, events.book_event_data(book, origin))])
        return dict(book), False

    async def update_book(
        self, book_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change the fields of a book."""
        updated, changed = models.update_book(self.book(book_id), data, now=now())
        if changed and "isbn13" in changed and updated["isbn13"]:
            other = models.find_book_by_isbn(self.state, updated["isbn13"])
            if other is not None and other["id"] != book_id:
                raise LibraryError("duplicate_isbn", isbn=updated["isbn13"])
        return await self._replace_book(updated, changed, origin)

    async def fill_book(
        self, book_id: str, draft: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Fill the empty fields of a book from an Open Library draft."""
        updated, changed = models.fill_from_draft(self.book(book_id), draft, now=now())
        if "isbn13" in changed:
            other = models.find_book_by_isbn(self.state, updated["isbn13"])
            if other is not None and other["id"] != book_id:
                updated["isbn13"] = None
                updated["isbn10"] = None
                changed = [f for f in changed if f not in ("isbn13", "isbn10")]
        return await self._replace_book(updated, changed, origin)

    async def _replace_book(
        self, updated: dict[str, Any], changed: list[str], origin: str | None
    ) -> dict[str, Any]:
        if not changed:
            return updated
        self.state["books"][updated["id"]] = updated
        payload = events.book_updated_event_data(updated, changed, origin)
        await self._commit([(EVENT_BOOK_UPDATED, payload)])
        return dict(updated)

    async def set_cover(
        self,
        book_id: str,
        kind: str,
        file: str | None,
        *,
        origin: str | None = None,
    ) -> dict[str, Any]:
        """Set the cover of a book. The previous file is released."""
        book = self.book(book_id)
        models.choice(kind, "kind", models.COVER_KINDS)
        cover = {"kind": kind, "file": file if kind != "none" else None}
        old = (book.get("cover") or {}).get("file")
        if cover == book.get("cover"):
            return book
        book["cover"] = cover
        book["updated_at"] = now()
        self.state["books"][book_id] = book
        payload = events.book_updated_event_data(book, ["cover"], origin)
        await self._commit([(EVENT_BOOK_UPDATED, payload)])
        if old and old != cover["file"]:
            self._release_cover(old)
        return dict(book)

    def _release_cover(self, file: str) -> None:
        if self.on_cover_released is not None:
            self.on_cover_released(file)

    async def delete_book(
        self, book_id: str, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a book with its copies, reading rows and loans."""
        book = self.book(book_id)
        fired: list[Event] = []
        for copy_id in [
            c["id"] for c in self.state["copies"].values() if c["book_id"] == book_id
        ]:
            copy = self.state["copies"].pop(copy_id)
            fired.append(
                (EVENT_COPY_REMOVED, events.copy_event_data(book, copy, origin))
            )
        for rows in self.state["reading"].values():
            rows.pop(book_id, None)
        self.state["reading"] = {p: r for p, r in self.state["reading"].items() if r}
        for loan_id in [
            lo["id"] for lo in self.state["loans"].values() if lo["book_id"] == book_id
        ]:
            del self.state["loans"][loan_id]
        self._orphan_item(book.get("wishlist"))
        del self.state["books"][book_id]
        fired.append((EVENT_BOOK_REMOVED, events.book_event_data(book, origin)))
        await self._commit(fired)
        if file := (book.get("cover") or {}).get("file"):
            self._release_cover(file)
        return book

    # ── Copies ───────────────────────────────────────────────────────────────

    def _copy_record(self, data: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        book = self.book(str(data.get("book_id")))
        self.check_shelf(data.get("shelf_id"))
        return models.build_copy(data, now=now()), book

    async def add_copy(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Add a copy of a book.

        The first copy of a book on the wishlist takes it off the wishlist, as
        ``got_wishlist_book`` does. The wishlist sync then removes its to-do
        item.
        """
        record, book = self._copy_record(data)
        clears = models.copy_clears_wishlist(self.state, book["id"])
        self.state["copies"][record["id"]] = record
        fired: list[Event] = [
            (EVENT_COPY_ADDED, events.copy_event_data(book, record, origin))
        ]
        if clears:
            entry = book["wishlist"]
            self._orphan_item(entry)
            book["wishlist"] = None
            self.state["books"][book["id"]] = book
            payload = events.wishlist_event_data(book, entry, origin)
            fired.append((EVENT_WISHLIST_REMOVED, payload))
        await self._commit(fired)
        return dict(record)

    async def update_copy(
        self, copy_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change a copy.

        A new shelf fires ``copy_moved``. A change of the other fields fires
        ``copy_updated`` with the names of those fields.
        """
        record = self.copy(copy_id)
        if "shelf_id" in data:
            self.check_shelf(data["shelf_id"])
        updated, changed = models.update_copy(record, data)
        if not changed:
            return updated
        self.state["copies"][copy_id] = updated
        fired: list[Event] = []
        book = self.book(updated["book_id"])
        if "shelf_id" in changed:
            fired.append(
                (
                    EVENT_COPY_MOVED,
                    events.copy_moved_event_data(
                        book, updated, record.get("shelf_id"), origin
                    ),
                )
            )
        if other := [f for f in changed if f != "shelf_id"]:
            payload = events.copy_updated_event_data(book, updated, other, origin)
            fired.append((EVENT_COPY_UPDATED, payload))
        await self._commit(fired)
        return dict(updated)

    async def move_copy(
        self, copy_id: str, shelf_id: str | None, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Move a copy to a shelf, or to no shelf."""
        return await self.update_copy(copy_id, {"shelf_id": shelf_id}, origin=origin)

    async def delete_copy(
        self, copy_id: str, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a copy. A copy that is lent out cannot be deleted."""
        record = self.copy(copy_id)
        if models.open_loan_of_copy(self.state, copy_id):
            raise LibraryError("copy_on_loan")
        del self.state["copies"][copy_id]
        book = self.book(record["book_id"])
        payload = events.copy_event_data(book, record, origin)
        await self._commit([(EVENT_COPY_REMOVED, payload)])
        return record

    # ── Reading ──────────────────────────────────────────────────────────────

    def _reading_events(
        self,
        book: dict[str, Any],
        person_id: str,
        row: dict[str, Any] | None,
        previous: str | None,
        origin: str | None,
    ) -> list[Event]:
        status = row["status"] if row else None
        fired: list[Event] = [
            (
                EVENT_READING_CHANGED,
                events.reading_changed_event_data(
                    book, person_id, status, previous, origin
                ),
            )
        ]
        if row is not None and status == "read" and previous != "read":
            fired.append(
                (
                    EVENT_BOOK_FINISHED,
                    events.book_finished_event_data(book, person_id, row, origin),
                )
            )
        return fired

    async def set_reading(
        self,
        book_id: str,
        person_id: str,
        data: dict[str, Any],
        *,
        origin: str | None = None,
    ) -> dict[str, Any] | None:
        """Set the reading row of a person. Status ``none`` removes the row."""
        book = self.book(book_id)
        current = self.reading_row(person_id, book_id)
        previous = current["status"] if current else None
        if data.get("status") == models.STATUS_NONE:
            if current is None:
                return None
            del self.state["reading"][person_id][book_id]
            if not self.state["reading"][person_id]:
                del self.state["reading"][person_id]
            fired = self._reading_events(book, person_id, None, previous, origin)
            await self._commit(fired)
            return None
        row, changed = models.apply_reading(current, data, now=now(), today=today())
        if not changed:
            return row
        self.state["reading"].setdefault(person_id, {})[book_id] = row
        if "status" in changed:
            fired = self._reading_events(book, person_id, row, previous, origin)
        else:
            payload = events.reading_updated_event_data(
                book, person_id, row["status"], changed, origin
            )
            fired = [(EVENT_READING_UPDATED, payload)]
        await self._commit(fired)
        return dict(row)

    # ── Loans ────────────────────────────────────────────────────────────────

    async def add_loan(
        self, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Start a loan.

        ``out`` lends a copy, and the copy keeps its shelf. ``in`` borrows a book,
        and sets the status of the person to ``reading`` if it is ``want`` or
        absent.
        """
        if data.get("direction") == "out":
            copy = self.copy(str(data.get("copy_id")))
            if models.open_loan_of_copy(self.state, copy["id"]):
                raise LibraryError("copy_on_loan")
            data = {**data, "book_id": copy["book_id"]}
        loan = models.build_loan(data, today=today())
        book = self.book(loan["book_id"])
        self.state["loans"][loan["id"]] = loan
        fired: list[Event] = [
            (EVENT_LOAN_STARTED, events.loan_event_data(book, loan, origin))
        ]
        if loan["direction"] == "in" and loan["person_id"]:
            current = self.reading_row(loan["person_id"], book["id"])
            if current is None or current["status"] == "want":
                row, _ = models.apply_reading(
                    current, {"status": "reading"}, now=now(), today=today()
                )
                self.state["reading"].setdefault(loan["person_id"], {})[book["id"]] = (
                    row
                )
                fired += self._reading_events(
                    book,
                    loan["person_id"],
                    row,
                    current["status"] if current else None,
                    origin,
                )
        await self._commit(fired)
        return dict(loan)

    async def return_loan(
        self, loan_id: str, returned: str | None = None, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Return a loan. A returned loan stays returned."""
        loan = self.loan(loan_id)
        if not models.is_open(loan):
            return loan
        loan["returned"] = models.iso_date(returned, "returned") or today()
        self.state["loans"][loan_id] = loan
        book = self.book(loan["book_id"])
        payload = events.loan_event_data(book, loan, origin)
        await self._commit([(EVENT_LOAN_RETURNED, payload)])
        return dict(loan)

    async def update_loan(
        self, loan_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change the party, the dates, the format or the note of a loan."""
        updated, changed = models.update_loan(self.loan(loan_id), data)
        if not changed:
            return updated
        self.state["loans"][loan_id] = updated
        payload = events.loan_updated_event_data(
            self._loan_book(updated), updated, changed, origin
        )
        await self._commit([(EVENT_LOAN_UPDATED, payload)])
        return dict(updated)

    async def delete_loan(
        self, loan_id: str, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Delete a loan. The loan sync deletes its Home Keeper task."""
        loan = self.loan(loan_id)
        del self.state["loans"][loan_id]
        payload = events.loan_event_data(self._loan_book(loan), loan, origin)
        await self._commit([(EVENT_LOAN_REMOVED, payload)])
        return loan

    def _loan_book(self, loan: dict[str, Any]) -> dict[str, Any]:
        """The book of a loan, for an event payload."""
        return self.state["books"].get(loan["book_id"]) or {"id": loan["book_id"]}

    async def set_lookup_tries(self, book_id: str, tries: int) -> None:
        """Record the count of Open Library lookups of a book that gave no details.

        The lookup queue keeps the count here, so the retry limit holds across
        a restart. The count is bookkeeping of the queue that no user sees, so
        it fires no event, as ``set_loan_task`` does.
        """
        book = self.state["books"].get(book_id)
        if book is None or book.get("lookup_tries") == tries:
            return
        book["lookup_tries"] = tries
        await self._commit([])

    async def set_loan_task(self, loan_id: str, task_id: str | None) -> None:
        """Record the Home Keeper task id of a loan."""
        loan = self.state["loans"].get(loan_id)
        if loan is None or loan.get("hk_task_id") == task_id:
            return
        loan["hk_task_id"] = task_id
        await self._commit([])

    async def forget_loan_task(self, loan_id: str, *, disable: bool) -> None:
        """Clear the task id of a loan. *disable* also turns ``add_task`` off."""
        loan = self.state["loans"].get(loan_id)
        if loan is None:
            return
        loan["hk_task_id"] = None
        if disable:
            loan["add_task"] = False
        await self._commit([])

    async def fire_overdue(self, today_: str) -> list[str]:
        """Fire ``loan_overdue`` once for each loan that passed its due date."""
        fired: list[Event] = []
        ids = []
        for loan in self.state["loans"].values():
            if not models.is_overdue(loan, today_) or loan.get("overdue_fired"):
                continue
            loan["overdue_fired"] = True
            book = self.state["books"].get(loan["book_id"]) or {"id": loan["book_id"]}
            fired.append((EVENT_LOAN_OVERDUE, events.loan_event_data(book, loan, None)))
            ids.append(loan["id"])
        if fired:
            await self._commit(fired)
        return ids

    # ── Wishlist ─────────────────────────────────────────────────────────────

    def _orphan_item(self, entry: dict[str, Any] | None) -> None:
        """Keep the to-do item of a removed wishlist entry for the sync to remove."""
        if not entry or not entry.get("todo_uid") or not entry.get("todo_entity"):
            return
        self.state["todo_orphans"].append(
            {"entity_id": entry["todo_entity"], "uid": entry["todo_uid"]}
        )

    async def add_to_wishlist(
        self,
        book_id: str,
        person_id: str,
        *,
        buy: bool = False,
        origin: str | None = None,
    ) -> dict[str, Any]:
        """Put a book on the wishlist of a person."""
        book = self.book(book_id)
        if book.get("wishlist"):
            raise LibraryError("already_on_wishlist")
        entry = models.build_wishlist(person_id, buy=buy, now=now())
        book["wishlist"] = entry
        self.state["books"][book_id] = book
        payload = events.wishlist_event_data(book, entry, origin)
        await self._commit([(EVENT_WISHLIST_ADDED, payload)])
        return dict(book)

    async def update_wishlist(
        self, book_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change ``buy`` or the person of a wishlist entry."""
        book = self.book(book_id)
        entry = dict(book.get("wishlist") or {})
        if not entry:
            raise LibraryError("not_on_wishlist")
        changed = []
        if "buy" in data and models.boolean(data["buy"], "buy") != entry["buy"]:
            entry["buy"] = data["buy"]
            changed.append("buy")
        if "person_id" in data and data["person_id"] != entry["person_id"]:
            entry["person_id"] = models.text(
                data["person_id"], "person_id", models.MAX_SHORT, required=True
            )
            changed.append("person_id")
        if not changed:
            return book
        book["wishlist"] = entry
        book["updated_at"] = now()
        self.state["books"][book_id] = book
        payload = events.book_updated_event_data(book, ["wishlist"], origin)
        await self._commit([(EVENT_BOOK_UPDATED, payload)])
        return dict(book)

    async def remove_from_wishlist(
        self, book_id: str, *, origin: str | None = None
    ) -> dict[str, Any]:
        """Take a book off the wishlist."""
        book = self.book(book_id)
        entry = book.get("wishlist")
        if not entry:
            raise LibraryError("not_on_wishlist")
        self._orphan_item(entry)
        book["wishlist"] = None
        self.state["books"][book_id] = book
        payload = events.wishlist_event_data(book, entry, origin)
        await self._commit([(EVENT_WISHLIST_REMOVED, payload)])
        return dict(book)

    async def got_wishlist_book(
        self, book_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Add a copy of a wishlist book and take it off the wishlist."""
        book = self.book(book_id)
        entry = book.get("wishlist")
        if not entry:
            raise LibraryError("not_on_wishlist")
        record, _ = self._copy_record({**data, "book_id": book_id})
        self._orphan_item(entry)
        book["wishlist"] = None
        self.state["books"][book_id] = book
        self.state["copies"][record["id"]] = record
        fired: list[Event] = [
            (EVENT_COPY_ADDED, events.copy_event_data(book, record, origin)),
            (EVENT_WISHLIST_REMOVED, events.wishlist_event_data(book, entry, origin)),
        ]
        await self._commit(fired)
        return dict(record)

    async def apply_wishlist_plan(self, plan: SyncPlan) -> None:
        """Write the store steps of a wishlist sync plan."""
        fired: list[Event] = []
        books = self.state["books"]
        for bind in plan.binds:
            entry = (books.get(bind.book_id) or {}).get("wishlist")
            if entry:
                entry["todo_entity"] = bind.entity_id
                entry["todo_uid"] = bind.uid
        for bought in plan.bought:
            book = books.get(bought.book_id)
            entry = (book or {}).get("wishlist")
            if book and entry:
                entry["bought"] = True
                entry["buy"] = False
                entry["todo_uid"] = None
                entry["todo_entity"] = None
                book["updated_at"] = now()
                fired.append(
                    (
                        EVENT_BOOK_UPDATED,
                        events.book_updated_event_data(book, ["wishlist"], None),
                    )
                )
        for unbind in plan.unbinds:
            book = books.get(unbind.book_id)
            entry = (book or {}).get("wishlist")
            if book and entry:
                entry["todo_uid"] = None
                entry["todo_entity"] = None
                if unbind.buy_off and entry.get("buy"):
                    entry["buy"] = False
                    book["updated_at"] = now()
                    fired.append(
                        (
                            EVENT_BOOK_UPDATED,
                            events.book_updated_event_data(book, ["wishlist"], None),
                        )
                    )
        dropped = {(d.entity_id, d.uid) for d in plan.drop_orphans}
        if dropped:
            self.state["todo_orphans"] = [
                o
                for o in self.state["todo_orphans"]
                if (o["entity_id"], o["uid"]) not in dropped
            ]
        if not plan.store_changes:
            return
        await self._commit(fired)

    # ── People ───────────────────────────────────────────────────────────────

    async def set_person_settings(
        self, person_id: str, data: dict[str, Any], *, origin: str | None = None
    ) -> dict[str, Any]:
        """Change the library settings of a person."""
        current = models.person_settings(self.state["people"], person_id)
        updated, changed = models.apply_person_settings(current, data)
        if changed:
            self.state["people"][person_id] = updated
            payload = events.person_settings_event_data(person_id, changed, origin)
            await self._commit([(EVENT_PERSON_SETTINGS_UPDATED, payload)])
        return updated

    # ── Import ───────────────────────────────────────────────────────────────

    async def commit_import(
        self,
        new_state: dict[str, Any],
        summary: dict[str, Any],
        *,
        person_id: str | None,
        source: str,
        origin: str | None = None,
    ) -> None:
        """Replace the document with the result of an import.

        The import fires only ``import_completed``, not 1 event for each row.
        """
        self.state = models.normalize_state(new_state)
        payload = events.import_completed_event_data(summary, person_id, source, origin)
        await self._commit([(EVENT_IMPORT_COMPLETED, payload)])
