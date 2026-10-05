"""Pure parser for the Open Library JSON documents.

The client (``openlibrary_client.py``) reads these documents:

* ``/isbn/{isbn}.json``: the edition.
* ``/works/{key}.json``: the work of the edition.
* ``/authors/{key}.json``: each author.
* ``/search.json?title=&author=&limit=5``: a title and author search, for a CSV
  row with no ISBN.

The functions here turn them into a *book draft*: a dict with the book fields of
``models.DRAFT_FIELDS`` and an ``openlibrary`` block. The parser accepts the
shapes that Open Library documents show, and ignores a value of the wrong type.

This module imports no Home Assistant code.
"""

from __future__ import annotations

import re
from typing import Any

from . import isbn as isbn_mod
from .models import fold, title_key

# Open Library language keys are MARC codes. The common ones map to the ISO 639-1
# code. Another code is stored as is.
_LANGUAGES = {
    "eng": "en",
    "ger": "de",
    "fre": "fr",
    "spa": "es",
    "ita": "it",
    "dut": "nl",
    "swe": "sv",
    "dan": "da",
    "nor": "nb",
    "fin": "fi",
    "pol": "pl",
    "por": "pt",
    "rus": "ru",
    "cze": "cs",
    "cat": "ca",
    "chi": "zh",
    "jpn": "ja",
}
_MAX_SUBJECTS = 10
_KEY_RE = re.compile(r"^/(books|works|authors)/(OL\d+[MWA])$")


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_value(value: Any) -> str:
    """A description is a string or ``{"type": "/type/text", "value": ...}``."""
    if isinstance(value, dict):
        return _str(value.get("value"))
    return _str(value)


def _key(value: Any, kind: str) -> str | None:
    """``OL123W`` from ``/works/OL123W``, if the kind matches."""
    match = _KEY_RE.match(_str(value))
    if match and match.group(1) == kind:
        return match.group(2)
    return None


def _str_list(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        entry = _str(item)
        if entry and entry not in out:
            out.append(entry)
    return out[:limit]


def _first_int(value: Any) -> int | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _year(value: Any) -> str:
    """The 4-digit year in a publish date such as ``March 1987``, else the text."""
    text = _str(value)
    match = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", text)
    return match.group(1) if match else text[:50]


def _language(value: Any) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        raw = first.get("key") if isinstance(first, dict) else first
        code = _str(raw).rsplit("/", 1)[-1]
        if code:
            return _LANGUAGES.get(code, code)
    return None


def _series(value: Any) -> dict[str, Any] | None:
    """``["Earthsea Cycle", "#2"]`` or ``["Dune Chronicles (1)"]`` to a series."""
    names = _str_list(value)
    if not names:
        return None
    name = names[0]
    number = None
    match = re.match(r"^(.*?)[\s,;]*[\(#]\s*(\d+(?:\.\d+)?)\)?\s*$", name)
    if match and match.group(1).strip():
        name, number = match.group(1).strip(), match.group(2)
    elif len(names) > 1 and re.fullmatch(r"#?\s*\d+(?:\.\d+)?", names[1]):
        number = names[1].lstrip("#").strip()
    return {"name": name[:200], "number": number}


def author_keys(edition: dict[str, Any], work: dict[str, Any] | None) -> list[str]:
    """The author keys (``OL123A``) of an edition, else of its work."""
    keys: list[str] = []
    for entry in edition.get("authors") or []:
        if isinstance(entry, dict) and (key := _key(entry.get("key"), "authors")):
            keys.append(key)
    if not keys and work:
        for entry in work.get("authors") or []:
            if not isinstance(entry, dict):
                continue
            author = entry.get("author")
            raw = author.get("key") if isinstance(author, dict) else None
            if key := _key(raw, "authors"):
                keys.append(key)
    return list(dict.fromkeys(keys))


def work_key(edition: dict[str, Any]) -> str | None:
    """The work key (``OL123W``) of an edition."""
    for entry in edition.get("works") or []:
        if isinstance(entry, dict) and (key := _key(entry.get("key"), "works")):
            return key
    return None


def author_name(author: dict[str, Any]) -> str:
    """The display name of an author document."""
    return _str(author.get("name")) or _str(author.get("personal_name"))


def parse_edition(
    edition: dict[str, Any],
    work: dict[str, Any] | None = None,
    authors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A book draft from an edition, its work and its author documents."""
    work = work or {}
    isbn13 = None
    isbn10 = None
    for raw in _str_list(edition.get("isbn_13")) + _str_list(edition.get("isbn_10")):
        found13, found10 = isbn_mod.try_normalize(raw)
        if found13:
            isbn13, isbn10 = isbn13 or found13, isbn10 or found10
    names = [name for a in authors or [] if (name := author_name(a))]
    if not names and (by := _str(edition.get("by_statement"))):
        names = [by.removeprefix("by ").strip()]
    subjects = _str_list(edition.get("subjects")) or _str_list(work.get("subjects"))
    cover_id = _first_int(edition.get("covers")) or _first_int(work.get("covers"))
    description = _text_value(edition.get("description")) or _text_value(
        work.get("description")
    )
    publishers = _str_list(edition.get("publishers"))
    return {
        "title": _str(edition.get("title")) or _str(work.get("title")),
        "subtitle": _str(edition.get("subtitle")),
        "authors": names,
        "isbn13": isbn13,
        "isbn10": isbn10,
        "publisher": publishers[0] if publishers else "",
        "published": _year(edition.get("publish_date")),
        "pages": _first_int(edition.get("number_of_pages")),
        "language": _language(edition.get("languages")),
        "subjects": subjects[:_MAX_SUBJECTS],
        "series": _series(edition.get("series")),
        "description": description,
        "openlibrary": {
            "edition_key": _key(edition.get("key"), "books"),
            "work_key": work_key(edition) or _key(work.get("key"), "works"),
            "cover_id": cover_id,
        },
    }


def parse_search_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """A book draft from 1 ``docs`` entry of a search result."""
    isbn13 = None
    isbn10 = None
    for raw in _str_list(doc.get("isbn"), 200):
        found13, found10 = isbn_mod.try_normalize(raw)
        if found13 and found13.startswith("978"):
            isbn13, isbn10 = found13, found10
            break
        if found13 and isbn13 is None:
            isbn13, isbn10 = found13, found10
    editions = _str_list(doc.get("edition_key"))
    publishers = _str_list(doc.get("publisher"))
    year = doc.get("first_publish_year")
    return {
        "title": _str(doc.get("title")),
        "subtitle": _str(doc.get("subtitle")),
        "authors": _str_list(doc.get("author_name")),
        "isbn13": isbn13,
        "isbn10": isbn10,
        "publisher": publishers[0] if publishers else "",
        "published": str(year) if isinstance(year, int) else "",
        "pages": _first_int(doc.get("number_of_pages_median")),
        "language": _language(doc.get("language")),
        "subjects": _str_list(doc.get("subject"))[:_MAX_SUBJECTS],
        "series": None,
        "description": "",
        "openlibrary": {
            "edition_key": editions[0] if editions else None,
            "work_key": _key(doc.get("key"), "works"),
            "cover_id": _first_int(doc.get("cover_i")),
        },
    }


def parse_search(result: Any) -> list[dict[str, Any]]:
    """The book drafts of a search result, in result order."""
    if not isinstance(result, dict):
        return []
    docs = result.get("docs")
    if not isinstance(docs, list):
        return []
    return [parse_search_doc(doc) for doc in docs if isinstance(doc, dict)]


def best_match(
    drafts: list[dict[str, Any]], title: str, authors: list[str]
) -> dict[str, Any] | None:
    """The first draft whose title and first author match, else None.

    With no author in the query, the folded title alone must match.
    """
    wanted = title_key(title, authors)
    wanted_title = fold(str(title).split(":", 1)[0])
    for draft in drafts:
        if authors:
            if title_key(draft.get("title"), draft.get("authors")) == wanted:
                return draft
        elif fold(str(draft.get("title", "")).split(":", 1)[0]) == wanted_title:
            return draft
    return None


def edition_url(base: str, isbn13: str) -> str:
    """The URL of the edition document of an ISBN."""
    return f"{base}/isbn/{isbn13}.json"


def work_url(base: str, key: str) -> str:
    """The URL of a work document."""
    return f"{base}/works/{key}.json"


def author_url(base: str, key: str) -> str:
    """The URL of an author document."""
    return f"{base}/authors/{key}.json"


def cover_image_url(base: str, cover_id: int) -> str:
    """The URL of the large cover image. A missing cover gives a 404."""
    return f"{base}/b/id/{cover_id}-L.jpg?default=false"
