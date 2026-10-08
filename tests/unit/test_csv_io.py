"""Unit tests for the pure CSV import and export."""

from __future__ import annotations

import csv
import io
import string

import ex.csv_io as cio
import ex.isbn as isbn_mod
import ex.models as m
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

NOW = "2026-10-05T12:00:00+00:00"

GOODREADS = (
    "﻿Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,"
    "Average Rating,Publisher,Binding,Number of Pages,Year Published,"
    "Original Publication Year,Date Read,Date Added,Bookshelves,"
    "Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,"
    "Read Count,Owned Copies\n"
    '1,The Left Hand of Darkness,Ursula K. Le Guin,"Le Guin, Ursula K.",,'
    '"=""0441478123""","=""9780441478125""",5,4.1,Ace,Mass Market Paperback,'
    '304,1987,1969,2024/03/05,2024/01/01,"favorites, read",,read,'
    "Great<br/>book,,Mine,2,1\n"
    '2,Dune,Frank Herbert,"Herbert, Frank",Kevin J. Anderson,"=""""","=""""",0,4.2,'
    "Ace,Kindle Edition,,1990,,,,currently-reading,,currently-reading,,,,1,0\n"
    '3,Emma,Jane Austen,"Austen, Jane",,"=""""","=""""",0,4,Penguin,Hardcover,,,,,,'
    "to-read,,to-read,,,,0,0\n"
    '4,Persuasion,Jane Austen,"Austen, Jane",,"=""""","=""""",0,4,Penguin,'
    "Hardcover,,,,,,to-read,,to-read,,,,0,1\n"
    '5,Ulysses,James Joyce,"Joyce, James",,,,0,3,X,Paperback,,,,,,'
    "did-not-finish,,did-not-finish,,,,0,0\n"
    "6,Notes,Me,,,,,0,0,,,,,,,,custom,,custom,,,,0,0\n"
)

STORYGRAPH = (
    "Title,Authors,Contributors,ISBN/UID,Format,Read Status,Star Rating,Review,"
    "Last Date Read,Dates Read,Read Count,Moods,Pace,Character- or Plot-Driven?,"
    "Strong Character Development?,Loveable Characters?,Diverse Characters?,"
    "Flawed Characters?,Content Warnings,Content Warning Description,Tags,Owned?\n"
    "Dune,Frank Herbert,,9780441013593,paperback,read,4.75,Good,2024/02/01,,1,,,,,,,,,,"
    '"sf, classic",Yes\n'
    "Emma,Jane Austen,,,hardcover,to-read,,,,,0,,,,,,,,,,,No\n"
    "Ulysses,James Joyce,,,digital,did-not-finish,2.25,,,,0,,,,,,,,,,,Yes\n"
    "Middlemarch,George Eliot,,,audio,currently-reading,,,,,0,,,,,,,,,,,No\n"
)


def test_isbn_cell() -> None:
    assert cio.isbn_cell('="0441478123"') == "0441478123"
    assert cio.isbn_cell('=""') == ""
    assert cio.isbn_cell(" 978 ") == "978"


def test_parse_goodreads() -> None:
    rows = cio.parse(GOODREADS, "goodreads")
    assert [r["line"] for r in rows] == [1, 2, 3, 4, 5, 6]
    left = rows[0]
    assert left["title"] == "The Left Hand of Darkness"
    assert left["authors"] == ["Ursula K. Le Guin"]
    assert (left["isbn13"], left["isbn10"]) == ("9780441478125", "0441478123")
    assert left["status"] == "read" and left["rating"] == 5
    assert left["finished"] == "2024-03-05" and left["read_count"] == 2
    assert left["owned"] == 1 and left["copy"] == {"format": "paperback"}
    assert left["tags"] == ["favorites"]
    assert left["notes"] == "Great\nbook\n\nMine"
    assert left["publisher"] == "Ace" and left["pages"] == 304
    assert left["published"] == "1987"
    dune = rows[1]
    assert dune["authors"] == ["Frank Herbert", "Kevin J. Anderson"]
    assert dune["isbn13"] is None and dune["status"] == "reading"
    assert dune["rating"] is None and dune["copy"] is None and dune["owned"] == 0
    assert dune["published"] == "1990"
    emma = rows[2]
    assert emma["wishlist"] is True and emma["status"] is None
    persuasion = rows[3]
    assert persuasion["status"] == "want" and persuasion["wishlist"] is False
    assert persuasion["copy"] == {"format": "hardcover"}
    assert rows[4]["status"] == "dnf"
    assert rows[5]["status"] is None and rows[5]["tags"] == []
    assert all(r["needs_details"] for r in rows)


def test_parse_goodreads_falls_back_to_the_original_year() -> None:
    text = "Title,Year Published,Original Publication Year\nX,,1901\n"
    assert cio.parse_goodreads(text)[0]["published"] == "1901"


def test_parse_storygraph() -> None:
    rows = cio.parse(STORYGRAPH, "storygraph")
    dune = rows[0]
    assert dune["isbn13"] == "9780441013593" and dune["status"] == "read"
    assert dune["rating"] == 5 and dune["finished"] == "2024-02-01"
    assert dune["tags"] == ["sf", "classic"] and dune["notes"] == "Good"
    assert dune["owned"] == 1 and dune["copy"] == {"format": "paperback"}
    assert dune["read_count"] == 1
    assert rows[1]["wishlist"] is True and rows[1]["status"] is None
    assert rows[2]["status"] == "dnf" and rows[2]["rating"] == 2
    assert rows[2]["copy"] == {"format": "ebook"}
    assert rows[3]["status"] == "reading" and rows[3]["owned"] == 0


@pytest.mark.parametrize(
    ("value", "rating"),
    [("0", None), ("", None), ("x", None), ("0.4", 1), ("2.5", 3), ("9", 5)],
)
def test_rating(value: str, rating: int | None) -> None:
    assert cio._rating(value) == rating


def test_cell_helpers() -> None:
    assert cio._date("2024/3/5") == "2024-03-05"
    assert cio._date("2024-02-30") is None
    assert cio._date("soon") is None
    assert cio._int(" 7 ") == 7 and cio._int("7.0") is None
    assert cio._float("nan") is None and cio._float("inf") is None
    assert cio._float("1.5") == 1.5
    assert cio._split("a, b,,a") == ["a", "b"]
    assert cio._money_cell("12.0") == 12 and cio._money_cell("-1") is None
    assert cio._money_cell("1.25") == 1.25 and cio._money_cell("") is None
    assert cio._bool_cell("Yes") and cio._bool_cell("true")
    assert not cio._bool_cell("no")


def test_parse_errors() -> None:
    with pytest.raises(m.LibraryError) as info:
        cio.parse("Name,Author\nx,y\n", "goodreads")
    assert info.value.key == "csv_unreadable"
    assert info.value.placeholders == {"column": "Title"}
    with pytest.raises(m.LibraryError) as info:
        cio.parse("Title\nx\n", "kindle")
    assert info.value.key == "invalid_choice"
    with pytest.raises(m.LibraryError):
        cio.parse("title\n", "goodreads")
    with pytest.raises(m.LibraryError):
        cio.parse("", "goodreads")


def test_parse_library_round_trip() -> None:
    rows = cio.parse_library("title,format,location\nX,scroll,Den / Left\n")
    assert rows[0]["copy"] is None and rows[0]["location"] == ["Den", "Left"]
    assert rows[0]["needs_details"] is False


# ── Import ───────────────────────────────────────────────────────────────────


BOOK_HEX = "0123456789abcdef0123456789abcdef"


def _library() -> dict:
    state = m.empty_state()
    state["rooms"]["r"] = {"id": "r", "name": "Den", "order": 0}
    state["bookcases"]["k"] = {"id": "k", "room_id": "r", "name": "Left", "order": 0}
    state["shelves"]["s"] = {"id": "s", "bookcase_id": "k", "name": "Top", "order": 0}
    book = m.build_book({"title": "Persuasion", "authors": ["Jane Austen"]}, now=NOW)
    book["id"] = "persuasion"
    state["books"]["persuasion"] = book
    return state


def test_apply_goodreads_import() -> None:
    state = _library()
    rows = cio.parse(GOODREADS, "goodreads")
    new, summary, results, lookup = cio.apply_import(
        state,
        rows,
        person_id="p",
        shelf_id="s",
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert state["books"].keys() == {"persuasion"}, "the input must not change"
    assert summary == {
        "rows": 6,
        "read": 1,
        "reading": 1,
        "want": 1,
        "dnf": 1,
        "wishlist": 1,
        "copies": 2,
        "tags": 1,
        "errors": 0,
        "existing": 0,
        "new": 5,
        "title_match": 1,
        "reading_kept": 0,
    }
    assert [r["action"] for r in results] == [
        "new",
        "new",
        "new",
        "title_match",
        "new",
        "new",
    ]
    assert results[3]["book_id"] == "persuasion"
    assert results[0] == {
        "line": 1,
        "title": "The Left Hand of Darkness",
        "authors": ["Ursula K. Le Guin"],
        "isbn": "9780441478125",
        "book_id": results[0]["book_id"],
        "action": "new",
    }
    assert cio.summary_of(summary, 2) == {
        "rows": 6,
        "books_added": 5,
        "books_matched": 1,
        "copies_added": 2,
        "reading_set": 4,
        "reading_kept": 2,
        "wishlist_added": 1,
        "errors": 0,
    }
    assert len(lookup) == 5
    left = next(b for b in new["books"].values() if b["isbn13"] == "9780441478125")
    assert left["needs_details"] is True and left["tags"] == ["favorites"]
    copies = [c for c in new["copies"].values() if c["book_id"] == left["id"]]
    assert len(copies) == 1 and copies[0]["shelf_id"] == "s"
    assert copies[0]["format"] == "paperback"
    reading = new["reading"]["p"][left["id"]]
    assert reading["status"] == "read" and reading["read_count"] == 2
    assert reading["private_notes"] == "Great\nbook\n\nMine"
    emma = next(b for b in new["books"].values() if b["title"] == "Emma")
    assert emma["wishlist"]["person_id"] == "p" and emma["wishlist"]["buy"] is False
    assert emma["id"] not in new["reading"]["p"]


def test_import_matches_and_keeps_reading() -> None:
    state = _library()
    state["reading"]["p"] = {"persuasion": {**m.empty_reading(now=NOW)}}
    rows = cio.parse(GOODREADS, "goodreads")
    first, _, _, _ = cio.apply_import(
        state,
        rows,
        person_id="p",
        shelf_id="missing",
        import_notes=False,
        replace_reading=False,
        now=NOW,
    )
    assert first["reading"]["p"]["persuasion"]["status"] == "want"
    left = next(b for b in first["books"].values() if b["isbn13"] == "9780441478125")
    assert first["reading"]["p"][left["id"]]["private_notes"] == ""
    copy = next(c for c in first["copies"].values() if c["book_id"] == left["id"])
    assert copy["shelf_id"] is None
    _second, summary, _results, lookup = cio.apply_import(
        first,
        rows,
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert summary["new"] == 0 and summary["existing"] == 1
    assert summary["title_match"] == 5
    assert summary["copies"] == 0 and summary["reading_kept"] == 4
    assert summary["read"] + summary["reading"] + summary["want"] == 0
    assert summary["wishlist"] == 0
    assert lookup == []
    third, summary, _, _ = cio.apply_import(
        first,
        rows,
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=True,
        now=NOW,
    )
    assert summary["read"] + summary["want"] + summary["dnf"] == 3
    assert summary["reading"] == 1 and summary["reading_kept"] == 0
    assert third["reading"]["p"][left["id"]]["private_notes"] == "Great\nbook\n\nMine"


def test_import_row_error_and_empty_person() -> None:
    state = _library()
    rows = [cio.empty_row(1)]
    new, summary, results, _ = cio.apply_import(
        state,
        rows,
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert summary["errors"] == 1 and results[0]["action"] == "error"
    assert results[0]["error"] == "field_required"
    assert results[0]["placeholders"] == {"field": "title"}
    assert "p" not in new["reading"]


def test_import_library_rows_use_ids_and_locations() -> None:
    state = _library()
    book = state["books"].pop("persuasion")
    book["id"] = BOOK_HEX
    state["books"][BOOK_HEX] = book
    copy = m.build_copy({"book_id": BOOK_HEX, "shelf_id": "s"}, now=NOW)
    state["copies"][copy["id"]] = copy
    text = cio.export(state, None, "library")
    new, summary, _, _ = cio.apply_import(
        m.empty_state()
        | {
            "shelves": state["shelves"],
            "bookcases": state["bookcases"],
            "rooms": state["rooms"],
        },
        cio.parse(text, "library"),
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert summary["new"] == 1 and summary["copies"] == 1
    assert new["books"][BOOK_HEX]["title"] == "Persuasion"
    assert new["copies"][copy["id"]]["shelf_id"] == "s"
    _, again, _, _ = cio.apply_import(
        new,
        cio.parse(text, "library"),
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert again["copies"] == 0 and again["existing"] == 1


def test_import_library_ids_that_are_not_record_ids_are_dropped() -> None:
    header = "book_id,copy_id,title,format\n"
    rows = cio.parse(
        header
        + "../../evil,x,Escape,paperback\n"
        + f"{BOOK_HEX},{BOOK_HEX.upper()},Upper,paperback\n"
        + f"{BOOK_HEX}0,{BOOK_HEX},Long,paperback\n"
        + f"{BOOK_HEX},{BOOK_HEX},Good,paperback\n",
        "library",
    )
    assert [(r["book_id"], r["copy"]["id"]) for r in rows] == [
        (None, None),
        (BOOK_HEX, None),
        (None, BOOK_HEX),
        (BOOK_HEX, BOOK_HEX),
    ]


def test_import_row_with_a_bad_copy_adds_no_book() -> None:
    rows = cio.parse("title,format,condition\nPersuasion,paperback,mint\n", "library")
    new, summary, results, lookup = cio.apply_import(
        m.empty_state(),
        rows,
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=False,
        now=NOW,
    )
    assert results[0]["action"] == "error"
    assert results[0]["error"] == "invalid_choice"
    assert summary["errors"] == 1 and summary["new"] == 0
    assert new["books"] == {} and new["copies"] == {} and lookup == []


def test_import_sets_the_reading_of_a_book_once() -> None:
    state = _library()
    for _ in range(2):
        copy = m.build_copy({"book_id": "persuasion"}, now=NOW)
        state["copies"][copy["id"]] = copy
    state["reading"]["p"] = {
        "persuasion": m.empty_reading(now=NOW) | {"status": "read"}
    }
    text = cio.export(state, "p", "library")
    for replace, read, kept in ((False, 1, 0), (True, 1, 0)):
        _, summary, _, _ = cio.apply_import(
            m.empty_state(),
            cio.parse(text, "library"),
            person_id="p",
            shelf_id=None,
            import_notes=True,
            replace_reading=replace,
            now=NOW,
        )
        assert summary["rows"] == 2
        assert (summary["read"], summary["reading_kept"]) == (read, kept)


# ── Export ───────────────────────────────────────────────────────────────────


def test_export_goodreads_header_and_cells() -> None:
    state = _library()
    state["books"]["persuasion"]["isbn13"] = "9780441478125"
    state["books"]["persuasion"]["isbn10"] = "0441478123"
    copy = m.build_copy({"book_id": "persuasion", "format": "audiobook"}, now=NOW)
    state["copies"][copy["id"]] = copy
    state["reading"]["p"] = {
        "persuasion": {
            **m.empty_reading(now=NOW),
            "status": "read",
            "rating": 4,
            "finished": "2024-01-02",
            "read_count": 1,
        }
    }
    text = cio.export(state, "p", "goodreads")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    assert tuple(reader.fieldnames or ()) == cio.GOODREADS_COLUMNS
    row = next(reader)
    assert row["ISBN13"] == '="9780441478125"' and row["ISBN"] == '="0441478123"'
    assert row["Exclusive Shelf"] == "read" and row["Bookshelves"] == "read"
    assert row["Date Read"] == "2024/01/02" and row["My Rating"] == "4"
    assert row["Binding"] == "Audible Audio" and row["Owned Copies"] == "1"
    assert row["Author"] == "Jane Austen" and row["Author l-f"] == "Austen, Jane"
    no_person = next(csv.DictReader(io.StringIO(cio.export(state, None, "goodreads"))))
    assert no_person["Exclusive Shelf"] == "" and no_person["Read Count"] == ""
    assert cio.export_filename("library", "2026-10-05") == (
        "library-library-2026-10-05.csv"
    )
    with pytest.raises(m.LibraryError):
        cio.write([], "kindle")


def test_export_wishlist_is_to_read() -> None:
    state = _library()
    state["books"]["persuasion"]["wishlist"] = m.build_wishlist("p", buy=True, now=NOW)
    row = next(csv.DictReader(io.StringIO(cio.export(state, "p", "goodreads"))))
    assert row["Exclusive Shelf"] == "to-read" and row["Owned Copies"] == "0"
    other = next(csv.DictReader(io.StringIO(cio.export(state, "q", "goodreads"))))
    assert other["Exclusive Shelf"] == ""


def test_export_library_has_a_row_for_each_copy() -> None:
    state = _library()
    for stamp, fmt in (("t1", "hardcover"), ("t2", "ebook")):
        copy = m.build_copy({"book_id": "persuasion", "format": fmt}, now=stamp)
        state["copies"][copy["id"]] = copy
    rows = cio.rows_from_state(state, None, "library")
    assert [r["copy"]["format"] for r in rows] == ["hardcover", "ebook"]
    assert [r["line"] for r in rows] == [1, 2]
    assert len(cio.rows_from_state(state, None, "goodreads")) == 1


# ── Round trips ──────────────────────────────────────────────────────────────

_WORD = st.text(
    alphabet=string.ascii_letters + string.digits + "éüß'\"", min_size=1, max_size=12
)
_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\r﻿")
    | st.sampled_from(["\n", ",", '"']),
    max_size=40,
).map(str.strip)
_NAME = st.lists(_WORD, min_size=1, max_size=3).map(" ".join)
_DATE = st.dates(min_value=__import__("datetime").date(1900, 1, 1)).map(
    lambda d: d.isoformat()
)
_ISBN = st.text(alphabet="0123456789", min_size=9, max_size=9).map(
    lambda d: isbn_mod.normalize(d + isbn_mod.isbn10_check_char(d))
)
_TAG = st.text(alphabet=string.ascii_lowercase + "-", min_size=1, max_size=10).filter(
    lambda t: t not in ("read", "currently-reading", "to-read", "did-not-finish")
)


@st.composite
def _goodreads_row(draw) -> dict:
    row = cio.empty_row(1)
    row["title"] = draw(_TEXT.filter(bool))
    row["authors"] = draw(st.lists(_NAME, min_size=0, max_size=3, unique=True))
    isbns = draw(st.none() | _ISBN)
    if isbns:
        row["isbn13"], row["isbn10"] = isbns
    row["publisher"] = draw(_TEXT)
    row["published"] = draw(st.sampled_from(["", "1969", "2001"]))
    row["pages"] = draw(st.none() | st.integers(min_value=1, max_value=5000))
    owned = draw(st.integers(min_value=0, max_value=3))
    row["owned"] = owned
    if owned:
        row["copy"] = {"format": draw(st.sampled_from(m.FORMATS))}
    status = draw(st.sampled_from([None, *m.STATUSES]))
    if status == "want" and not owned:
        row["wishlist"] = True
        status = None
    elif status is None and not owned:
        row["wishlist"] = draw(st.booleans())
    row["status"] = status
    row["tags"] = draw(st.lists(_TAG, max_size=3, unique=True))
    if status is not None:
        row["rating"] = draw(st.none() | st.integers(min_value=1, max_value=5))
        row["read_count"] = draw(st.integers(min_value=0, max_value=9))
        if status == "read":
            row["finished"] = draw(st.none() | _DATE)
    row["notes"] = draw(_TEXT)
    return row


@settings(max_examples=150, deadline=None)
@given(st.lists(_goodreads_row(), min_size=1, max_size=5))
def test_goodreads_round_trip(rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        row["line"] = index
    again = cio.parse(cio.write(rows, "goodreads"), "goodreads")
    assert again == rows


@st.composite
def _library_row(draw) -> dict:
    row = cio.empty_row(1)
    row["needs_details"] = False
    row["book_id"] = draw(st.uuids()).hex
    row["title"] = draw(_TEXT.filter(bool))
    for field in ("subtitle", "publisher", "description", "shared_notes"):
        row[field] = draw(_TEXT)
    row["published"] = draw(st.sampled_from(["", "1969", "c. 1900"]))
    row["authors"] = draw(st.lists(_NAME, max_size=3, unique=True))
    row["subjects"] = draw(st.lists(_NAME, max_size=3, unique=True))
    row["tags"] = draw(st.lists(_TAG, max_size=3, unique=True))
    isbns = draw(st.none() | _ISBN)
    if isbns:
        row["isbn13"], row["isbn10"] = isbns
    row["pages"] = draw(st.none() | st.integers(min_value=1, max_value=5000))
    row["language"] = draw(st.sampled_from([None, "en", "de"]))
    if draw(st.booleans()):
        row["series"] = {"name": draw(_NAME), "number": draw(st.none() | st.just("2"))}
    if draw(st.booleans()):
        row["copy"] = {
            "id": draw(st.uuids()).hex,
            "format": draw(st.sampled_from(m.FORMATS)),
            "condition": draw(st.sampled_from([None, *m.CONDITIONS])),
            "acquired": draw(st.none() | _DATE),
            "acquired_from": draw(_TEXT),
            "price": draw(st.none() | st.integers(0, 500) | st.just(9.5)),
            "value": draw(st.none() | st.integers(0, 500)),
            "signed": draw(st.booleans()),
            "first_edition": draw(st.booleans()),
            "note": draw(_TEXT),
        }
        row["owned"] = 1
        row["location"] = draw(st.just([]) | st.lists(_NAME, min_size=3, max_size=3))
    status = draw(st.sampled_from([None, *m.STATUSES]))
    row["status"] = status
    if status is not None:
        row["rating"] = draw(st.none() | st.integers(min_value=1, max_value=5))
        row["page"] = draw(st.none() | st.integers(min_value=0, max_value=900))
        row["started"] = draw(st.none() | _DATE)
        row["finished"] = draw(st.none() | _DATE)
        row["read_count"] = draw(st.none() | st.integers(min_value=0, max_value=9))
    row["notes"] = draw(_TEXT)
    row["wishlist"] = draw(st.booleans())
    row["wishlist_buy"] = row["wishlist"] and draw(st.booleans())
    return row


@settings(max_examples=150, deadline=None)
@given(st.lists(_library_row(), min_size=1, max_size=5))
def test_library_round_trip(rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        row["line"] = index
    again = cio.parse(cio.write(rows, "library"), "library")
    assert again == rows


@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        _library_row(),
        min_size=1,
        max_size=5,
        unique_by=(
            lambda r: m.title_key(r["title"], r["authors"]),
            lambda r: r["isbn13"] or r["book_id"],
        ),
    )
)
def test_state_export_import_export_is_stable(rows: list[dict]) -> None:
    """Import a library CSV into an empty library, export it, and compare.

    The titles differ, because 2 rows with the same title and author are 1 book.
    """
    for index, row in enumerate(rows, start=1):
        row["line"] = index
        row["location"] = []
    state, _, _, _ = cio.apply_import(
        m.empty_state(),
        rows,
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=True,
        now=NOW,
    )
    first = cio.export(state, "p", "library")
    rebuilt, _, _, _ = cio.apply_import(
        m.empty_state(),
        cio.parse(first, "library"),
        person_id="p",
        shelf_id=None,
        import_notes=True,
        replace_reading=True,
        now=NOW,
    )
    assert cio.export(rebuilt, "p", "library") == first
