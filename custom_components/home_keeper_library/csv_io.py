"""Pure CSV import and export for Goodreads, StoryGraph and the library format.

Import has 2 steps:

1. ``parse(text, source)`` reads the CSV text into *import rows*: plain dicts
   with the same keys for each source (see :func:`empty_row`).
2. ``apply_import(state, rows, ...)`` returns a new document, a summary and a
   result for each row. It changes no argument, so a dry run is the same call
   with the result thrown away.

Export writes the Goodreads header, so the file imports into Goodreads and
StoryGraph, or the library format, which has every book and copy field.
``rows_from_state`` makes the rows, and ``write(rows, fmt)`` writes them, so
``parse(write(rows))`` gives the rows back (a property test checks this).

This module imports no Home Assistant code.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

from . import isbn as isbn_mod
from .models import (
    COPY_FIELDS,
    FORMATS,
    STATUSES,
    LibraryError,
    build_book,
    build_copy,
    build_wishlist,
    clone,
    copy_field,
    empty_reading,
    find_shelf_by_path,
    format_from_binding,
    location_path,
    title_key,
)

SOURCES = ("goodreads", "storygraph", "library")
EXPORT_FORMATS = ("goodreads", "library")

GOODREADS_COLUMNS = (
    "Book Id",
    "Title",
    "Author",
    "Author l-f",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Average Rating",
    "Publisher",
    "Binding",
    "Number of Pages",
    "Year Published",
    "Original Publication Year",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Bookshelves with positions",
    "Exclusive Shelf",
    "My Review",
    "Spoiler",
    "Private Notes",
    "Read Count",
    "Owned Copies",
)
STORYGRAPH_COLUMNS = (
    "Title",
    "Authors",
    "Contributors",
    "ISBN/UID",
    "Format",
    "Read Status",
    "Star Rating",
    "Review",
    "Last Date Read",
    "Dates Read",
    "Read Count",
    "Moods",
    "Pace",
    "Character- or Plot-Driven?",
    "Strong Character Development?",
    "Loveable Characters?",
    "Diverse Characters?",
    "Flawed Characters?",
    "Content Warnings",
    "Content Warning Description",
    "Tags",
    "Owned?",
)
LIBRARY_COLUMNS = (
    "book_id",
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
    "series_number",
    "description",
    "tags",
    "shared_notes",
    "copy_id",
    "format",
    "condition",
    "acquired",
    "acquired_from",
    "price",
    "value",
    "signed",
    "first_edition",
    "copy_note",
    "location",
    "status",
    "rating",
    "page",
    "started",
    "finished",
    "read_count",
    "private_notes",
    "wishlist",
    "wishlist_buy",
)
# The separator of a list in a library CSV cell, and of a location path.
LIST_SEP = "; "
PATH_SEP = " / "

_GOODREADS_SHELVES = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "want",
    "did-not-finish": "dnf",
}
_STATUS_TO_SHELF = {v: k for k, v in _GOODREADS_SHELVES.items()}
_STORYGRAPH_STATUS = _GOODREADS_SHELVES
_BINDINGS = {
    "hardcover": "Hardcover",
    "paperback": "Paperback",
    "ebook": "Kindle Edition",
    "audiobook": "Audible Audio",
    "other": "",
}

# The copy fields of a library row, and their CSV column.
_COPY_COLUMNS = {
    "format": "format",
    "condition": "condition",
    "acquired": "acquired",
    "acquired_from": "acquired_from",
    "price": "price",
    "value": "value",
    "signed": "signed",
    "first_edition": "first_edition",
    "note": "copy_note",
}


def empty_row(line: int) -> dict[str, Any]:
    """An import row with every key."""
    return {
        "line": line,
        "book_id": None,
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
        "owned": 0,
        "copy": None,
        "location": [],
        "status": None,
        "wishlist": False,
        "wishlist_buy": False,
        "rating": None,
        "page": None,
        "started": None,
        "finished": None,
        "read_count": None,
        "notes": "",
        "needs_details": True,
    }


# ── Cell readers ─────────────────────────────────────────────────────────────


def _cell(row: dict[str, Any], name: str) -> str:
    value = row.get(name)
    return value.strip() if isinstance(value, str) else ""


def isbn_cell(value: str) -> str:
    """``="0441478123"`` to ``0441478123``. ``=""`` is an empty cell."""
    value = value.strip()
    if value.startswith("="):
        value = value[1:]
    return value.strip().strip('"').strip()


def _int(value: str) -> int | None:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return int(value)
    return None


def _float(value: str) -> float | None:
    try:
        number = float(value.strip())
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def _date(value: str) -> str | None:
    """``YYYY/MM/DD`` or ``YYYY-MM-DD`` to ``YYYY-MM-DD``."""
    value = value.strip().replace("/", "-")
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        return None
    try:
        return date(
            int(match.group(1)), int(match.group(2)), int(match.group(3))
        ).isoformat()
    except ValueError:
        return None


def _split(value: str, sep: str = ",") -> list[str]:
    out: list[str] = []
    for part in value.split(sep):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def _isbns(*cells: str) -> tuple[str | None, str | None]:
    for cell in cells:
        found = isbn_mod.try_normalize(isbn_cell(cell))
        if found[0]:
            return found
    return None, None


def _rating(value: str) -> int | None:
    number = _float(value)
    if number is None or number <= 0:
        return None
    return max(1, min(5, int(number + 0.5)))


def _review(value: str) -> str:
    return re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE).strip()


def _notes(*parts: str) -> str:
    return "\n\n".join(part for part in parts if part)


def _reader(text: str) -> csv.DictReader[str]:
    if text.startswith("﻿"):
        text = text[1:]
    return csv.DictReader(io.StringIO(text, newline=""))


def _rows(text: str, required: str) -> list[dict[str, Any]]:
    try:
        reader = _reader(text)
        fields = reader.fieldnames or []
        if required not in fields:
            raise LibraryError("csv_unreadable", column=required)
        return list(reader)
    except csv.Error as err:
        raise LibraryError("csv_unreadable", column=required) from err


# ── Parsers ──────────────────────────────────────────────────────────────────


def parse_goodreads(text: str) -> list[dict[str, Any]]:
    """Import rows from a Goodreads export."""
    rows = []
    for index, raw in enumerate(_rows(text, "Title"), start=1):
        row = empty_row(index)
        row["title"] = _cell(raw, "Title")
        first = _cell(raw, "Author")
        authors = [first] if first else []
        authors += [
            a for a in _split(_cell(raw, "Additional Authors")) if a not in authors
        ]
        row["authors"] = authors
        row["isbn13"], row["isbn10"] = _isbns(_cell(raw, "ISBN13"), _cell(raw, "ISBN"))
        row["publisher"] = _cell(raw, "Publisher")
        row["published"] = _cell(raw, "Year Published") or _cell(
            raw, "Original Publication Year"
        )
        row["pages"] = _int(_cell(raw, "Number of Pages")) or None
        owned = _int(_cell(raw, "Owned Copies")) or 0
        row["owned"] = owned
        binding = _cell(raw, "Binding")
        if owned:
            row["copy"] = {"format": format_from_binding(binding)}
        shelf = _cell(raw, "Exclusive Shelf")
        status = _GOODREADS_SHELVES.get(shelf)
        if status == "want" and not owned:
            row["wishlist"] = True
            status = None
        row["status"] = status
        row["tags"] = [s for s in _split(_cell(raw, "Bookshelves")) if s != shelf]
        if status is not None:
            row["rating"] = _rating(_cell(raw, "My Rating"))
            row["read_count"] = _int(_cell(raw, "Read Count"))
            if status == "read":
                row["finished"] = _date(_cell(raw, "Date Read"))
        row["notes"] = _notes(
            _review(_cell(raw, "My Review")), _cell(raw, "Private Notes")
        )
        rows.append(row)
    return rows


def parse_storygraph(text: str) -> list[dict[str, Any]]:
    """Import rows from a StoryGraph export."""
    rows = []
    for index, raw in enumerate(_rows(text, "Title"), start=1):
        row = empty_row(index)
        row["title"] = _cell(raw, "Title")
        row["authors"] = _split(_cell(raw, "Authors"))
        row["isbn13"], row["isbn10"] = _isbns(_cell(raw, "ISBN/UID"))
        owned = _cell(raw, "Owned?").casefold() in ("yes", "true", "1")
        row["owned"] = 1 if owned else 0
        if owned:
            row["copy"] = {"format": format_from_binding(_cell(raw, "Format"))}
        status = _STORYGRAPH_STATUS.get(_cell(raw, "Read Status"))
        if status == "want" and not owned:
            row["wishlist"] = True
            status = None
        row["status"] = status
        row["tags"] = _split(_cell(raw, "Tags"))
        if status is not None:
            row["rating"] = _rating(_cell(raw, "Star Rating"))
            row["read_count"] = _int(_cell(raw, "Read Count"))
            if status == "read":
                row["finished"] = _date(_cell(raw, "Last Date Read"))
        row["notes"] = _review(_cell(raw, "Review"))
        rows.append(row)
    return rows


_RECORD_ID_RE = re.compile(r"[0-9a-f]{32}")


def _bool_cell(value: str) -> bool:
    return value.strip().casefold() in ("true", "yes", "1")


def _record_id(value: str) -> str | None:
    """*value* if it has the form of a record id (:func:`models.new_id`), else None.

    A cover file name starts with the book id, so an id from a file must not
    hold a path.
    """
    return value if _RECORD_ID_RE.fullmatch(value) else None


def parse_library(text: str) -> list[dict[str, Any]]:
    """Import rows from a library export: 1 row for each copy."""
    rows = []
    for index, raw in enumerate(_rows(text, "title"), start=1):
        row = empty_row(index)
        row["book_id"] = _record_id(_cell(raw, "book_id"))
        for field in ("title", "subtitle", "publisher", "published", "description"):
            row[field] = _cell(raw, field)
        row["shared_notes"] = _cell(raw, "shared_notes")
        row["authors"] = _split(_cell(raw, "authors"), LIST_SEP.strip())
        row["subjects"] = _split(_cell(raw, "subjects"), LIST_SEP.strip())
        row["tags"] = _split(_cell(raw, "tags"), LIST_SEP.strip())
        row["isbn13"], row["isbn10"] = _isbns(
            _cell(raw, "isbn13"), _cell(raw, "isbn10")
        )
        row["pages"] = _int(_cell(raw, "pages")) or None
        row["language"] = _cell(raw, "language") or None
        if series := _cell(raw, "series"):
            row["series"] = {
                "name": series,
                "number": _cell(raw, "series_number") or None,
            }
        fmt = _cell(raw, "format")
        if fmt in FORMATS:
            copy: dict[str, Any] = {"id": _record_id(_cell(raw, "copy_id"))}
            copy["format"] = fmt
            copy["condition"] = _cell(raw, "condition") or None
            copy["acquired"] = _date(_cell(raw, "acquired"))
            copy["acquired_from"] = _cell(raw, "acquired_from")
            copy["price"] = _money_cell(_cell(raw, "price"))
            copy["value"] = _money_cell(_cell(raw, "value"))
            copy["signed"] = _bool_cell(_cell(raw, "signed"))
            copy["first_edition"] = _bool_cell(_cell(raw, "first_edition"))
            copy["note"] = _cell(raw, "copy_note")
            row["copy"] = copy
            row["owned"] = 1
        location = _cell(raw, "location")
        row["location"] = location.split(PATH_SEP) if location else []
        status = _cell(raw, "status")
        row["status"] = status if status in STATUSES else None
        if row["status"] is not None:
            row["rating"] = _rating(_cell(raw, "rating"))
            row["page"] = _int(_cell(raw, "page"))
            row["started"] = _date(_cell(raw, "started"))
            row["finished"] = _date(_cell(raw, "finished"))
            row["read_count"] = _int(_cell(raw, "read_count"))
        row["notes"] = _cell(raw, "private_notes")
        row["wishlist"] = _bool_cell(_cell(raw, "wishlist"))
        row["wishlist_buy"] = _bool_cell(_cell(raw, "wishlist_buy"))
        row["needs_details"] = False
        rows.append(row)
    return rows


def _money_cell(value: str) -> float | int | None:
    number = _float(value)
    if number is None or number < 0:
        return None
    return int(number) if number.is_integer() else number


def parse(text: str, source: str) -> list[dict[str, Any]]:
    """Import rows from CSV *text* of *source*."""
    if source == "goodreads":
        return parse_goodreads(text)
    if source == "storygraph":
        return parse_storygraph(text)
    if source == "library":
        return parse_library(text)
    raise LibraryError("invalid_choice", field="source", options=", ".join(SOURCES))


# ── Import ───────────────────────────────────────────────────────────────────


class _Index:
    """The match keys of the books: ISBN-13, ISBN-10, then title and author."""

    def __init__(self, books: dict[str, dict[str, Any]]) -> None:
        self.by_id: set[str] = set()
        self.isbn13: dict[str, str] = {}
        self.isbn10: dict[str, str] = {}
        self.title: dict[str, str] = {}
        for book in books.values():
            self.add(book)

    def add(self, book: dict[str, Any]) -> None:
        self.by_id.add(book["id"])
        if book["isbn13"]:
            self.isbn13.setdefault(book["isbn13"], book["id"])
        if book["isbn10"]:
            self.isbn10.setdefault(book["isbn10"], book["id"])
        key = title_key(book["title"], book["authors"])
        if key.split("|", 1)[0]:
            self.title.setdefault(key, book["id"])

    def match(self, row: dict[str, Any]) -> tuple[str | None, str]:
        """``(book_id, action)``: ``existing``, ``title_match`` or ``new``."""
        if row["book_id"] and row["book_id"] in self.by_id:
            return str(row["book_id"]), ACTION_EXISTING
        if row["isbn13"] and row["isbn13"] in self.isbn13:
            return self.isbn13[row["isbn13"]], ACTION_EXISTING
        if row["isbn10"] and row["isbn10"] in self.isbn10:
            return self.isbn10[row["isbn10"]], ACTION_EXISTING
        found = self.title.get(title_key(row["title"], row["authors"]))
        return found, ACTION_TITLE_MATCH if found else ACTION_NEW


# The book fields of an import row.
_ROW_BOOK_FIELDS = (
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
)


def _new_book(row: dict[str, Any], now: str) -> dict[str, Any]:
    data = {
        field: row[field]
        for field in _ROW_BOOK_FIELDS
        if row.get(field) not in (None, "", [])
    }
    data["needs_details"] = bool(row.get("needs_details", True))
    book = build_book(data, now=now)
    if row.get("book_id"):
        book["id"] = str(row["book_id"])
    return book


ACTION_NEW = "new"
ACTION_EXISTING = "existing"
ACTION_TITLE_MATCH = "title_match"
ACTION_ERROR = "error"
COUNT_KEYS = (
    "rows",
    "read",
    "reading",
    "want",
    "dnf",
    "wishlist",
    "copies",
    "tags",
    "errors",
    "existing",
    "new",
    "title_match",
)


def summary_of(counts: dict[str, int], kept: int) -> dict[str, int]:
    """The summary of the ``import_completed`` event, from the import counts."""
    return {
        "rows": counts["rows"],
        "books_added": counts["new"],
        "books_matched": counts["existing"] + counts["title_match"],
        "copies_added": counts["copies"],
        "reading_set": counts["read"]
        + counts["reading"]
        + counts["want"]
        + counts["dnf"],
        "reading_kept": kept,
        "wishlist_added": counts["wishlist"],
        "errors": counts["errors"],
    }


def apply_import(
    state: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    person_id: str,
    shelf_id: str | None,
    import_notes: bool,
    replace_reading: bool,
    now: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    """Apply import rows to a copy of *state*.

    Return ``(new_state, counts, results, lookup_ids)``. ``counts`` has the keys
    of :data:`COUNT_KEYS` and ``reading_kept``. Each result has ``line``,
    ``title``, ``authors``, ``isbn``, ``book_id`` and ``action`` (``new``,
    ``existing``, ``title_match`` or ``error``). An error result also has
    ``error`` (a translation key) and ``placeholders``. ``lookup_ids`` are the
    new books that need details from Open Library.
    """
    new = clone(state)
    index = _Index(new["books"])
    reading = new["reading"].setdefault(person_id, {})
    copy_ids = set(new["copies"])
    owned_books = {c.get("book_id") for c in new["copies"].values()}
    reading_done: set[str] = set()
    counts = dict.fromkeys(COUNT_KEYS, 0)
    counts["rows"] = len(rows)
    counts["reading_kept"] = 0
    results: list[dict[str, Any]] = []
    lookup_ids: list[str] = []
    for row in rows:
        result: dict[str, Any] = {
            "line": row["line"],
            "title": row["title"],
            "authors": list(row["authors"]),
            "isbn": row["isbn13"] or row["isbn10"],
            "book_id": None,
            "action": ACTION_NEW,
        }
        try:
            # Check the copy first, so a row with a bad copy changes no record.
            copy_data = row.get("copy") or {}
            for field in COPY_FIELDS:
                if copy_data.get(field) is not None:
                    copy_field(field, copy_data[field])
            book_id, action = index.match(row)
            if book_id is None:
                book = _new_book(row, now)
                new["books"][book["id"]] = book
                index.add(book)
                book_id = book["id"]
                if book["needs_details"]:
                    lookup_ids.append(book_id)
                if row["tags"]:
                    counts["tags"] += 1
            else:
                book = new["books"][book_id]
                extra = [t for t in row["tags"] if t not in book["tags"]]
                if extra:
                    book["tags"] = [*book["tags"], *extra]
                    counts["tags"] += 1
            counts[action] += 1
            result["action"] = action
            result["book_id"] = book_id
            if _import_copy(new, row, book_id, shelf_id, copy_ids, owned_books, now):
                counts["copies"] += 1
            # A library file has 1 row for each copy. The first row of a book
            # sets its reading status.
            if row["status"] and book_id not in reading_done:
                reading_done.add(book_id)
                if book_id in reading and not replace_reading:
                    counts["reading_kept"] += 1
                else:
                    reading[book_id] = _reading_row(row, import_notes, now)
                    counts[row["status"]] += 1
            if (
                row["wishlist"]
                and book_id not in owned_books
                and not new["books"][book_id]["wishlist"]
            ):
                entry = build_wishlist(
                    person_id, buy=bool(row["wishlist_buy"]), now=now
                )
                new["books"][book_id]["wishlist"] = entry
                counts["wishlist"] += 1
        except LibraryError as err:
            result["action"] = ACTION_ERROR
            result["error"] = err.key
            result["placeholders"] = err.placeholders
            counts["errors"] += 1
        results.append(result)
    if not reading:
        new["reading"].pop(person_id, None)
    return new, counts, results, lookup_ids


def _import_copy(
    new: dict[str, Any],
    row: dict[str, Any],
    book_id: str,
    shelf_id: str | None,
    copy_ids: set[str],
    owned_books: set[Any],
    now: str,
) -> bool:
    """Add the copy of a row, if the row has one and it is not in the library.

    A Goodreads or StoryGraph row adds 1 copy only to a book with no copy. A
    library row adds its copy unless a copy with its id exists. Return whether a
    copy was added.
    """
    copy = row.get("copy")
    if copy is None:
        return False
    copy_id = copy.get("id")
    if copy_id is not None:
        if copy_id in copy_ids:
            return False
    elif book_id in owned_books:
        return False
    location = row.get("location") or []
    target = find_shelf_by_path(new, location) if location else None
    data = {k: v for k, v in copy.items() if k != "id" and v is not None}
    data["book_id"] = book_id
    data["shelf_id"] = target or (shelf_id if shelf_id in new["shelves"] else None)
    record = build_copy(data, now=now)
    if copy_id:
        record["id"] = str(copy_id)
    new["copies"][record["id"]] = record
    copy_ids.add(record["id"])
    owned_books.add(book_id)
    return True


def _reading_row(row: dict[str, Any], import_notes: bool, now: str) -> dict[str, Any]:
    reading = empty_reading(now=now)
    reading["status"] = row["status"]
    for field in ("rating", "page", "started", "finished"):
        reading[field] = row.get(field)
    count = row["read_count"]
    if count is None:
        count = 1 if row["status"] == "read" else 0
    reading["read_count"] = count
    if import_notes:
        reading["private_notes"] = row["notes"]
    return reading


# ── Export ───────────────────────────────────────────────────────────────────


def rows_from_state(
    state: dict[str, Any], person_id: str | None, fmt: str
) -> list[dict[str, Any]]:
    """Import rows that describe the library, for :func:`write`.

    The library format has 1 row for each copy, and 1 row for a book with no
    copy. The Goodreads format has 1 row for each book. With no *person_id*, the
    rows have no reading status.
    """
    copies: dict[str, list[dict[str, Any]]] = {}
    for copy in sorted(
        state["copies"].values(), key=lambda c: (str(c.get("created_at")), c["id"])
    ):
        copies.setdefault(copy["book_id"], []).append(copy)
    reading = state["reading"].get(person_id, {}) if person_id else {}
    rows: list[dict[str, Any]] = []
    books = sorted(
        state["books"].values(),
        key=lambda b: (b["title"].casefold(), b["id"]),
    )
    for book in books:
        base = empty_row(len(rows) + 1)
        for field in (*_ROW_BOOK_FIELDS, "needs_details"):
            base[field] = clone(book[field])
        base["book_id"] = book["id"]
        row_reading = reading.get(book["id"])
        if row_reading:
            for field in ("status", "rating", "page", "started", "finished"):
                base[field] = row_reading.get(field)
            base["read_count"] = row_reading.get("read_count")
            base["notes"] = row_reading.get("private_notes", "")
        wish = book["wishlist"]
        if wish and (person_id is None or wish.get("person_id") == person_id):
            base["wishlist"] = True
            base["wishlist_buy"] = bool(wish.get("buy"))
        book_copies = copies.get(book["id"], [])
        base["owned"] = len(book_copies)
        if fmt == "goodreads" or not book_copies:
            if book_copies:
                base["copy"] = {"format": book_copies[0].get("format", "other")}
            rows.append(base)
            continue
        for copy in book_copies:
            row = clone(base)
            row["line"] = len(rows) + 1
            row["copy"] = {
                "id": copy["id"],
                **{field: copy.get(field) for field in _COPY_COLUMNS},
            }
            row["location"] = location_path(state, copy.get("shelf_id"))
            rows.append(row)
    return rows


def _write_cells(fieldnames: tuple[str, ...], cells: list[dict[str, str]]) -> str:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(cells)
    return out.getvalue()


def _num(value: Any) -> str:
    return "" if value is None else str(value)


def _goodreads_cells(row: dict[str, Any]) -> dict[str, str]:
    authors = row["authors"] or []
    status = row["status"]
    shelf = _STATUS_TO_SHELF.get(status or "", "")
    if not shelf and row["wishlist"]:
        shelf = "to-read"
    shelves = [*([shelf] if shelf else []), *row["tags"]]
    copy = row["copy"] or {}
    first = authors[0] if authors else ""
    last_first = first
    if " " in first:
        given, family = first.rsplit(" ", 1)
        last_first = f"{family}, {given}"
    return {
        "Book Id": "",
        "Title": row["title"],
        "Author": first,
        "Author l-f": last_first,
        "Additional Authors": ", ".join(authors[1:]),
        "ISBN": f'="{row["isbn10"] or ""}"',
        "ISBN13": f'="{row["isbn13"] or ""}"',
        "My Rating": str(row["rating"] or 0),
        "Average Rating": "",
        "Publisher": row["publisher"],
        "Binding": _BINDINGS.get(copy.get("format", "other"), ""),
        "Number of Pages": _num(row["pages"]),
        "Year Published": row["published"],
        "Original Publication Year": "",
        "Date Read": (row["finished"] or "").replace("-", "/"),
        "Date Added": "",
        "Bookshelves": ", ".join(shelves),
        "Bookshelves with positions": "",
        "Exclusive Shelf": shelf,
        "My Review": "",
        "Spoiler": "",
        "Private Notes": row["notes"],
        "Read Count": _num(row["read_count"]) if status else "",
        "Owned Copies": str(row["owned"] or 0),
    }


def _bool_text(value: Any) -> str:
    return "true" if value else "false"


def _library_cells(row: dict[str, Any]) -> dict[str, str]:
    series = row["series"] or {}
    copy = row["copy"] or {}
    return {
        "book_id": row["book_id"] or "",
        "title": row["title"],
        "subtitle": row["subtitle"],
        "authors": LIST_SEP.join(row["authors"] or []),
        "isbn13": row["isbn13"] or "",
        "isbn10": row["isbn10"] or "",
        "publisher": row["publisher"],
        "published": row["published"],
        "pages": _num(row["pages"]),
        "language": row["language"] or "",
        "subjects": LIST_SEP.join(row["subjects"] or []),
        "series": series.get("name", ""),
        "series_number": series.get("number") or "",
        "description": row["description"],
        "tags": LIST_SEP.join(row["tags"] or []),
        "shared_notes": row["shared_notes"],
        "copy_id": copy.get("id") or "",
        "format": copy.get("format") or "",
        "condition": copy.get("condition") or "",
        "acquired": copy.get("acquired") or "",
        "acquired_from": copy.get("acquired_from") or "",
        "price": _num(copy.get("price")),
        "value": _num(copy.get("value")),
        "signed": _bool_text(copy.get("signed")) if copy else "",
        "first_edition": _bool_text(copy.get("first_edition")) if copy else "",
        "copy_note": copy.get("note") or "",
        "location": PATH_SEP.join(row["location"] or []),
        "status": row["status"] or "",
        "rating": _num(row["rating"]),
        "page": _num(row["page"]),
        "started": row["started"] or "",
        "finished": row["finished"] or "",
        "read_count": _num(row["read_count"]),
        "private_notes": row["notes"],
        "wishlist": _bool_text(row["wishlist"]),
        "wishlist_buy": _bool_text(row["wishlist_buy"]),
    }


def write(rows: list[dict[str, Any]], fmt: str) -> str:
    """CSV text for import rows, in the Goodreads or the library format."""
    if fmt == "goodreads":
        return _write_cells(GOODREADS_COLUMNS, [_goodreads_cells(r) for r in rows])
    if fmt == "library":
        return _write_cells(LIBRARY_COLUMNS, [_library_cells(r) for r in rows])
    raise LibraryError(
        "invalid_choice", field="format", options=", ".join(EXPORT_FORMATS)
    )


def export(state: dict[str, Any], person_id: str | None, fmt: str) -> str:
    """CSV text of the library in *fmt*."""
    return write(rows_from_state(state, person_id, fmt), fmt)


def export_filename(fmt: str, today: str) -> str:
    """The file name of an export, such as ``library-goodreads-2026-10-05.csv``."""
    return f"library-{fmt}-{today}.csv"


__all__ = [
    "EXPORT_FORMATS",
    "GOODREADS_COLUMNS",
    "LIBRARY_COLUMNS",
    "SOURCES",
    "STORYGRAPH_COLUMNS",
    "apply_import",
    "empty_row",
    "export",
    "export_filename",
    "isbn_cell",
    "parse",
    "parse_goodreads",
    "parse_library",
    "parse_storygraph",
    "rows_from_state",
    "write",
]
