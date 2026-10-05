"""The ``home_keeper_library.*`` services and the operations behind them.

Each service has 1 handler here, ``async (ctx, data) -> response``. The service
registration and the websocket twin of the service (``websocket_api.py``) both
call the same handler, so the 2 surfaces cannot do different things. The fields
of a service are in :data:`SERVICE_FIELDS`, and the websocket command takes the
same fields.

The gate of each service is in ``api_surface.SERVICES``. An ``admin_only``
service rejects a non-admin user with ``Unauthorized`` before the handler runs.
A ``caller_scoped`` service lets a non-admin user change only their own person,
and its handler checks that. A call with no user (an automation) is trusted.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv

from . import csv_io, models, people, projections
from .api_surface import SERVICES, ServiceSpec
from .backend_i18n import resolve_exception
from .const import (
    CONF_CURRENCY,
    DOMAIN,
    LOOKUP_MAX_TRIES,
    MAX_CSV_BYTES,
    MAX_IMPORT_ROW_RESULTS,
)
from .coordinator import LibraryCoordinator, find_coordinator
from .covers import async_store_openlibrary_cover, async_use_upload
from .isbn import IsbnError
from .isbn import normalize as normalize_isbn
from .models import LibraryError
from .openlibrary_client import OpenLibraryError
from .store import now, today

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ctx:
    """The context of 1 operation: Home Assistant, the coordinator and the caller."""

    hass: HomeAssistant
    coordinator: LibraryCoordinator
    actor: people.Actor

    @property
    def store(self) -> Any:
        """The store."""
        return self.coordinator.store

    def book_reply(self, book: dict[str, Any]) -> dict[str, Any]:
        """A book in a reply, projected for the caller."""
        state = self.store.state
        current = state["books"].get(book["id"], book)
        return projections.project_book(
            state,
            current,
            viewer=self.actor.person_id,
            is_admin=self.actor.is_admin,
        )


Handler = Callable[[Ctx, dict[str, Any]], Awaitable[dict[str, Any]]]

# ── Field schemas ────────────────────────────────────────────────────────────

_OPT_STR = vol.Any(None, cv.string)
_OPT_INT = vol.Any(None, vol.Coerce(int))
_OPT_NUM = vol.Any(None, vol.Coerce(float))
_STR_LIST = vol.All(cv.ensure_list, [cv.string])
_FORMAT = vol.In(models.FORMATS)
_ORDER = vol.All(vol.Coerce(int), vol.Range(min=0))

_BOOK_FIELDS = {
    vol.Optional("title"): cv.string,
    vol.Optional("subtitle"): _OPT_STR,
    vol.Optional("authors"): _STR_LIST,
    vol.Optional("isbn"): _OPT_STR,
    vol.Optional("isbn13"): _OPT_STR,
    vol.Optional("isbn10"): _OPT_STR,
    vol.Optional("publisher"): _OPT_STR,
    vol.Optional("published"): vol.Any(None, cv.string, vol.Coerce(str)),
    vol.Optional("pages"): _OPT_INT,
    vol.Optional("language"): _OPT_STR,
    vol.Optional("subjects"): _STR_LIST,
    vol.Optional("series"): vol.Any(None, cv.string, dict),
    vol.Optional("description"): _OPT_STR,
    vol.Optional("tags"): _STR_LIST,
    vol.Optional("shared_notes"): _OPT_STR,
    vol.Optional("needs_details"): cv.boolean,
}
_COPY_FIELDS = {
    vol.Optional("shelf_id"): _OPT_STR,
    vol.Optional("format"): _FORMAT,
    vol.Optional("condition"): vol.Any(None, vol.In(models.CONDITIONS)),
    vol.Optional("acquired"): _OPT_STR,
    vol.Optional("acquired_from"): _OPT_STR,
    vol.Optional("price"): _OPT_NUM,
    vol.Optional("value"): _OPT_NUM,
    vol.Optional("signed"): cv.boolean,
    vol.Optional("first_edition"): cv.boolean,
    vol.Optional("note"): _OPT_STR,
}
_BOOK_REF = {
    vol.Optional("book_id"): cv.string,
    vol.Optional("isbn"): cv.string,
    vol.Optional("title"): cv.string,
    vol.Optional("authors"): _STR_LIST,
}
_LOAN_FIELDS = {
    vol.Required("party"): cv.string,
    vol.Optional("started"): _OPT_STR,
    vol.Optional("due"): _OPT_STR,
    vol.Optional("note"): _OPT_STR,
    vol.Optional("add_task", default=True): cv.boolean,
}

SERVICE_FIELDS: dict[str, dict[Any, Any]] = {
    "add_room": {
        vol.Required("name"): cv.string,
        vol.Optional("area_id"): _OPT_STR,
        vol.Optional("order"): _ORDER,
    },
    "update_room": {
        vol.Required("room_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("area_id"): _OPT_STR,
        vol.Optional("order"): _ORDER,
    },
    "delete_room": {
        vol.Required("room_id"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    },
    "add_bookcase": {
        vol.Required("room_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("note"): _OPT_STR,
        vol.Optional("order"): _ORDER,
    },
    "update_bookcase": {
        vol.Required("bookcase_id"): cv.string,
        vol.Optional("room_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("note"): _OPT_STR,
        vol.Optional("order"): _ORDER,
    },
    "delete_bookcase": {
        vol.Required("bookcase_id"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    },
    "add_shelf": {
        vol.Required("bookcase_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("order"): _ORDER,
    },
    "update_shelf": {
        vol.Required("shelf_id"): cv.string,
        vol.Optional("bookcase_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("order"): _ORDER,
    },
    "delete_shelf": {
        vol.Required("shelf_id"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    },
    "lookup_isbn": {vol.Required("isbn"): cv.string},
    "add_book": {
        **_BOOK_FIELDS,
        vol.Optional("lookup", default=True): cv.boolean,
    },
    "update_book": {vol.Required("book_id"): cv.string, **_BOOK_FIELDS},
    "delete_book": {vol.Required("book_id"): cv.string},
    "refresh_book": {vol.Required("book_id"): cv.string},
    "scan_isbn": {
        vol.Required("isbn"): cv.string,
        vol.Optional("shelf_id"): _OPT_STR,
        vol.Optional("format"): _FORMAT,
        vol.Optional("on_duplicate", default="ask"): vol.In(
            ("ask", "add_copy", "move", "skip")
        ),
    },
    "add_copy": {vol.Required("book_id"): cv.string, **_COPY_FIELDS},
    "update_copy": {vol.Required("copy_id"): cv.string, **_COPY_FIELDS},
    "move_copy": {
        vol.Required("copy_id"): cv.string,
        vol.Optional("shelf_id"): _OPT_STR,
    },
    "delete_copy": {vol.Required("copy_id"): cv.string},
    "set_cover": {
        vol.Required("book_id"): cv.string,
        vol.Required("kind"): vol.In(models.COVER_KINDS),
        vol.Optional("file_id"): cv.string,
    },
    "set_reading": {
        vol.Required("book_id"): cv.string,
        vol.Optional("person_id"): cv.string,
        vol.Optional("status"): vol.In((*models.STATUSES, models.STATUS_NONE)),
        vol.Optional("rating"): _OPT_INT,
        vol.Optional("page"): _OPT_INT,
        vol.Optional("started"): _OPT_STR,
        vol.Optional("finished"): _OPT_STR,
        vol.Optional("read_count"): vol.Coerce(int),
        vol.Optional("private_notes"): _OPT_STR,
    },
    "lend_book": {vol.Required("copy_id"): cv.string, **_LOAN_FIELDS},
    "borrow_book": {
        **_BOOK_REF,
        **_LOAN_FIELDS,
        vol.Required("person_id"): cv.string,
        vol.Optional("format"): vol.Any(None, _FORMAT),
    },
    "return_loan": {
        vol.Required("loan_id"): cv.string,
        vol.Optional("returned"): _OPT_STR,
    },
    "update_loan": {
        vol.Required("loan_id"): cv.string,
        vol.Optional("party"): cv.string,
        vol.Optional("started"): _OPT_STR,
        vol.Optional("due"): _OPT_STR,
        vol.Optional("note"): _OPT_STR,
        vol.Optional("format"): vol.Any(None, _FORMAT),
    },
    "delete_loan": {vol.Required("loan_id"): cv.string},
    "add_to_wishlist": {
        **_BOOK_REF,
        vol.Required("person_id"): cv.string,
        vol.Optional("buy", default=False): cv.boolean,
    },
    "update_wishlist": {
        vol.Required("book_id"): cv.string,
        vol.Optional("buy"): cv.boolean,
        vol.Optional("person_id"): cv.string,
    },
    "remove_from_wishlist": {vol.Required("book_id"): cv.string},
    "got_wishlist_book": {
        vol.Required("book_id"): cv.string,
        vol.Optional("shelf_id"): _OPT_STR,
        vol.Optional("format"): _FORMAT,
    },
    "set_person_settings": {
        vol.Required("person_id"): cv.string,
        vol.Optional("share_reading"): cv.boolean,
        vol.Optional("yearly_goal"): _OPT_INT,
        vol.Optional("wishlist_todo"): _OPT_STR,
    },
    "set_settings": {vol.Required("currency"): cv.string},
    "import_csv": {
        vol.Required("content"): cv.string,
        vol.Required("source"): vol.In(csv_io.SOURCES),
        vol.Required("person_id"): cv.string,
        vol.Optional("shelf_id"): _OPT_STR,
        vol.Optional("import_notes", default=True): cv.boolean,
        vol.Optional("replace_reading", default=False): cv.boolean,
        vol.Optional("dry_run", default=False): cv.boolean,
    },
    "export_csv": {
        vol.Optional("person_id"): _OPT_STR,
        vol.Optional("format", default="goodreads"): vol.In(csv_io.EXPORT_FORMATS),
    },
    "list_books": {
        vol.Optional("query"): cv.string,
        vol.Optional("room_id"): cv.string,
        vol.Optional("shelf_id"): cv.string,
        vol.Optional("owned"): cv.boolean,
        vol.Optional("status"): vol.In(models.STATUSES),
        vol.Optional("person_id"): cv.string,
        vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    },
    "get_book": {vol.Required("book_id"): cv.string},
    "list_locations": {},
    "list_loans": {
        vol.Optional("status", default="all"): vol.In(("open", "returned", "all")),
        vol.Optional("direction"): vol.In(models.DIRECTIONS),
    },
    "list_people": {},
}


# ── Shared helpers ───────────────────────────────────────────────────────────


def _clean(data: dict[str, Any], *drop: str) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in drop}


def _person_or_error(ctx: Ctx, person_id: str | None) -> str:
    """A known person id, else ``no_person`` or ``person_not_found``."""
    if not person_id:
        raise LibraryError("no_person")
    if people.person(ctx.hass, person_id) is None:
        raise LibraryError("person_not_found", id=person_id)
    return person_id


def _self_or_admin(ctx: Ctx, person_id: str | None) -> str:
    """The person of the call. A non-admin user can only name their own person."""
    target = person_id or ctx.actor.person_id
    if target != ctx.actor.person_id and not ctx.actor.is_admin:
        raise Unauthorized(context=None)
    return _person_or_error(ctx, target)


async def _draft_for_isbn(ctx: Ctx, isbn13: str) -> tuple[dict[str, Any] | None, str]:
    """``(draft, status)``. Status is ``found``, ``not_found`` or ``unavailable``."""
    try:
        draft = await ctx.coordinator.client.async_lookup_isbn(isbn13)
    except OpenLibraryError as err:
        _LOGGER.debug("Open Library lookup of %s failed: %s", isbn13, err)
        return None, "unavailable"
    return (draft, "found") if draft else (None, "not_found")


async def _add_book(
    ctx: Ctx, data: dict[str, Any], *, lookup: bool = True
) -> tuple[dict[str, Any], bool, str]:
    """Add a book. Return ``(book, existing, lookup_status)``.

    With an ISBN, a stored book with that ISBN is returned. Else Open Library
    fills the fields that the call does not send. A failed lookup saves the
    book with ``needs_details: true`` and queues a retry.
    """
    fields = _clean(data, "lookup")
    isbn13 = None
    if fields.get("isbn"):
        try:
            isbn13, _ = normalize_isbn(fields["isbn"])
        except IsbnError as err:
            raise LibraryError("invalid_isbn", isbn=str(fields["isbn"])) from err
        if found := models.find_book_by_isbn(ctx.store.state, isbn13):
            return dict(found), True, "existing"
    elif not fields.get("title"):
        raise LibraryError("isbn_or_title_required")
    status = "manual"
    draft = None
    if lookup and isbn13:
        draft, status = await _draft_for_isbn(ctx, isbn13)
    if draft:
        merged = {k: v for k, v in draft.items() if v not in (None, "", [])}
        merged.update({k: v for k, v in fields.items() if v not in (None, "", [])})
        merged.pop("isbn13", None)
        merged.pop("isbn10", None)
        merged["isbn"] = isbn13
        fields = merged
    elif isbn13 or lookup:
        fields["needs_details"] = True
    if not fields.get("title"):
        fields["title"] = isbn13 or ""
    book, existing = await ctx.store.add_book(fields)
    if not existing:
        if draft:
            try:
                await async_store_openlibrary_cover(
                    ctx.hass, ctx.coordinator, book["id"]
                )
            except OpenLibraryError:
                _LOGGER.debug("No cover for %s", book["id"])
        elif status == "not_found":
            # Open Library does not have the book, so no restart asks again.
            await ctx.store.set_lookup_tries(book["id"], LOOKUP_MAX_TRIES)
        elif book.get("needs_details"):
            ctx.coordinator.lookup.async_enqueue(book["id"])
    return ctx.store.book(book["id"]), existing, status


async def _resolve_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    """The book of ``book_id``, ``isbn`` or ``title``. A new book if none matches."""
    if data.get("book_id"):
        return ctx.store.book(data["book_id"])
    if data.get("isbn"):
        book, _, _ = await _add_book(ctx, {"isbn": data["isbn"]})
        return book
    if data.get("title"):
        key = models.title_key(data["title"], data.get("authors") or [])
        for book in ctx.store.state["books"].values():
            if models.title_key(book.get("title"), book.get("authors")) == key:
                return dict(book)
        book, _, _ = await _add_book(
            ctx, {"title": data["title"], "authors": data.get("authors") or []}
        )
        return book
    raise LibraryError("isbn_or_title_required")


async def _loan_reply(ctx: Ctx, loan_id: str) -> dict[str, Any]:
    """Run the loan task sync, then return the loan as stored."""
    await ctx.coordinator.loan_sync.async_reconcile()
    loan = ctx.store.state["loans"].get(loan_id)
    return {"loan": dict(loan) if loan else None}


# ── Locations ────────────────────────────────────────────────────────────────


async def _add_room(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"room": await ctx.store.add_room(data)}


async def _update_room(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"room": await ctx.store.update_room(data["room_id"], _clean(data))}


async def _delete_room(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    room = await ctx.store.delete_room(data["room_id"], force=data.get("force", False))
    return {"room": room}


async def _add_bookcase(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"bookcase": await ctx.store.add_bookcase(data)}


async def _update_bookcase(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    bookcase = await ctx.store.update_bookcase(data["bookcase_id"], _clean(data))
    return {"bookcase": bookcase}


async def _delete_bookcase(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    bookcase = await ctx.store.delete_bookcase(
        data["bookcase_id"], force=data.get("force", False)
    )
    return {"bookcase": bookcase}


async def _add_shelf(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"shelf": await ctx.store.add_shelf(data)}


async def _update_shelf(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"shelf": await ctx.store.update_shelf(data["shelf_id"], _clean(data))}


async def _delete_shelf(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    shelf = await ctx.store.delete_shelf(
        data["shelf_id"], force=data.get("force", False)
    )
    return {"shelf": shelf}


# ── Books ────────────────────────────────────────────────────────────────────


async def _lookup_isbn(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    try:
        isbn13, isbn10 = normalize_isbn(data["isbn"])
    except IsbnError as err:
        raise LibraryError("invalid_isbn", isbn=data["isbn"]) from err
    existing = models.find_book_by_isbn(ctx.store.state, isbn13)
    draft, status = await _draft_for_isbn(ctx, isbn13)
    return {
        "found": draft is not None,
        "status": status,
        "isbn13": isbn13,
        "isbn10": isbn10,
        "draft": draft,
        "existing_book_id": existing["id"] if existing else None,
    }


async def _add_book_service(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book, existing, status = await _add_book(ctx, data, lookup=data.get("lookup", True))
    return {"book": ctx.book_reply(book), "existing": existing, "lookup": status}


async def _update_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book = await ctx.store.update_book(data["book_id"], _clean(data, "book_id"))
    return {"book": ctx.book_reply(book)}


async def _delete_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book = await ctx.store.delete_book(data["book_id"])
    await ctx.coordinator.loan_sync.async_reconcile()
    return {"book": book}


async def _refresh_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book = ctx.store.book(data["book_id"])
    try:
        draft = await ctx.coordinator.lookup.async_find(book)
    except OpenLibraryError as err:
        raise LibraryError("lookup_unavailable") from err
    if draft is not None:
        await ctx.coordinator.lookup.async_apply(book["id"], draft)
    return {"book": ctx.book_reply(ctx.store.book(book["id"])), "found": bool(draft)}


def _copies_with_location(ctx: Ctx, book_id: str) -> list[dict[str, Any]]:
    state = ctx.store.state
    out = []
    for copy in models.copies_of(state, book_id):
        row = projections.project_copy(copy, is_admin=ctx.actor.is_admin)
        row["location"] = models.location_path(state, copy.get("shelf_id"))
        out.append(row)
    return out


async def _new_copy(ctx: Ctx, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Add a copy. Return ``(copy, from_wishlist)``.

    ``from_wishlist`` is True when the copy took its book off the wishlist.
    """
    book_id = str(data.get("book_id"))
    from_wishlist = models.copy_clears_wishlist(ctx.store.state, book_id)
    copy = await ctx.store.add_copy(data)
    if from_wishlist:
        await ctx.coordinator.wishlist_sync.async_run()
    return copy, from_wishlist


async def _scan_isbn(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    shelf_id = ctx.store.check_shelf(data.get("shelf_id"))
    copy_data: dict[str, Any] = {"shelf_id": shelf_id}
    if data.get("format"):
        copy_data["format"] = data["format"]
    try:
        isbn13, _ = normalize_isbn(data["isbn"])
    except IsbnError as err:
        raise LibraryError("invalid_isbn", isbn=data["isbn"]) from err
    existing = models.find_book_by_isbn(ctx.store.state, isbn13)
    if existing is not None:
        copies = models.copies_of(ctx.store.state, existing["id"])
        mode = data.get("on_duplicate", "ask")
        if copies and mode in ("ask", "skip"):
            return {
                "result": "duplicate" if mode == "ask" else "skipped",
                "book": ctx.book_reply(existing),
                "copy": None,
                "existing_copies": _copies_with_location(ctx, existing["id"]),
                "from_wishlist": False,
            }
        if copies and mode == "move":
            target = next(
                (c for c in copies if c.get("shelf_id") != shelf_id), copies[0]
            )
            moved = await ctx.store.move_copy(target["id"], shelf_id)
            return {
                "result": "moved",
                "book": ctx.book_reply(existing),
                "copy": moved,
                "existing_copies": _copies_with_location(ctx, existing["id"]),
                "from_wishlist": False,
            }
        copy, from_wishlist = await _new_copy(
            ctx, {**copy_data, "book_id": existing["id"]}
        )
        return {
            "result": "added",
            "book": ctx.book_reply(existing),
            "copy": copy,
            "existing_copies": _copies_with_location(ctx, existing["id"]),
            "from_wishlist": from_wishlist,
        }
    book, _, status = await _add_book(ctx, {"isbn": isbn13})
    copy, from_wishlist = await _new_copy(ctx, {**copy_data, "book_id": book["id"]})
    return {
        "result": "added" if status == "found" else "not_found",
        "book": ctx.book_reply(book),
        "copy": copy,
        "existing_copies": [],
        "from_wishlist": from_wishlist,
    }


# ── Copies and covers ────────────────────────────────────────────────────────


async def _add_copy(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    copy, from_wishlist = await _new_copy(ctx, data)
    return {"copy": copy, "from_wishlist": from_wishlist}


async def _update_copy(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    copy = await ctx.store.update_copy(data["copy_id"], _clean(data, "copy_id"))
    return {"copy": copy}


async def _move_copy(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"copy": await ctx.store.move_copy(data["copy_id"], data.get("shelf_id"))}


async def _delete_copy(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {"copy": await ctx.store.delete_copy(data["copy_id"])}


async def _set_cover(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book_id = data["book_id"]
    kind = data["kind"]
    if kind == "custom":
        if not data.get("file_id"):
            raise LibraryError("field_required", field="file_id")
        book = await async_use_upload(
            ctx.hass, ctx.coordinator, book_id, data["file_id"]
        )
    elif kind == "openlibrary":
        ctx.store.book(book_id)
        current = ctx.store.state["books"][book_id]
        if (current.get("cover") or {}).get("kind") == "custom":
            await ctx.store.set_cover(book_id, "none", None)
        try:
            found = await async_store_openlibrary_cover(
                ctx.hass, ctx.coordinator, book_id
            )
        except OpenLibraryError as err:
            raise LibraryError("lookup_unavailable") from err
        if not found:
            raise LibraryError("no_openlibrary_cover")
        book = ctx.store.book(book_id)
    else:
        book = await ctx.store.set_cover(book_id, "none", None)
    return {"book": ctx.book_reply(book)}


# ── Reading ──────────────────────────────────────────────────────────────────


async def _set_reading(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    person_id = _self_or_admin(ctx, data.get("person_id"))
    row = await ctx.store.set_reading(
        data["book_id"], person_id, _clean(data, "book_id", "person_id")
    )
    return {"book_id": data["book_id"], "person_id": person_id, "reading": row}


# ── Loans ────────────────────────────────────────────────────────────────────


async def _lend_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    loan = await ctx.store.add_loan({**data, "direction": "out"})
    return await _loan_reply(ctx, loan["id"])


async def _borrow_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    person_id = _person_or_error(ctx, data["person_id"])
    if not data.get("party"):
        raise LibraryError("field_required", field="party")
    book = await _resolve_book(ctx, data)
    loan = await ctx.store.add_loan(
        {
            **_clean(data, "book_id", "isbn", "title", "authors"),
            "direction": "in",
            "book_id": book["id"],
            "person_id": person_id,
        }
    )
    reply = await _loan_reply(ctx, loan["id"])
    reply["book"] = ctx.book_reply(book)
    return reply


async def _return_loan(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    loan = await ctx.store.return_loan(data["loan_id"], data.get("returned"))
    return await _loan_reply(ctx, loan["id"])


async def _update_loan(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    loan = await ctx.store.update_loan(data["loan_id"], _clean(data, "loan_id"))
    return await _loan_reply(ctx, loan["id"])


async def _delete_loan(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    loan = await ctx.store.delete_loan(data["loan_id"])
    await ctx.coordinator.loan_sync.async_reconcile()
    return {"loan": loan}


# ── Wishlist ─────────────────────────────────────────────────────────────────


async def _add_to_wishlist(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    person_id = _person_or_error(ctx, data["person_id"])
    book = await _resolve_book(ctx, data)
    book = await ctx.store.add_to_wishlist(
        book["id"], person_id, buy=data.get("buy", False)
    )
    await ctx.coordinator.wishlist_sync.async_run()
    return {"book": ctx.book_reply(book)}


async def _update_wishlist(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    if "person_id" in data:
        _person_or_error(ctx, data["person_id"])
    book = await ctx.store.update_wishlist(data["book_id"], _clean(data, "book_id"))
    await ctx.coordinator.wishlist_sync.async_run()
    return {"book": ctx.book_reply(book)}


async def _remove_from_wishlist(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    book = await ctx.store.remove_from_wishlist(data["book_id"])
    await ctx.coordinator.wishlist_sync.async_run()
    return {"book": ctx.book_reply(book)}


async def _got_wishlist_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    copy = await ctx.store.got_wishlist_book(data["book_id"], _clean(data, "book_id"))
    await ctx.coordinator.wishlist_sync.async_run()
    return {"copy": copy}


# ── People ───────────────────────────────────────────────────────────────────


async def _set_person_settings(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    person_id = data["person_id"]
    if not ctx.actor.is_admin and (
        person_id != ctx.actor.person_id or "wishlist_todo" in data
    ):
        raise Unauthorized(context=None)
    _person_or_error(ctx, person_id)
    entity_id = data.get("wishlist_todo")
    if entity_id and (
        not entity_id.startswith("todo.") or ctx.hass.states.get(entity_id) is None
    ):
        raise LibraryError("todo_entity_not_found", entity_id=entity_id)
    settings = await ctx.store.set_person_settings(person_id, _clean(data, "person_id"))
    if "wishlist_todo" in data:
        await ctx.coordinator.wishlist_sync.async_run()
    return {"person_id": person_id, "settings": settings}


async def _set_settings(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    currency = str(data["currency"]).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise LibraryError("invalid_currency", currency=data["currency"])
    entry = ctx.coordinator.entry
    ctx.hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_CURRENCY: currency}
    )
    # The store fires settings_updated, and the tab and the card read the
    # currency from get_state again.
    ctx.coordinator.async_check_settings()
    return {"currency": currency}


# ── Import and export ────────────────────────────────────────────────────────


async def _import_csv(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    content = data["content"]
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise LibraryError("csv_too_large", mb=MAX_CSV_BYTES // (1024 * 1024))
    person_id = _person_or_error(ctx, data["person_id"])
    shelf_id = ctx.store.check_shelf(data.get("shelf_id"))
    rows = csv_io.parse(content, data["source"])
    snapshot = models.clone(ctx.store.state)
    new_state, counts, results, lookup_ids = await ctx.hass.async_add_executor_job(
        lambda: csv_io.apply_import(
            snapshot,
            rows,
            person_id=person_id,
            shelf_id=shelf_id,
            import_notes=data.get("import_notes", True),
            replace_reading=data.get("replace_reading", False),
            now=now(),
        )
    )
    dry_run = data.get("dry_run", False)
    summary = csv_io.summary_of(counts, counts["reading_kept"])
    if not dry_run:
        await ctx.store.commit_import(
            new_state, summary, person_id=person_id, source=data["source"]
        )
        for book_id in lookup_ids:
            ctx.coordinator.lookup.async_enqueue(book_id)
    lang = ctx.hass.config.language
    shown = []
    for result in results[:MAX_IMPORT_ROW_RESULTS]:
        row = {k: v for k, v in result.items() if k not in ("error", "placeholders")}
        row["message"] = (
            resolve_exception(lang, result["error"], **result["placeholders"])
            if "error" in result
            else ""
        )
        shown.append(row)
    return {
        "dry_run": dry_run,
        "counts": {key: counts[key] for key in csv_io.COUNT_KEYS},
        "rows": shown,
        "truncated": len(results) > MAX_IMPORT_ROW_RESULTS,
    }


async def _export_csv(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    person_id = data.get("person_id") or None
    if person_id:
        _person_or_error(ctx, person_id)
    fmt = data.get("format", "goodreads")
    content = csv_io.export(ctx.store.state, person_id, fmt)
    return {"filename": csv_io.export_filename(fmt, today()), "content": content}


# ── Reads ────────────────────────────────────────────────────────────────────


async def _list_books(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    filters = dict(data)
    if filters.get("status"):
        person_id = filters.get("person_id") or ctx.actor.person_id
        filters["person_id"] = person_id
        shared = models.person_settings(ctx.store.state["people"], str(person_id))
        if (
            not ctx.actor.is_admin
            and person_id != ctx.actor.person_id
            and not shared["share_reading"]
        ):
            return {"books": []}
    return {
        "books": projections.list_books(
            ctx.store.state,
            filters,
            viewer=ctx.actor.person_id,
            is_admin=ctx.actor.is_admin,
        )
    }


async def _get_book(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    detail = projections.book_detail(
        ctx.store.state,
        data["book_id"],
        viewer=ctx.actor.person_id,
        is_admin=ctx.actor.is_admin,
    )
    if detail is None:
        raise LibraryError("book_not_found", id=data["book_id"])
    return {"book": detail}


async def _list_locations(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    state = ctx.store.state
    counts: dict[str | None, int] = {}
    for copy in state["copies"].values():
        counts[copy.get("shelf_id")] = counts.get(copy.get("shelf_id"), 0) + 1
    rooms = []
    for room in sorted(state["rooms"].values(), key=lambda r: (r["order"], r["name"])):
        bookcases = []
        for bookcase in sorted(
            (b for b in state["bookcases"].values() if b["room_id"] == room["id"]),
            key=lambda b: (b["order"], b["name"]),
        ):
            shelves = [
                {**shelf, "copies": counts.get(shelf["id"], 0)}
                for shelf in sorted(
                    (
                        s
                        for s in state["shelves"].values()
                        if s["bookcase_id"] == bookcase["id"]
                    ),
                    key=lambda s: (s["order"], s["name"]),
                )
            ]
            bookcases.append({**bookcase, "shelves": shelves})
        rooms.append({**room, "bookcases": bookcases})
    return {"rooms": rooms, "no_shelf": counts.get(None, 0)}


async def _list_loans(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    state = ctx.store.state
    wanted = data.get("status", "all")
    out = []
    for loan in sorted(state["loans"].values(), key=lambda lo: lo["started"]):
        is_open = models.is_open(loan)
        if (wanted == "open" and not is_open) or (wanted == "returned" and is_open):
            continue
        if data.get("direction") and loan["direction"] != data["direction"]:
            continue
        row = projections.project_loan(loan, is_admin=ctx.actor.is_admin)
        row["title"] = (state["books"].get(loan["book_id"]) or {}).get("title", "")
        row["overdue"] = models.is_overdue(loan, today())
        out.append(row)
    return {"loans": out}


async def _list_people(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "people": projections.project_people(
            ctx.store.state,
            people.persons(ctx.hass),
            viewer=ctx.actor.person_id,
            is_admin=ctx.actor.is_admin,
        )
    }


SERVICE_HANDLERS: dict[str, Handler] = {
    "add_room": _add_room,
    "update_room": _update_room,
    "delete_room": _delete_room,
    "add_bookcase": _add_bookcase,
    "update_bookcase": _update_bookcase,
    "delete_bookcase": _delete_bookcase,
    "add_shelf": _add_shelf,
    "update_shelf": _update_shelf,
    "delete_shelf": _delete_shelf,
    "lookup_isbn": _lookup_isbn,
    "add_book": _add_book_service,
    "update_book": _update_book,
    "delete_book": _delete_book,
    "refresh_book": _refresh_book,
    "scan_isbn": _scan_isbn,
    "add_copy": _add_copy,
    "update_copy": _update_copy,
    "move_copy": _move_copy,
    "delete_copy": _delete_copy,
    "set_cover": _set_cover,
    "set_reading": _set_reading,
    "lend_book": _lend_book,
    "borrow_book": _borrow_book,
    "return_loan": _return_loan,
    "update_loan": _update_loan,
    "delete_loan": _delete_loan,
    "add_to_wishlist": _add_to_wishlist,
    "update_wishlist": _update_wishlist,
    "remove_from_wishlist": _remove_from_wishlist,
    "got_wishlist_book": _got_wishlist_book,
    "set_person_settings": _set_person_settings,
    "set_settings": _set_settings,
    "import_csv": _import_csv,
    "export_csv": _export_csv,
    "list_books": _list_books,
    "get_book": _get_book,
    "list_locations": _list_locations,
    "list_loans": _list_loans,
    "list_people": _list_people,
}

_RESPONSES = {
    "none": SupportsResponse.NONE,
    "optional": SupportsResponse.OPTIONAL,
    "only": SupportsResponse.ONLY,
}


def coordinator_or_error(hass: HomeAssistant) -> LibraryCoordinator:
    """The loaded coordinator, or the localized ``not_loaded`` error."""
    coordinator = find_coordinator(hass)
    if coordinator is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_loaded"
        )
    return coordinator


async def async_run(
    hass: HomeAssistant, spec: ServiceSpec, actor: people.Actor, data: dict[str, Any]
) -> dict[str, Any]:
    """Run 1 operation for *actor*, with the gate of *spec*.

    Raise ``Unauthorized`` for a refused caller, and :class:`LibraryError` for
    input that the library refuses.
    """
    if spec.admin_only and not actor.is_admin:
        raise Unauthorized(context=None)
    coordinator = coordinator_or_error(hass)
    ctx = Ctx(hass, coordinator, actor)
    return await SERVICE_HANDLERS[spec.name](ctx, data)


def _service_handler(
    hass: HomeAssistant, spec: ServiceSpec
) -> Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]:
    async def handle(call: ServiceCall) -> ServiceResponse:
        actor = await people.actor_for_call(hass, call)
        try:
            result = await async_run(hass, spec, actor, dict(call.data))
        except Unauthorized as err:
            raise Unauthorized(context=call.context) from err
        except LibraryError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=err.key,
                translation_placeholders=err.placeholders,
            ) from err
        return result if call.return_response else None

    return handle


def async_register_services(hass: HomeAssistant) -> None:
    """Register each service of ``api_surface.SERVICES``."""
    for spec in SERVICES:
        hass.services.async_register(
            DOMAIN,
            spec.name,
            _service_handler(hass, spec),
            schema=vol.Schema(SERVICE_FIELDS[spec.name]),
            supports_response=_RESPONSES[spec.response],
        )
