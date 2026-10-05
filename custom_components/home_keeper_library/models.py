"""Pure data model of the library: normalize and build the stored records.

The store holds one JSON document with these sections, each a map by id::

    rooms, bookcases, shelves, books, copies, loans
    reading:  {person_id: {book_id: row}}
    people:   {person_id: settings}
    todo_orphans: [{entity_id, uid}]

A record is a plain dict. The functions here check caller input and return new
dicts. They never change their arguments, and they never read a clock: the caller
passes ``now`` (an aware ISO 8601 timestamp) and ``today`` (a ``YYYY-MM-DD``
date). A bad value raises :class:`LibraryError` with a translation key from
``strings.json`` ``exceptions``. The service layer turns it into a localized error.

This module imports no Home Assistant code.
"""

from __future__ import annotations

import copy as _copy
import math
import re
import unicodedata
import uuid
from datetime import date
from typing import Any

from . import isbn as isbn_mod

STATE_SECTIONS = (
    "rooms",
    "bookcases",
    "shelves",
    "books",
    "copies",
    "reading",
    "loans",
    "people",
)

FORMATS = ("hardcover", "paperback", "ebook", "audiobook", "other")
DEFAULT_FORMAT = "paperback"
CONDITIONS = ("new", "fine", "good", "fair", "poor")
STATUSES = ("want", "reading", "read", "dnf")
# The ``status`` value of ``set_reading`` that removes the reading row.
STATUS_NONE = "none"
DIRECTIONS = ("out", "in")
COVER_KINDS = ("openlibrary", "custom", "none")

MAX_NAME = 100
MAX_TITLE = 500
MAX_SHORT = 200
MAX_NOTE = 2000
MAX_LONG = 20000
MAX_LIST = 50
MAX_ORDER = 1_000_000
MAX_PAGES = 100_000
MAX_READ_COUNT = 1000
MAX_GOAL = 10_000
MAX_MONEY = 1_000_000_000

# The book fields that a caller sets. ``wishlist``, ``cover`` and the time stamps
# have their own paths.
BOOK_TEXT_FIELDS = {
    "title": MAX_TITLE,
    "subtitle": MAX_TITLE,
    "publisher": MAX_SHORT,
    "published": 50,
    "description": MAX_LONG,
    "shared_notes": MAX_LONG,
}
BOOK_FIELDS = (
    "title",
    "subtitle",
    "authors",
    "isbn13",
    "isbn10",
    "publisher",
    "published",
    "pages",
    "language",
    "subjects",
    "series",
    "description",
    "tags",
    "shared_notes",
    "openlibrary",
    "needs_details",
)
# The fields that ``fill_from_draft`` can write. A user edit of a field is kept.
DRAFT_FIELDS = (
    "title",
    "subtitle",
    "authors",
    "isbn13",
    "isbn10",
    "publisher",
    "published",
    "pages",
    "language",
    "subjects",
    "series",
    "description",
)
COPY_FIELDS = (
    "shelf_id",
    "format",
    "condition",
    "acquired",
    "acquired_from",
    "price",
    "value",
    "signed",
    "first_edition",
    "note",
)
READING_FIELDS = (
    "status",
    "rating",
    "page",
    "started",
    "finished",
    "read_count",
    "private_notes",
)
LOAN_UPDATE_FIELDS = ("party", "due", "note", "started", "format")
PERSON_FIELDS = ("share_reading", "wishlist_todo", "yearly_goal")


class LibraryError(ValueError):
    """Input that the library refuses.

    ``key`` is a key in ``strings.json`` ``exceptions``, and ``placeholders``
    fill its message.
    """

    def __init__(self, key: str, **placeholders: Any) -> None:
        super().__init__(key)
        self.key = key
        self.placeholders = {name: str(value) for name, value in placeholders.items()}


def new_id() -> str:
    """A new record id: a uuid4 hex string."""
    return uuid.uuid4().hex


def empty_state() -> dict[str, Any]:
    """The document of a new library."""
    state: dict[str, Any] = {name: {} for name in STATE_SECTIONS}
    state["todo_orphans"] = []
    return state


def normalize_state(raw: Any) -> dict[str, Any]:
    """Return a document with every section, from a stored or a missing one.

    A section that is absent or has the wrong type becomes empty. This is also the
    place for a storage migration: the store calls it on every load.
    """
    state = empty_state()
    if not isinstance(raw, dict):
        return state
    for name in STATE_SECTIONS:
        value = raw.get(name)
        if isinstance(value, dict):
            state[name] = value
    orphans = raw.get("todo_orphans")
    if isinstance(orphans, list):
        state["todo_orphans"] = [
            entry
            for entry in orphans
            if isinstance(entry, dict)
            and isinstance(entry.get("entity_id"), str)
            and isinstance(entry.get("uid"), str)
        ]
    return state


def clone(value: Any) -> Any:
    """A deep copy of a JSON value."""
    return _copy.deepcopy(value)


# ── Field checks ─────────────────────────────────────────────────────────────


def text(value: Any, field: str, max_len: int, *, required: bool = False) -> str:
    """A trimmed string of at most *max_len* characters."""
    if value is None:
        value = ""
    if isinstance(value, int | float) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise LibraryError("invalid_field", field=field)
    value = value.strip()
    if required and not value:
        raise LibraryError("field_required", field=field)
    if len(value) > max_len:
        raise LibraryError("field_too_long", field=field, max=max_len)
    return value


def optional_text(value: Any, field: str, max_len: int) -> str | None:
    """Like :func:`text`, but an empty value is None."""
    result = text(value, field, max_len)
    return result or None


def str_list(value: Any, field: str, *, max_len: int = MAX_SHORT) -> list[str]:
    """A list of distinct, trimmed, non-empty strings, in input order."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list | tuple):
        raise LibraryError("invalid_field", field=field)
    out: list[str] = []
    for item in value:
        entry = text(item, field, max_len)
        if entry and entry not in out:
            out.append(entry)
    if len(out) > MAX_LIST:
        raise LibraryError("field_too_long", field=field, max=MAX_LIST)
    return out


def boolean(value: Any, field: str) -> bool:
    """A bool. Strings and numbers are refused."""
    if not isinstance(value, bool):
        raise LibraryError("invalid_field", field=field)
    return value


def integer(
    value: Any, field: str, *, low: int, high: int, nullable: bool = True
) -> int | None:
    """An int from *low* to *high*, or None if *nullable* and the value is None."""
    if value is None or value == "":
        if nullable:
            return None
        raise LibraryError("field_required", field=field)
    if isinstance(value, bool):
        raise LibraryError("invalid_field", field=field)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value.strip())
    if not isinstance(value, int):
        raise LibraryError("invalid_field", field=field)
    if not low <= value <= high:
        raise LibraryError("out_of_range", field=field, low=low, high=high)
    return value


def money(value: Any, field: str) -> float | int | None:
    """A number from 0 up, or None. A whole value stays an int."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise LibraryError("invalid_field", field=field)
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError as err:
            raise LibraryError("invalid_field", field=field) from err
    if not isinstance(value, int | float) or not math.isfinite(value):
        raise LibraryError("invalid_field", field=field)
    if not 0 <= value <= MAX_MONEY:
        raise LibraryError("out_of_range", field=field, low=0, high=MAX_MONEY)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def iso_date(value: Any, field: str) -> str | None:
    """A ``YYYY-MM-DD`` string from a date or a string, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()[:10]
    if isinstance(value, str):
        candidate = value.strip()[:10]
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError as err:
            raise LibraryError("invalid_date", field=field) from err
    raise LibraryError("invalid_date", field=field)


def choice(value: Any, field: str, options: tuple[str, ...]) -> str:
    """One of *options*."""
    if value not in options:
        raise LibraryError("invalid_choice", field=field, options=", ".join(options))
    return str(value)


def entity_id_or_none(value: Any, field: str, domain: str) -> str | None:
    """A ``<domain>.<object_id>`` entity id, or None."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(
        rf"{re.escape(domain)}\.[a-z0-9_]+", value
    ):
        raise LibraryError("invalid_field", field=field)
    return value


# ── Locations ────────────────────────────────────────────────────────────────


def build_room(data: dict[str, Any], *, order: int) -> dict[str, Any]:
    """A new room."""
    return {
        "id": new_id(),
        "name": text(data.get("name"), "name", MAX_NAME, required=True),
        "area_id": optional_text(data.get("area_id"), "area_id", MAX_SHORT),
        "order": _order(data.get("order", order)),
    }


def build_bookcase(data: dict[str, Any], *, order: int) -> dict[str, Any]:
    """A new bookcase. The caller checks that ``room_id`` exists."""
    return {
        "id": new_id(),
        "room_id": text(data.get("room_id"), "room_id", MAX_SHORT, required=True),
        "name": text(data.get("name"), "name", MAX_NAME, required=True),
        "note": text(data.get("note"), "note", MAX_NOTE),
        "order": _order(data.get("order", order)),
    }


def build_shelf(data: dict[str, Any], *, order: int) -> dict[str, Any]:
    """A new shelf. The caller checks that ``bookcase_id`` exists."""
    return {
        "id": new_id(),
        "bookcase_id": text(
            data.get("bookcase_id"), "bookcase_id", MAX_SHORT, required=True
        ),
        "name": text(data.get("name"), "name", MAX_NAME, required=True),
        "order": _order(data.get("order", order)),
    }


def _order(value: Any) -> int:
    result = integer(value, "order", low=0, high=MAX_ORDER, nullable=False)
    assert result is not None
    return result


_LOCATION_RULES: dict[str, dict[str, Any]] = {
    "room": {"name": ("name",), "area_id": ("area_id",), "order": ("order",)},
    "bookcase": {
        "name": ("name",),
        "note": ("note",),
        "order": ("order",),
        "room_id": ("room_id",),
    },
    "shelf": {"name": ("name",), "order": ("order",), "bookcase_id": ("bookcase_id",)},
}


def update_location(
    kind: str, record: dict[str, Any], data: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(updated, changed_fields)`` for a room, a bookcase or a shelf."""
    updated = dict(record)
    changed: list[str] = []
    for field in _LOCATION_RULES[kind]:
        if field not in data:
            continue
        raw = data[field]
        if field == "name":
            value: Any = text(raw, field, MAX_NAME, required=True)
        elif field == "order":
            value = _order(raw)
        elif field == "note":
            value = text(raw, field, MAX_NOTE)
        elif field == "area_id":
            value = optional_text(raw, field, MAX_SHORT)
        else:
            value = text(raw, field, MAX_SHORT, required=True)
        if value != updated.get(field):
            updated[field] = value
            changed.append(field)
    return updated, changed


def next_order(records: dict[str, dict[str, Any]], **match: Any) -> int:
    """The order after the last record whose fields equal *match*."""
    orders = [
        int(record.get("order", 0))
        for record in records.values()
        if all(record.get(key) == value for key, value in match.items())
    ]
    return max(orders) + 1 if orders else 0


# ── Books ────────────────────────────────────────────────────────────────────


def _series(value: Any) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = {"name": value}
    if not isinstance(value, dict):
        raise LibraryError("invalid_field", field="series")
    name = text(value.get("name"), "series", MAX_SHORT)
    if not name:
        return None
    number = value.get("number")
    if number is not None and number != "":
        if isinstance(number, bool) or not isinstance(number, int | float | str):
            raise LibraryError("invalid_field", field="series")
        number = text(number, "series", 20) or None
    else:
        number = None
    return {"name": name, "number": number}


def _openlibrary(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise LibraryError("invalid_field", field="openlibrary")
    cover_id = value.get("cover_id")
    if cover_id is not None:
        cover_id = integer(cover_id, "openlibrary", low=1, high=2**53)
    out = {
        "edition_key": optional_text(value.get("edition_key"), "openlibrary", 50),
        "work_key": optional_text(value.get("work_key"), "openlibrary", 50),
        "cover_id": cover_id,
    }
    return out if any(v is not None for v in out.values()) else None


def book_field(field: str, value: Any) -> Any:
    """Check one caller-set book field and return its stored value."""
    if field in BOOK_TEXT_FIELDS:
        return text(value, field, BOOK_TEXT_FIELDS[field], required=field == "title")
    if field in ("authors", "subjects", "tags"):
        return str_list(value, field)
    if field == "isbn13":
        if value in (None, ""):
            return None
        isbn13, _ = _isbn(value)
        return isbn13
    if field == "isbn10":
        if value in (None, ""):
            return None
        value = isbn_mod.clean(value)
        if not isbn_mod.is_valid_isbn10(value):
            raise LibraryError("invalid_isbn", isbn=value)
        return value
    if field == "pages":
        return integer(value, field, low=1, high=MAX_PAGES)
    if field == "language":
        return optional_text(value, field, 20)
    if field == "series":
        return _series(value)
    if field == "openlibrary":
        return _openlibrary(value)
    if field == "needs_details":
        return boolean(value, field)
    raise LibraryError("invalid_field", field=field)


def _isbn(value: Any) -> tuple[str, str | None]:
    try:
        return isbn_mod.normalize(value)
    except isbn_mod.IsbnError as err:
        raise LibraryError("invalid_isbn", isbn=isbn_mod.clean(value)) from err


def build_book(data: dict[str, Any], *, now: str) -> dict[str, Any]:
    """A new book from caller input.

    ``isbn`` is a convenience field: an ISBN-10 or an ISBN-13 that fills both
    ``isbn13`` and ``isbn10``.
    """
    book: dict[str, Any] = {
        "id": new_id(),
        "title": "",
        "subtitle": "",
        "authors": [],
        "isbn13": None,
        "isbn10": None,
        "publisher": "",
        "published": "",
        "pages": None,
        "language": None,
        "subjects": [],
        "series": None,
        "description": "",
        "tags": [],
        "shared_notes": "",
        "openlibrary": None,
        "cover": {"kind": "none", "file": None},
        "needs_details": False,
        "created_at": now,
        "updated_at": now,
        "wishlist": None,
    }
    for field in BOOK_FIELDS:
        if field in data:
            book[field] = book_field(field, data[field])
    if data.get("isbn") not in (None, ""):
        book["isbn13"], book["isbn10"] = _isbn(data["isbn"])
    elif book["isbn13"] and not book["isbn10"]:
        book["isbn10"] = isbn_mod.to_isbn10(book["isbn13"])
    elif book["isbn10"] and not book["isbn13"]:
        book["isbn13"] = isbn_mod.to_isbn13(book["isbn10"])
    if not book["title"]:
        raise LibraryError("field_required", field="title")
    return book


def update_book(
    book: dict[str, Any], data: dict[str, Any], *, now: str
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(updated, changed_fields)``. ``updated_at`` moves on a change."""
    updated = dict(book)
    changed: list[str] = []
    patch = {field: data[field] for field in BOOK_FIELDS if field in data}
    if data.get("isbn") not in (None, ""):
        patch["isbn13"], patch["isbn10"] = _isbn(data["isbn"])
    for field, raw in patch.items():
        value = book_field(field, raw)
        if value != updated.get(field):
            updated[field] = value
            changed.append(field)
    if changed:
        updated["updated_at"] = now
    return updated, changed


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def fill_from_draft(
    book: dict[str, Any], draft: dict[str, Any], *, now: str
) -> tuple[dict[str, Any], list[str]]:
    """Fill the empty fields of *book* from an Open Library *draft*.

    A field that has a value is a user edit and stays. The ``openlibrary`` keys
    are always taken from the draft, and ``needs_details`` turns off.
    """
    updated = dict(book)
    changed: list[str] = []
    for field in DRAFT_FIELDS:
        if field not in draft or _is_empty(draft[field]):
            continue
        if not _is_empty(updated.get(field)):
            continue
        try:
            value = book_field(field, draft[field])
        except LibraryError:
            continue
        updated[field] = value
        changed.append(field)
    if draft.get("openlibrary"):
        value = _openlibrary(draft["openlibrary"])
        if value != updated.get("openlibrary"):
            updated["openlibrary"] = value
            changed.append("openlibrary")
    if updated.get("needs_details"):
        updated["needs_details"] = False
        changed.append("needs_details")
    if changed:
        updated["updated_at"] = now
    return updated, changed


SUMMARY_TEMPLATE = "{title} by {author}"


def book_summary(book: dict[str, Any], template: str = SUMMARY_TEMPLATE) -> str:
    """``Title by Author``, or the title alone if the book has no author.

    *template* is the ``item.summary`` backend string in the language of Home
    Assistant.
    """
    authors = book.get("authors") or []
    title = str(book.get("title") or "")
    if not authors:
        return title
    return template.replace("{title}", title).replace("{author}", str(authors[0]))


def fold(value: Any) -> str:
    """A key for loose text comparison: no accents, case or punctuation."""
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    words = re.findall(r"[^\W_]+", plain.casefold())
    return " ".join(words)


def title_key(title: Any, authors: Any) -> str:
    """The match key of a title and its first author.

    A subtitle after ``:`` is ignored, and the author is reduced to the last word
    of the name, so ``Le Guin, Ursula K.`` and ``Ursula K. Le Guin`` can match.
    """
    raw = str(title or "").split(":", 1)[0]
    first = ""
    if isinstance(authors, list | tuple) and authors:
        first = str(authors[0])
    elif isinstance(authors, str):
        first = authors
    if "," in first:
        first = first.split(",", 1)[0]
    else:
        parts = fold(first).split(" ")
        first = parts[-1] if parts else ""
    return f"{fold(raw)}|{fold(first)}"


# ── Copies ───────────────────────────────────────────────────────────────────


def copy_field(field: str, value: Any) -> Any:
    """Check one caller-set copy field and return its stored value."""
    if field == "shelf_id":
        return optional_text(value, field, MAX_SHORT)
    if field == "format":
        return choice(value, field, FORMATS)
    if field == "condition":
        return None if value in (None, "") else choice(value, field, CONDITIONS)
    if field == "acquired":
        return iso_date(value, field)
    if field == "acquired_from":
        return text(value, field, MAX_SHORT)
    if field in ("price", "value"):
        return money(value, field)
    if field in ("signed", "first_edition"):
        return boolean(value, field)
    if field == "note":
        return text(value, field, MAX_NOTE)
    raise LibraryError("invalid_field", field=field)


def build_copy(data: dict[str, Any], *, now: str) -> dict[str, Any]:
    """A new copy. The caller checks that the book and the shelf exist."""
    record: dict[str, Any] = {
        "id": new_id(),
        "book_id": text(data.get("book_id"), "book_id", MAX_SHORT, required=True),
        "shelf_id": None,
        "format": DEFAULT_FORMAT,
        "condition": None,
        "acquired": None,
        "acquired_from": "",
        "price": None,
        "value": None,
        "signed": False,
        "first_edition": False,
        "note": "",
        "created_at": now,
    }
    for field in COPY_FIELDS:
        if field in data:
            record[field] = copy_field(field, data[field])
    return record


def update_copy(
    record: dict[str, Any], data: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(updated, changed_fields)`` for a copy."""
    updated = dict(record)
    changed: list[str] = []
    for field in COPY_FIELDS:
        if field not in data:
            continue
        value = copy_field(field, data[field])
        if value != updated.get(field):
            updated[field] = value
            changed.append(field)
    return updated, changed


def format_from_binding(binding: Any) -> str:
    """The copy format for a Goodreads ``Binding`` or a StoryGraph ``Format``."""
    value = fold(binding)
    if not value:
        return "other"
    if "audio" in value or "audible" in value:
        return "audiobook"
    if "kindle" in value or "ebook" in value or "digital" in value:
        return "ebook"
    if "hardcover" in value or "hardback" in value:
        return "hardcover"
    if "paperback" in value or "paper back" in value:
        return "paperback"
    return "other"


# ── Reading ──────────────────────────────────────────────────────────────────


def empty_reading(*, now: str) -> dict[str, Any]:
    """A reading row with status ``want``."""
    return {
        "status": "want",
        "rating": None,
        "page": None,
        "started": None,
        "finished": None,
        "read_count": 0,
        "private_notes": "",
        "updated_at": now,
    }


def reading_field(field: str, value: Any) -> Any:
    """Check one reading field and return its stored value."""
    if field == "status":
        return choice(value, field, STATUSES)
    if field == "rating":
        return integer(value, field, low=1, high=5)
    if field == "page":
        return integer(value, field, low=0, high=MAX_PAGES)
    if field in ("started", "finished"):
        return iso_date(value, field)
    if field == "read_count":
        return integer(value, field, low=0, high=MAX_READ_COUNT, nullable=False)
    if field == "private_notes":
        return text(value, field, MAX_LONG)
    raise LibraryError("invalid_field", field=field)


def apply_reading(
    row: dict[str, Any] | None, data: dict[str, Any], *, now: str, today: str
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(row, changed_fields)`` after a ``set_reading`` call.

    When the status becomes ``read``, ``finished`` is today and ``read_count``
    goes up by 1, unless the call sends those fields. When the status becomes
    ``reading``, ``started`` is today unless the call sends it.
    """
    base = dict(row) if row else empty_reading(now=now)
    previous = row.get("status") if row else None
    updated = dict(base)
    for field in READING_FIELDS:
        if field in data:
            updated[field] = reading_field(field, data[field])
    status = updated["status"]
    if status != previous:
        if status == "read":
            if "finished" not in data:
                updated["finished"] = today
            if "read_count" not in data:
                updated["read_count"] = int(base.get("read_count") or 0) + 1
        elif status == "reading" and "started" not in data:
            updated["started"] = today
    changed = [
        field for field in READING_FIELDS if updated.get(field) != base.get(field)
    ]
    if row is None and "status" not in changed:
        changed.insert(0, "status")
    if changed:
        updated["updated_at"] = now
    return updated, changed


# ── Loans ────────────────────────────────────────────────────────────────────


def build_loan(data: dict[str, Any], *, today: str) -> dict[str, Any]:
    """A new loan. The caller checks the book, the copy and the person."""
    direction = choice(data.get("direction"), "direction", DIRECTIONS)
    started = iso_date(data.get("started"), "started") or today
    due = iso_date(data.get("due"), "due")
    if due is not None and due < started:
        raise LibraryError("due_before_start")
    copy_id = optional_text(data.get("copy_id"), "copy_id", MAX_SHORT)
    person_id = optional_text(data.get("person_id"), "person_id", MAX_SHORT)
    if direction == "out" and copy_id is None:
        raise LibraryError("field_required", field="copy_id")
    if direction == "in":
        copy_id = None
        if person_id is None:
            raise LibraryError("field_required", field="person_id")
    fmt = data.get("format")
    return {
        "id": new_id(),
        "direction": direction,
        "book_id": text(data.get("book_id"), "book_id", MAX_SHORT, required=True),
        "copy_id": copy_id,
        "party": text(data.get("party"), "party", MAX_SHORT, required=True),
        "person_id": person_id,
        "format": None if fmt in (None, "") else choice(fmt, "format", FORMATS),
        "started": started,
        "due": due,
        "returned": None,
        "note": text(data.get("note"), "note", MAX_NOTE),
        "hk_task_id": None,
        "add_task": bool(data.get("add_task", True)),
        "overdue_fired": False,
    }


def update_loan(
    loan: dict[str, Any], data: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(updated, changed_fields)``. A new due date can fire again."""
    updated = dict(loan)
    changed: list[str] = []
    for field in LOAN_UPDATE_FIELDS:
        if field not in data:
            continue
        raw = data[field]
        if field == "party":
            value: Any = text(raw, field, MAX_SHORT, required=True)
        elif field == "note":
            value = text(raw, field, MAX_NOTE)
        elif field == "format":
            value = None if raw in (None, "") else choice(raw, field, FORMATS)
        elif field == "started":
            value = iso_date(raw, field) or loan["started"]
        else:
            value = iso_date(raw, field)
        if value != updated.get(field):
            updated[field] = value
            changed.append(field)
    if updated.get("due") is not None and updated["due"] < updated["started"]:
        raise LibraryError("due_before_start")
    if "due" in changed:
        updated["overdue_fired"] = False
    return updated, changed


def is_open(loan: dict[str, Any]) -> bool:
    """Whether the loan is not returned."""
    return loan.get("returned") is None


def is_overdue(loan: dict[str, Any], today: str) -> bool:
    """Whether the loan is open and its due date is before *today*."""
    due = loan.get("due")
    return is_open(loan) and isinstance(due, str) and due < today


# ── People ───────────────────────────────────────────────────────────────────


def default_person() -> dict[str, Any]:
    """The settings of a person with no stored settings."""
    return {"share_reading": True, "wishlist_todo": None, "yearly_goal": None}


def person_settings(people: dict[str, Any], person_id: str) -> dict[str, Any]:
    """The settings of *person_id*, with the defaults for a missing key."""
    stored = people.get(person_id)
    settings = default_person()
    if isinstance(stored, dict):
        settings.update({k: stored[k] for k in PERSON_FIELDS if k in stored})
    return settings


def apply_person_settings(
    settings: dict[str, Any], data: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(settings, changed_fields)``."""
    updated = dict(settings)
    for field in PERSON_FIELDS:
        if field not in data:
            continue
        raw = data[field]
        if field == "share_reading":
            updated[field] = boolean(raw, field)
        elif field == "wishlist_todo":
            updated[field] = entity_id_or_none(raw, field, "todo")
        else:
            updated[field] = integer(raw, field, low=1, high=MAX_GOAL)
    changed = [f for f in PERSON_FIELDS if updated.get(f) != settings.get(f)]
    return updated, changed


# ── Wishlist ─────────────────────────────────────────────────────────────────


def build_wishlist(person_id: str, *, buy: bool, now: str) -> dict[str, Any]:
    """A new wishlist entry on a book."""
    return {
        "person_id": text(person_id, "person_id", MAX_SHORT, required=True),
        "buy": boolean(buy, "buy"),
        "added_at": now,
        "todo_uid": None,
        "todo_entity": None,
        "bought": False,
    }


# ── Derived reads ────────────────────────────────────────────────────────────


def copies_of(state: dict[str, Any], book_id: str) -> list[dict[str, Any]]:
    """The copies of a book, oldest first."""
    rows = [c for c in state["copies"].values() if c.get("book_id") == book_id]
    return sorted(rows, key=lambda c: (str(c.get("created_at", "")), c["id"]))


def open_loan_of_copy(state: dict[str, Any], copy_id: str) -> dict[str, Any] | None:
    """The open ``out`` loan of a copy, if one exists."""
    for loan in state["loans"].values():
        if loan.get("copy_id") == copy_id and is_open(loan):
            return loan
    return None


def location_path(state: dict[str, Any], shelf_id: str | None) -> list[str]:
    """``[room, bookcase, shelf]`` names for a shelf, or ``[]``."""
    shelf = state["shelves"].get(shelf_id) if shelf_id else None
    if shelf is None:
        return []
    bookcase = state["bookcases"].get(shelf.get("bookcase_id")) or {}
    room = state["rooms"].get(bookcase.get("room_id")) or {}
    return [
        str(room.get("name", "")),
        str(bookcase.get("name", "")),
        str(shelf.get("name", "")),
    ]


def find_shelf_by_path(state: dict[str, Any], path: list[str]) -> str | None:
    """The id of the shelf whose room, bookcase and shelf names fold to *path*."""
    if len(path) != 3:
        return None
    wanted = [fold(part) for part in path]
    for shelf_id in state["shelves"]:
        if [fold(part) for part in location_path(state, shelf_id)] == wanted:
            return shelf_id
    return None


def find_book_by_isbn(
    state: dict[str, Any], isbn13: str | None, isbn10: str | None = None
) -> dict[str, Any] | None:
    """The book with this ISBN-13, then the book with this ISBN-10."""
    if isbn13:
        for book in state["books"].values():
            if book.get("isbn13") == isbn13:
                return book
    if isbn10:
        for book in state["books"].values():
            if book.get("isbn10") == isbn10:
                return book
    return None


def date_year(value: Any) -> int | None:
    """The year of a ``YYYY-MM-DD`` string."""
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


__all__ = [
    "BOOK_FIELDS",
    "CONDITIONS",
    "COPY_FIELDS",
    "COVER_KINDS",
    "DIRECTIONS",
    "FORMATS",
    "STATUSES",
    "STATUS_NONE",
    "LibraryError",
    "apply_person_settings",
    "apply_reading",
    "book_summary",
    "build_book",
    "build_bookcase",
    "build_copy",
    "build_loan",
    "build_room",
    "build_shelf",
    "build_wishlist",
    "empty_state",
    "fill_from_draft",
    "normalize_state",
    "update_book",
    "update_copy",
    "update_loan",
    "update_location",
]
