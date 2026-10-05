"""Pure payload builders for the bus events of Home Keeper Library.

Each state change fires a ``home_keeper_library_<noun>_<verb>`` event. The store
fires it, and a builder here makes the payload, so a test and an integrator read
the payload that ships. The book events share 1 spine:
``{book_id, title, person_id, origin}``. ``origin`` is the marker that the caller
sent, or None for a user.

The catalog is ``api_surface.EVENTS`` and ``docs/EVENTS.md``.

This module imports no Home Assistant code.
"""

from __future__ import annotations

from typing import Any


def room_event_data(room: dict[str, Any], origin: str | None) -> dict[str, Any]:
    """The payload of the room events."""
    return {"room_id": room["id"], "name": room.get("name", ""), "origin": origin}


def bookcase_event_data(bookcase: dict[str, Any], origin: str | None) -> dict[str, Any]:
    """The payload of the bookcase events."""
    return {
        "bookcase_id": bookcase["id"],
        "room_id": bookcase.get("room_id"),
        "name": bookcase.get("name", ""),
        "origin": origin,
    }


def shelf_event_data(shelf: dict[str, Any], origin: str | None) -> dict[str, Any]:
    """The payload of the shelf events."""
    return {
        "shelf_id": shelf["id"],
        "bookcase_id": shelf.get("bookcase_id"),
        "name": shelf.get("name", ""),
        "origin": origin,
    }


def location_changed_data(
    base: dict[str, Any], changed_fields: list[str]
) -> dict[str, Any]:
    """A location payload with the list of changed fields."""
    return {**base, "changed_fields": list(changed_fields)}


def book_event_data(
    book: dict[str, Any], origin: str | None, person_id: str | None = None
) -> dict[str, Any]:
    """The spine of every book event."""
    return {
        "book_id": book["id"],
        "title": book.get("title", ""),
        "person_id": person_id,
        "origin": origin,
    }


def book_updated_event_data(
    book: dict[str, Any], changed_fields: list[str], origin: str | None
) -> dict[str, Any]:
    """The payload of ``book_updated``."""
    return {**book_event_data(book, origin), "changed_fields": list(changed_fields)}


def copy_event_data(
    book: dict[str, Any], copy: dict[str, Any], origin: str | None
) -> dict[str, Any]:
    """The payload of ``copy_added`` and ``copy_removed``."""
    return {
        **book_event_data(book, origin),
        "copy_id": copy["id"],
        "shelf_id": copy.get("shelf_id"),
    }


def copy_updated_event_data(
    book: dict[str, Any],
    copy: dict[str, Any],
    changed_fields: list[str],
    origin: str | None,
) -> dict[str, Any]:
    """The payload of ``copy_updated``. It names the fields, not their values."""
    return {
        **copy_event_data(book, copy, origin),
        "changed_fields": list(changed_fields),
    }


def copy_moved_event_data(
    book: dict[str, Any],
    copy: dict[str, Any],
    previous_shelf_id: str | None,
    origin: str | None,
) -> dict[str, Any]:
    """The payload of ``copy_moved``."""
    return {
        **copy_event_data(book, copy, origin),
        "previous_shelf_id": previous_shelf_id,
    }


def reading_changed_event_data(
    book: dict[str, Any],
    person_id: str,
    status: str | None,
    previous_status: str | None,
    origin: str | None,
) -> dict[str, Any]:
    """The payload of ``reading_changed``. ``status`` is None for a removed row."""
    return {
        **book_event_data(book, origin, person_id),
        "status": status,
        "previous_status": previous_status,
    }


def reading_updated_event_data(
    book: dict[str, Any],
    person_id: str,
    status: str,
    changed_fields: list[str],
    origin: str | None,
) -> dict[str, Any]:
    """The payload of ``reading_updated``: a change that keeps the status.

    It names the fields, so the private notes of a person never go on the bus.
    """
    return {
        **book_event_data(book, origin, person_id),
        "status": status,
        "changed_fields": list(changed_fields),
    }


def book_finished_event_data(
    book: dict[str, Any], person_id: str, row: dict[str, Any], origin: str | None
) -> dict[str, Any]:
    """The payload of ``book_finished``."""
    return {
        **book_event_data(book, origin, person_id),
        "finished": row.get("finished"),
        "rating": row.get("rating"),
        "read_count": row.get("read_count", 0),
    }


def loan_event_data(
    book: dict[str, Any], loan: dict[str, Any], origin: str | None
) -> dict[str, Any]:
    """The payload of ``loan_started``, ``loan_returned`` and ``loan_overdue``."""
    return {
        **book_event_data(book, origin, loan.get("person_id")),
        "loan_id": loan["id"],
        "direction": loan.get("direction"),
        "copy_id": loan.get("copy_id"),
        "party": loan.get("party", ""),
        "started": loan.get("started"),
        "due": loan.get("due"),
        "returned": loan.get("returned"),
    }


def loan_updated_event_data(
    book: dict[str, Any],
    loan: dict[str, Any],
    changed_fields: list[str],
    origin: str | None,
) -> dict[str, Any]:
    """The payload of ``loan_updated``."""
    return {
        **loan_event_data(book, loan, origin),
        "changed_fields": list(changed_fields),
    }


def wishlist_event_data(
    book: dict[str, Any], entry: dict[str, Any], origin: str | None
) -> dict[str, Any]:
    """The payload of ``wishlist_added`` and ``wishlist_removed``."""
    return {
        **book_event_data(book, origin, entry.get("person_id")),
        "buy": bool(entry.get("buy")),
        "bought": bool(entry.get("bought")),
    }


def import_completed_event_data(
    summary: dict[str, Any], person_id: str | None, source: str, origin: str | None
) -> dict[str, Any]:
    """The payload of ``import_completed``."""
    return {
        "person_id": person_id,
        "source": source,
        "rows": int(summary.get("rows", 0)),
        "books_added": int(summary.get("books_added", 0)),
        "books_matched": int(summary.get("books_matched", 0)),
        "copies_added": int(summary.get("copies_added", 0)),
        "reading_set": int(summary.get("reading_set", 0)),
        "wishlist_added": int(summary.get("wishlist_added", 0)),
        "errors": int(summary.get("errors", 0)),
        "origin": origin,
    }


def person_settings_event_data(
    person_id: str, changed_fields: list[str], origin: str | None
) -> dict[str, Any]:
    """The payload of ``person_settings_updated``. It has no setting values."""
    return {
        "person_id": person_id,
        "changed_fields": list(changed_fields),
        "origin": origin,
    }


def settings_event_data(
    changed_fields: list[str], currency: str, origin: str | None
) -> dict[str, Any]:
    """The payload of ``settings_updated``: the options of the library."""
    return {
        "changed_fields": list(changed_fields),
        "currency": currency,
        "origin": origin,
    }
