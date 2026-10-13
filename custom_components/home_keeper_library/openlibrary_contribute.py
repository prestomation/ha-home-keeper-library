"""Send a book to Open Library: the pure parts.

An admin can send a book that Open Library does not have. Open Library takes a new
book from a normal account only through the form of its "Add a book" page, so the
library posts the same form. This module builds that form and reads the reply. The
HTTP calls are in ``openlibrary_account.py``.

* The form has 5 fields: the title, the first author, the publisher, the publish
  date and 1 ISBN. The admin selects which of the last 3 go.
* An author that Open Library has gets its key, so Open Library does not make a
  second author with the same name.
* Open Library replies with a redirect to the edit page of the edition. The mode
  in the URL tells if the edition is new or if Open Library already had it.

This module imports no Home Assistant code.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

# The book fields that the "Add a book" form takes. Title and author always go.
SEND_FIELDS = ("title", "authors", "publisher", "published", "isbn")
OPTIONAL_SEND_FIELDS = ("publisher", "published", "isbn")
NEW_AUTHOR = "__new__"

_EDITION_RE = re.compile(r"^/books/(OL\d+M)(?:/|$)")
_EDITION_KEY_RE = re.compile(r"^OL\d+M$")
_INPUT_RE = re.compile(r"(?:^|/books/)(OL\d+M)(?:[/?#.]|$)")
_WORK_KEY_RE = re.compile(r"^OL\d+W$")
_WORK_INPUT_RE = re.compile(r"(?:^|/works/)(OL\d+W)(?:[/?#.]|$)")
_ADDED_MODES = ("add-work", "add-book")


def send_fields(selected: list[str] | None) -> list[str]:
    """The fields to send: title and authors, plus the selected optional fields."""
    chosen = set(selected or [])
    return ["title", "authors", *(f for f in OPTIONAL_SEND_FIELDS if f in chosen)]


def add_book_form(
    book: dict[str, Any], fields: list[str], author_key: str
) -> dict[str, str]:
    """The form data of ``POST /books/add`` for *book*.

    *author_key* is ``/authors/OL…A`` or ``__new__``. The ISBN-13 goes first, else
    the ISBN-10. An empty field is not sent.
    """
    authors = book.get("authors") or []
    form = {
        "book_title": str(book.get("title") or "").strip(),
        "authors--0--author--key": author_key,
        "author_names--0": str(authors[0]).strip() if authors else "",
    }
    if "publisher" in fields and (publisher := str(book.get("publisher") or "")):
        form["publisher"] = publisher.strip()
    if "published" in fields and (published := str(book.get("published") or "")):
        form["publish_date"] = published.strip()
    if "isbn" in fields:
        if book.get("isbn13"):
            form["id_name"], form["id_value"] = "isbn_13", str(book["isbn13"])
        elif book.get("isbn10"):
            form["id_name"], form["id_value"] = "isbn_10", str(book["isbn10"])
    return form


def pick_author_key(search: Any, name: str) -> str:
    """The key of the author named *name* in a ``/search/authors.json`` reply.

    Only an exact name match counts, without case. With no match, or with 2
    authors of that name, the form asks for a new author.
    """
    wanted = name.strip().casefold()
    docs = search.get("docs") if isinstance(search, dict) else None
    if not wanted or not isinstance(docs, list):
        return NEW_AUTHOR
    keys = [
        doc["key"]
        for doc in docs
        if isinstance(doc, dict)
        and isinstance(doc.get("name"), str)
        and doc["name"].strip().casefold() == wanted
        and isinstance(doc.get("key"), str)
        and re.fullmatch(r"(?:/authors/)?OL\d+A", doc["key"])
    ]
    if len(keys) != 1:
        return NEW_AUTHOR
    key = keys[0]
    return key if key.startswith("/authors/") else f"/authors/{key}"


def parse_add_reply(status: int, location: str | None) -> tuple[str, str | None]:
    """Read the reply of ``POST /books/add``: ``(result, edition_key)``.

    * ``added``: Open Library made a new edition.
    * ``existing``: Open Library already had the edition.
    * ``ambiguous``: no redirect to an edition. Open Library asks the user to pick
      1 of many works, so the book must be added on the website.
    """
    if status not in (301, 302, 303, 307) or not location:
        return "ambiguous", None
    parts = urlsplit(location)
    match = _EDITION_RE.match(parts.path)
    if not match:
        return "ambiguous", None
    modes = parse_qs(parts.query).get("mode", [])
    added = any(mode in _ADDED_MODES for mode in modes)
    return ("added" if added else "existing"), match.group(1)


def session_username(cookie: str | None) -> str | None:
    """The user name in the ``session`` cookie of Open Library.

    The cookie value is ``/people/<username>,<time>,<hash>``. It can be quoted,
    with each comma as the octal escape ``\\054``, or URL-encoded.
    """
    if not cookie:
        return None
    value = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), cookie.strip())
    value = unquote(value.removeprefix('"'))
    match = re.match(r"^/people/([^,/]+),", value)
    return match.group(1) if match else None


def edition_key(text: Any) -> str | None:
    """The edition key ``OL…M`` in a key or an openlibrary.org URL, or None."""
    if not isinstance(text, str):
        return None
    value = text.strip()
    if _EDITION_KEY_RE.match(value):
        return value
    match = _INPUT_RE.search(value)
    return match.group(1) if match else None


def work_key(text: Any) -> str | None:
    """The work key ``OL…W`` in a key or an openlibrary.org URL, or None."""
    if not isinstance(text, str):
        return None
    value = text.strip()
    if _WORK_KEY_RE.match(value):
        return value
    match = _WORK_INPUT_RE.search(value)
    return match.group(1) if match else None
