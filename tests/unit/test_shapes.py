"""Exact shapes of the records and replies that the pure core builds.

A round trip passes when a key has a wrong name on both sides. These tests pin
each key and each default, so a renamed key or a changed default fails.
"""

from __future__ import annotations

import ex.csv_io as cio
import ex.models as m
import ex.openlibrary as ol
import ex.projections as pr
import pytest

NOW = "2026-10-05T12:00:00+00:00"


def _raises(fn, *args, **kwargs) -> m.LibraryError:
    with pytest.raises(m.LibraryError) as info:
        fn(*args, **kwargs)
    return info.value


def test_empty_row() -> None:
    assert cio.empty_row(7) == {
        "line": 7,
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


def test_build_book_shape() -> None:
    book = m.build_book({"title": "Dune"}, now=NOW)
    assert book == {
        "id": book["id"],
        "title": "Dune",
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
        "lookup_tries": 0,
        "created_at": NOW,
        "updated_at": NOW,
        "wishlist": None,
    }


def test_location_shapes() -> None:
    room = m.build_room({"name": "Den", "area_id": "office"}, order=2)
    assert room == {"id": room["id"], "name": "Den", "area_id": "office", "order": 2}
    case = m.build_bookcase({"room_id": "r", "name": "Left"}, order=1)
    assert case == {
        "id": case["id"],
        "room_id": "r",
        "name": "Left",
        "note": "",
        "order": 1,
    }
    shelf = m.build_shelf({"bookcase_id": "k", "name": "Top", "order": 4}, order=0)
    assert shelf == {"id": shelf["id"], "bookcase_id": "k", "name": "Top", "order": 4}


def test_copy_and_loan_shapes() -> None:
    copy = m.build_copy({"book_id": "b"}, now=NOW)
    assert copy == {
        "id": copy["id"],
        "book_id": "b",
        "shelf_id": None,
        "format": "paperback",
        "condition": None,
        "acquired": None,
        "acquired_from": "",
        "price": None,
        "value": None,
        "signed": False,
        "first_edition": False,
        "note": "",
        "created_at": NOW,
    }
    loan = m.build_loan(
        {"direction": "out", "copy_id": "c", "book_id": "b", "party": " Al "},
        today="2026-10-05",
    )
    assert loan == {
        "id": loan["id"],
        "direction": "out",
        "book_id": "b",
        "copy_id": "c",
        "party": "Al",
        "person_id": None,
        "format": None,
        "started": "2026-10-05",
        "due": None,
        "returned": None,
        "note": "",
        "hk_task_id": None,
        "add_task": True,
        "overdue_fired": False,
    }
    err = _raises(m.build_loan, {}, today="x")
    assert err.key == "invalid_choice" and err.placeholders["field"] == "direction"
    err = _raises(
        m.build_loan,
        {"direction": "out", "copy_id": "c", "party": "x"},
        today="2026-10-05",
    )
    assert err.placeholders == {"field": "book_id"}
    err = _raises(
        m.build_loan,
        {"direction": "out", "copy_id": "c", "book_id": "b", "party": "x", "due": 3},
        today="2026-10-05",
    )
    assert err.key == "invalid_date" and err.placeholders == {"field": "due"}
    err = _raises(
        m.build_loan,
        {"direction": "out", "copy_id": "c", "book_id": "b", "party": "x", "note": 5j},
        today="2026-10-05",
    )
    assert err.placeholders == {"field": "note"}
    loan = m.build_loan(
        {
            "direction": "in",
            "book_id": "b",
            "party": "x",
            "person_id": "p",
            "copy_id": "c",
            "started": "2026-01-01",
            "note": "n",
        },
        today="2026-10-05",
    )
    assert loan["copy_id"] is None and loan["started"] == "2026-01-01"
    assert loan["note"] == "n"


def test_field_names_in_errors() -> None:
    def key(fn, *args, **kwargs):
        with pytest.raises(m.LibraryError) as info:
            fn(*args, **kwargs)
        return info.value.key, info.value.placeholders

    assert key(m.build_room, {"name": "x", "area_id": []}, order=0) == (
        "invalid_field",
        {"field": "area_id"},
    )
    assert key(m.build_bookcase, {"room_id": "r", "name": "x", "note": []}, order=0)[
        1
    ] == {"field": "note"}
    assert key(m.build_shelf, {"bookcase_id": "k", "name": ""}, order=0)[1] == {
        "field": "name"
    }
    assert key(m.build_copy, {"book_id": "b", "price": -1}, now=NOW)[1]["field"] == (
        "price"
    )
    assert key(m.build_copy, {"book_id": "b", "value": "x"}, now=NOW)[1] == {
        "field": "value"
    }
    assert key(m.copy_field, "condition", "mint")[1]["field"] == "condition"
    assert key(m.copy_field, "acquired", "soon")[1] == {"field": "acquired"}
    assert key(m.copy_field, "signed", 1)[1] == {"field": "signed"}
    assert key(m.copy_field, "note", [])[1] == {"field": "note"}
    assert key(m.copy_field, "acquired_from", [])[1] == {"field": "acquired_from"}
    assert key(m.book_field, "openlibrary", {"cover_id": 0})[1]["field"] == (
        "openlibrary"
    )
    assert key(m.book_field, "openlibrary", 3)[1] == {"field": "openlibrary"}
    assert key(m.book_field, "series", [1])[1] == {"field": "series"}
    assert key(m.book_field, "language", [])[1] == {"field": "language"}
    assert key(m.book_field, "needs_details", "yes")[1] == {"field": "needs_details"}
    assert key(m.book_field, "authors", 3)[1] == {"field": "authors"}
    assert key(m.reading_field, "started", "x")[1] == {"field": "started"}
    assert key(m.reading_field, "page", -1)[1]["field"] == "page"
    assert key(m.reading_field, "private_notes", [])[1] == {"field": "private_notes"}
    assert key(m.update_location, "room", {"name": "a"}, {"area_id": []})[1] == {
        "field": "area_id"
    }
    assert key(m.update_location, "room", {"name": "a"}, {"order": "x"})[1] == {
        "field": "order"
    }
    assert key(m.update_location, "bookcase", {"name": "a"}, {"note": []})[1] == {
        "field": "note"
    }
    assert key(m.update_location, "room", {"name": "a"}, {"name": "b" * 101})[1] == {
        "field": "name",
        "max": "100",
    }
    loan = {"started": "2026-10-01", "due": None}
    assert key(m.update_loan, loan, {"party": ""})[1] == {"field": "party"}
    assert key(m.update_loan, loan, {"note": []})[1] == {"field": "note"}
    assert key(m.update_loan, loan, {"format": "x"})[1]["field"] == "format"
    assert key(m.update_loan, loan, {"due": "x"})[1] == {"field": "due"}
    assert key(m.apply_person_settings, {}, {"share_reading": 1})[1] == {
        "field": "share_reading"
    }
    assert key(m.apply_person_settings, {}, {"yearly_goal": 0})[1]["field"] == (
        "yearly_goal"
    )


def test_openlibrary_block() -> None:
    assert m.book_field("openlibrary", {"edition_key": "OL1M"}) == {
        "edition_key": "OL1M",
        "work_key": None,
        "cover_id": None,
    }
    assert m.book_field("openlibrary", {"cover_id": "12"})["cover_id"] == 12
    assert m.book_field("series", {"name": "D", "number": 2.5}) == {
        "name": "D",
        "number": "2.5",
    }


def test_parse_search_doc_shape() -> None:
    doc = {
        "key": "/works/OL5W",
        "title": "T",
        "subtitle": "S",
        "author_name": ["A"],
        "isbn": ["bad", "9791032305690", "0441478123"],
        "edition_key": ["OL1M"],
        "publisher": ["P"],
        "first_publish_year": 2001,
        "number_of_pages_median": 10,
        "language": ["ger"],
        "subject": ["x"],
        "cover_i": 3,
    }
    assert ol.parse_search_doc(doc) == {
        "title": "T",
        "subtitle": "S",
        "authors": ["A"],
        "isbn13": "9780441478125",
        "isbn10": "0441478123",
        "publisher": "P",
        "published": "2001",
        "pages": 10,
        "language": "de",
        "subjects": ["x"],
        "series": None,
        "description": "",
        "openlibrary": {"edition_key": "OL1M", "work_key": "OL5W", "cover_id": 3},
    }
    empty = ol.parse_search_doc({})
    assert empty["isbn10"] is None and empty["published"] == ""
    assert empty["publisher"] == "" and empty["openlibrary"]["edition_key"] is None


def _two_books() -> dict:
    state = m.empty_state()
    for book_id, title, stamp in (("z", "Apple", "t2"), ("a", "Zed", "t1")):
        book = m.build_book({"title": title}, now=stamp)
        book["id"] = book_id
        state["books"][book_id] = book
    for copy_id, stamp in (("c2", "t1"), ("c1", "t2")):
        copy = m.build_copy({"book_id": "a"}, now=stamp)
        copy["id"] = copy_id
        state["copies"][copy_id] = copy
    state["reading"]["p"] = {"a": {**m.empty_reading(now=NOW), "status": "read"}}
    return state


def test_rows_from_state_order_and_reading() -> None:
    state = _two_books()
    rows = cio.rows_from_state(state, "p", "library")
    assert [(r["book_id"], (r["copy"] or {}).get("id")) for r in rows] == [
        ("z", None),
        ("a", "c2"),
        ("a", "c1"),
    ]
    assert [r["line"] for r in rows] == [1, 2, 3]
    assert rows[1]["status"] == "read" and rows[0]["status"] is None
    assert cio.rows_from_state(state, None, "library")[1]["status"] is None
    goodreads = cio.rows_from_state(state, "p", "goodreads")
    assert [r["owned"] for r in goodreads] == [0, 2]
    assert goodreads[1]["copy"] == {"format": "paperback"}


def test_cells() -> None:
    row = cio.empty_row(1)
    row.update(
        title="T",
        authors=["Ann Lee", "Bo"],
        isbn13="9780441478125",
        isbn10="0441478123",
        status="read",
        rating=4,
        finished="2026-01-02",
        read_count=2,
        tags=["fav"],
        owned=1,
        copy={"format": "ebook"},
        notes="n",
        pages=5,
        publisher="P",
        published="2001",
    )
    assert cio._goodreads_cells(row) == {
        "Book Id": "",
        "Title": "T",
        "Author": "Ann Lee",
        "Author l-f": "Lee, Ann",
        "Additional Authors": "Bo",
        "ISBN": '="0441478123"',
        "ISBN13": '="9780441478125"',
        "My Rating": "4",
        "Average Rating": "",
        "Publisher": "P",
        "Binding": "Kindle Edition",
        "Number of Pages": "5",
        "Year Published": "2001",
        "Original Publication Year": "",
        "Date Read": "2026/01/02",
        "Date Added": "",
        "Bookshelves": "read, fav",
        "Bookshelves with positions": "",
        "Exclusive Shelf": "read",
        "My Review": "",
        "Spoiler": "",
        "Private Notes": "n",
        "Read Count": "2",
        "Owned Copies": "1",
    }
    plain = cio._goodreads_cells(cio.empty_row(1))
    assert plain["ISBN"] == '=""' and plain["My Rating"] == "0"
    assert plain["Bookshelves"] == "" and plain["Binding"] == ""
    assert plain["Owned Copies"] == "0" and plain["Read Count"] == ""
    assert plain["Author l-f"] == "" and plain["Number of Pages"] == ""
    row.update(
        book_id="b",
        series={"name": "S", "number": "2"},
        copy={
            "id": "c",
            "format": "ebook",
            "condition": "good",
            "acquired": "2020-01-01",
            "acquired_from": "Shop",
            "price": 3,
            "value": None,
            "signed": True,
            "first_edition": False,
            "note": "cn",
        },
        location=["R", "B", "S"],
        page=9,
        started="2025-12-01",
        wishlist=True,
        wishlist_buy=False,
        language="en",
        subjects=["x", "y"],
        subtitle="Sub",
        description="D",
        shared_notes="sn",
    )
    assert cio._library_cells(row) == {
        "book_id": "b",
        "title": "T",
        "subtitle": "Sub",
        "authors": "Ann Lee; Bo",
        "isbn13": "9780441478125",
        "isbn10": "0441478123",
        "publisher": "P",
        "published": "2001",
        "pages": "5",
        "language": "en",
        "subjects": "x; y",
        "series": "S",
        "series_number": "2",
        "description": "D",
        "tags": "fav",
        "shared_notes": "sn",
        "copy_id": "c",
        "format": "ebook",
        "condition": "good",
        "acquired": "2020-01-01",
        "acquired_from": "Shop",
        "price": "3",
        "value": "",
        "signed": "true",
        "first_edition": "false",
        "copy_note": "cn",
        "location": "R / B / S",
        "status": "read",
        "rating": "4",
        "page": "9",
        "started": "2025-12-01",
        "finished": "2026-01-02",
        "read_count": "2",
        "private_notes": "n",
        "wishlist": "true",
        "wishlist_buy": "false",
    }
    empty = cio._library_cells(cio.empty_row(1))
    assert empty["signed"] == "" and empty["first_edition"] == ""
    assert empty["book_id"] == "" and empty["series"] == ""
    assert empty["wishlist"] == "false" and empty["format"] == ""


def test_project_state_counts_and_order() -> None:
    state = _two_books()
    state["rooms"] = {
        "r2": {"id": "r2", "name": "b", "order": 0},
        "r1": {"id": "r1", "name": "a", "order": 0},
    }
    state["bookcases"] = {
        "k1": {"id": "k1", "room_id": "r2", "name": "x", "order": 0},
        "k2": {"id": "k2", "room_id": "r1", "name": "y", "order": 5},
        "k3": {"id": "k3", "room_id": "r1", "name": "z", "order": 1},
    }
    reply = pr.project_state(
        state,
        persons=[],
        viewer=None,
        is_admin=True,
        currency="EUR",
        tab=False,
        revision=0,
    )
    assert [r["id"] for r in reply["rooms"]] == ["r1", "r2"]
    assert [b["id"] for b in reply["bookcases"]] == ["k3", "k2", "k1"]
    zed = next(b for b in reply["books"] if b["id"] == "a")
    assert zed["copy_count"] == 2 and zed["owned"] is True
    assert [c["id"] for c in reply["copies"]] == ["c2", "c1"]
    assert reply["me"] == {"person_id": None, "name": None, "is_admin": True}


def test_book_matches_joins_fields_with_a_space() -> None:
    state = m.empty_state()
    book = m.build_book({"title": "Dune", "subtitle": "Deluxe"}, now=NOW)
    state["books"][book["id"]] = book
    assert pr.book_matches(state, book, {"query": "dune deluxe"})
    assert not pr.book_matches(state, book, {"query": "dunedeluxe"})
    book["series"] = {"name": "Chronicles", "number": None}
    assert pr.book_matches(state, book, {"query": "chronicles"})


def test_book_detail_order_and_projection() -> None:
    state = _two_books()
    state["loans"] = {
        "l2": {"id": "l2", "book_id": "a", "started": "2026-02-01", "party": "X"},
        "l1": {"id": "l1", "book_id": "a", "started": "2026-01-01", "party": "Y"},
        "l3": {"id": "l3", "book_id": "z", "started": "2026-01-01", "party": "Z"},
    }
    state["reading"]["q"] = {"a": {**m.empty_reading(now=NOW), "private_notes": "s"}}
    detail = pr.book_detail(state, "a", viewer="p", is_admin=False)
    assert [c["id"] for c in detail["copies"]] == ["c2", "c1"]
    assert [lo["id"] for lo in detail["loans"]] == ["l1", "l2"]
    assert "private_notes" not in detail["reading"]["q"]
    assert "party" not in detail["loans"][0]


def test_cover_url_token() -> None:
    book = {"id": "b", "cover": {"kind": "custom", "file": "b-12ab34cd.jpg"}}
    assert pr.cover_url(book) == "/api/home_keeper_library/cover/b?v=12ab34cd"
