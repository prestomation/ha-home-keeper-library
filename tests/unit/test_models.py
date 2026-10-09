"""Unit tests for the pure data model."""

from __future__ import annotations

from datetime import date

import ex.models as m
import pytest

NOW = "2026-10-05T12:00:00+00:00"
TODAY = "2026-10-05"


def _err(fn, *args, **kwargs) -> m.LibraryError:
    with pytest.raises(m.LibraryError) as info:
        fn(*args, **kwargs)
    return info.value


# ── State ────────────────────────────────────────────────────────────────────


def test_empty_state_has_every_section() -> None:
    state = m.empty_state()
    assert set(state) == {*m.STATE_SECTIONS, "todo_orphans"}
    assert all(state[name] == {} for name in m.STATE_SECTIONS)
    assert state["todo_orphans"] == []


def test_normalize_state_fills_and_filters() -> None:
    assert m.normalize_state(None) == m.empty_state()
    raw = {
        "books": {
            "b": {"id": "b"},
            "t": {"id": "t", "lookup_tries": 2},
            "x": "not a book",
        },
        "rooms": [],
        "todo_orphans": [
            {"entity_id": "todo.a", "uid": "1"},
            {"entity_id": "todo.a"},
            "x",
            {"entity_id": 1, "uid": "2"},
        ],
    }
    state = m.normalize_state(raw)
    assert state["books"] == {
        "b": {"id": "b", "lookup_tries": 0},
        "t": {"id": "t", "lookup_tries": 2},
        "x": "not a book",
    }
    assert state["rooms"] == {}
    assert state["todo_orphans"] == [{"entity_id": "todo.a", "uid": "1"}]
    assert m.normalize_state({"todo_orphans": "x"})["todo_orphans"] == []


@pytest.mark.parametrize(
    ("value", "tries"),
    [(None, 0), (0, 0), (1, 1), (3, 3), (-1, 0), (True, 0), ("2", 0), (2.0, 0)],
)
def test_lookup_tries(value, tries) -> None:
    assert m.lookup_tries(value) == tries


def test_books_to_look_up() -> None:
    state = m.empty_state()
    base = {"needs_details": True, "isbn13": "9780441478125", "openlibrary": None}
    state["books"] = {
        "b_late": {**base, "id": "b_late", "created_at": "2", "lookup_tries": 2},
        "c_early": {**base, "id": "c_early", "created_at": "1"},
        "a_ten": {**base, "id": "a_ten", "isbn13": None, "isbn10": "0441478123"},
        "done": {**base, "id": "done", "lookup_tries": 3},
        "known": {**base, "id": "known", "openlibrary": {"work_key": "W"}},
        "noisbn": {**base, "id": "noisbn", "isbn13": None},
        "full": {**base, "id": "full", "needs_details": False},
    }
    state["books"]["a_ten"]["created_at"] = "3"
    assert m.books_to_look_up(state, 3) == ["c_early", "b_late", "a_ten"]
    assert m.books_to_look_up(state, 2) == ["c_early", "a_ten"]
    assert m.books_to_look_up(state, 4) == ["done", "c_early", "b_late", "a_ten"]
    state["books"]["b_late"]["created_at"] = "1"
    assert m.books_to_look_up(state, 3) == ["b_late", "c_early", "a_ten"]


def _merge_state(**sections):
    state = m.empty_state()
    for name, value in sections.items():
        state[name] = value
    return state


def test_merge_changes_writes_only_what_the_plan_changed() -> None:
    before = _merge_state(
        rooms={"r": {"id": "r", "name": "Den"}},
        books={
            "b": {"id": "b", "title": "Dune", "tags": [], "gone": 1},
            "same": {"id": "same", "title": "Same"},
            "drop": {"id": "drop", "title": "Drop"},
            "lost": {"id": "lost", "title": "Lost", "tags": []},
        },
    )
    after = m.clone(before)
    after["books"]["b"]["tags"] = ["sf"]
    after["books"]["b"]["series"] = {"name": "Dune"}
    del after["books"]["b"]["gone"]
    after["books"]["lost"]["tags"] = ["x"]
    del after["books"]["drop"]
    after["books"]["new"] = {"id": "new", "title": "New", "tags": ["a"]}
    after["books"]["taken"] = {"id": "taken", "title": "Mine"}
    current = m.clone(before)
    current["books"]["b"]["title"] = "Dune (edited)"
    current["books"]["same"]["title"] = "Same (edited)"
    del current["books"]["lost"]
    current["books"]["taken"] = {"id": "taken", "title": "Theirs"}
    current["rooms"]["r2"] = {"id": "r2", "name": "Attic"}
    kept = m.clone(current)
    merged = m.merge_changes(current, before, after)
    assert current == kept, "the merge must not change its input"
    assert merged["books"] == {
        "b": {
            "id": "b",
            "title": "Dune (edited)",
            "tags": ["sf"],
            "series": {"name": "Dune"},
        },
        "same": {"id": "same", "title": "Same (edited)"},
        "new": {"id": "new", "title": "New", "tags": ["a"]},
        "taken": {"id": "taken", "title": "Theirs"},
    }
    assert merged["rooms"] == current["rooms"]
    after["books"]["new"]["tags"].append("b")
    after["books"]["b"]["tags"].append("c")
    assert merged["books"]["new"]["tags"] == ["a"], "no alias of the plan"
    assert merged["books"]["b"]["tags"] == ["sf"], "no alias of the plan"


def test_merge_changes_keeps_links() -> None:
    books = {"b": {"id": "b"}, "gone": {"id": "gone"}}
    shelves = {"s": {"id": "s"}, "old": {"id": "old"}}
    before = _merge_state(books=dict(books), shelves=dict(shelves))
    before["reading"] = {"p": {"b": {"status": "want"}}}
    after = m.clone(before)
    after["copies"] = {
        "c1": {"id": "c1", "book_id": "b", "shelf_id": "s"},
        "c2": {"id": "c2", "book_id": "b", "shelf_id": "old"},
        "c3": {"id": "c3", "book_id": "gone", "shelf_id": None},
        "c4": {"id": "c4", "book_id": "b", "shelf_id": None},
    }
    after["reading"] = {
        "p": {"b": {"status": "read"}, "gone": {"status": "read"}},
        "q": {"gone": {"status": "want"}},
    }
    current = m.clone(before)
    del current["books"]["gone"]
    del current["shelves"]["old"]
    current["reading"]["p"]["other"] = {"status": "reading"}
    current["reading"]["r"] = {"x": {"status": "want"}}
    current["copies"]["mine"] = {"id": "mine", "book_id": "zzz", "shelf_id": "zz"}
    merged = m.merge_changes(current, before, after)
    assert merged["copies"] == {
        "c1": {"id": "c1", "book_id": "b", "shelf_id": "s"},
        "c2": {"id": "c2", "book_id": "b", "shelf_id": None},
        "c4": {"id": "c4", "book_id": "b", "shelf_id": None},
        "mine": {"id": "mine", "book_id": "zzz", "shelf_id": "zz"},
    }
    assert merged["reading"] == {
        "p": {"b": {"status": "read"}, "other": {"status": "reading"}},
        "r": {"x": {"status": "want"}},
    }


def test_merge_changes_removes_a_person_with_no_rows() -> None:
    before = _merge_state(books={"b": {"id": "b"}})
    before["reading"] = {"p": {"b": {"status": "want"}}}
    after = m.clone(before)
    after["reading"] = {}
    merged = m.merge_changes(m.clone(before), before, after)
    assert merged["reading"] == {}
    assert m.merge_changes(m.clone(before), before, m.clone(before)) == before


def test_merge_changes_when_the_current_data_already_lost_it() -> None:
    before = _merge_state(books={"b": {"id": "b", "x": 1}, "d": {"id": "d"}})
    after = _merge_state(books={"b": {"id": "b", "y": 2}})
    current = _merge_state(books={"b": {"id": "b"}})
    merged = m.merge_changes(current, before, after)
    assert merged["books"] == {"b": {"id": "b", "y": 2}}


def test_new_id_and_clone() -> None:
    first, second = m.new_id(), m.new_id()
    assert len(first) == 32 and first != second
    value = {"a": [1, {"b": 2}]}
    copy = m.clone(value)
    copy["a"][1]["b"] = 3
    assert value["a"][1]["b"] == 2


# ── Field checks ─────────────────────────────────────────────────────────────


def test_text() -> None:
    assert m.text("  a ", "f", 5) == "a"
    assert m.text(None, "f", 5) == ""
    assert m.text(12, "f", 5) == "12"
    assert m.text("abcde", "f", 5) == "abcde"
    assert _err(m.text, "abcdef", "f", 5).key == "field_too_long"
    assert _err(m.text, "abcdef", "f", 5).placeholders == {"field": "f", "max": "5"}
    assert _err(m.text, " ", "f", 5, required=True).key == "field_required"
    assert _err(m.text, [], "f", 5).key == "invalid_field"
    assert _err(m.text, True, "f", 5).key == "invalid_field"
    assert m.optional_text(" ", "f", 5) is None
    assert m.optional_text("x", "f", 5) == "x"


def test_str_list() -> None:
    assert m.str_list(None, "f") == []
    assert m.str_list("a", "f") == ["a"]
    assert m.str_list(["a", " a ", "", "b"], "f") == ["a", "b"]
    assert m.str_list(("x",), "f") == ["x"]
    assert _err(m.str_list, 3, "f").key == "invalid_field"
    assert len(m.str_list([str(i) for i in range(m.MAX_LIST)], "f")) == m.MAX_LIST
    too_many = [str(i) for i in range(m.MAX_LIST + 1)]
    assert _err(m.str_list, too_many, "f").key == "field_too_long"


def test_boolean() -> None:
    assert m.boolean(True, "f") is True
    assert m.boolean(False, "f") is False
    assert _err(m.boolean, 1, "f").key == "invalid_field"
    assert _err(m.boolean, "true", "f").key == "invalid_field"


def test_integer() -> None:
    assert m.integer(None, "f", low=0, high=5) is None
    assert m.integer("", "f", low=0, high=5) is None
    assert m.integer(3, "f", low=0, high=5) == 3
    assert m.integer(3.0, "f", low=0, high=5) == 3
    assert m.integer(" 4 ", "f", low=0, high=5) == 4
    assert m.integer(0, "f", low=0, high=5) == 0
    assert m.integer(5, "f", low=0, high=5) == 5
    assert _err(m.integer, 6, "f", low=0, high=5).key == "out_of_range"
    assert _err(m.integer, -1, "f", low=0, high=5).placeholders == {
        "field": "f",
        "low": "0",
        "high": "5",
    }
    assert _err(m.integer, True, "f", low=0, high=5).key == "invalid_field"
    assert _err(m.integer, 2.5, "f", low=0, high=5).key == "invalid_field"
    assert _err(m.integer, "x", "f", low=0, high=5).key == "invalid_field"
    assert m.integer("-0", "f", low=0, high=5) == 0
    for bad in ("--5", "²", "4-", "-"):
        assert _err(m.integer, bad, "f", low=0, high=5).key == "invalid_field"
    err = _err(m.integer, None, "f", low=0, high=5, nullable=False)
    assert err.key == "field_required"


def test_money() -> None:
    assert m.money(None, "f") is None
    assert m.money("", "f") is None
    assert m.money(10, "f") == 10
    assert m.money(10.0, "f") == 10 and isinstance(m.money(10.0, "f"), int)
    assert m.money(9.5, "f") == 9.5
    assert m.money(" 2.25 ", "f") == 2.25
    assert m.money(0, "f") == 0
    assert m.money(m.MAX_MONEY, "f") == m.MAX_MONEY
    assert _err(m.money, -1, "f").key == "out_of_range"
    assert _err(m.money, m.MAX_MONEY + 1, "f").key == "out_of_range"
    assert _err(m.money, float("nan"), "f").key == "invalid_field"
    assert _err(m.money, float("inf"), "f").key == "invalid_field"
    assert _err(m.money, "abc", "f").key == "invalid_field"
    assert _err(m.money, True, "f").key == "invalid_field"
    assert _err(m.money, [1], "f").key == "invalid_field"


def test_iso_date() -> None:
    assert m.iso_date(None, "f") is None
    assert m.iso_date("", "f") is None
    assert m.iso_date(date(2026, 1, 2), "f") == "2026-01-02"
    assert m.iso_date("2026-01-02T10:00:00", "f") == "2026-01-02"
    assert m.iso_date(" 2026-01-02 ", "f") == "2026-01-02"
    assert _err(m.iso_date, "2026-13-01", "f").key == "invalid_date"
    assert _err(m.iso_date, 20260101, "f").key == "invalid_date"


def test_choice_and_entity_id() -> None:
    assert m.choice("a", "f", ("a", "b")) == "a"
    err = _err(m.choice, "c", "f", ("a", "b"))
    assert err.key == "invalid_choice"
    assert err.placeholders["options"] == "a, b"
    assert m.entity_id_or_none(None, "f", "todo") is None
    assert m.entity_id_or_none("", "f", "todo") is None
    assert m.entity_id_or_none("todo.shop_1", "f", "todo") == "todo.shop_1"
    for bad in ("light.x", "todo.", "todo.A", 3, "xtodo.a"):
        assert _err(m.entity_id_or_none, bad, "f", "todo").key == "invalid_field"


# ── Locations ────────────────────────────────────────────────────────────────


def test_build_locations() -> None:
    room = m.build_room({"name": " Den ", "area_id": ""}, order=4)
    assert room["name"] == "Den" and room["area_id"] is None and room["order"] == 4
    assert m.build_room({"name": "Den", "order": 1}, order=4)["order"] == 1
    assert _err(m.build_room, {"name": ""}, order=0).key == "field_required"
    case = m.build_bookcase({"room_id": "r", "name": "Left", "note": "n"}, order=0)
    assert case["room_id"] == "r" and case["note"] == "n" and case["order"] == 0
    assert _err(m.build_bookcase, {"name": "x"}, order=0).key == "field_required"
    shelf = m.build_shelf({"bookcase_id": "k", "name": "Top"}, order=2)
    assert shelf == {"id": shelf["id"], "bookcase_id": "k", "name": "Top", "order": 2}
    assert _err(m.build_shelf, {"name": "x"}, order=0).key == "field_required"
    assert _err(m.build_room, {"name": "x", "order": -1}, order=0).key == "out_of_range"


def test_update_location() -> None:
    room = m.build_room({"name": "Den"}, order=0)
    same, changed = m.update_location("room", room, {"name": "Den"})
    assert changed == [] and same == room
    updated, changed = m.update_location(
        "room", room, {"name": "Study", "order": 3, "area_id": "office", "x": 1}
    )
    assert changed == ["name", "area_id", "order"]
    assert updated["name"] == "Study" and room["name"] == "Den"
    case = m.build_bookcase({"room_id": "r", "name": "A"}, order=0)
    updated, changed = m.update_location(
        "bookcase", case, {"note": "x", "room_id": "s"}
    )
    assert changed == ["note", "room_id"] and updated["room_id"] == "s"
    shelf = m.build_shelf({"bookcase_id": "k", "name": "A"}, order=0)
    updated, changed = m.update_location("shelf", shelf, {"bookcase_id": "j"})
    assert changed == ["bookcase_id"]
    err = _err(m.update_location, "shelf", shelf, {"bookcase_id": ""})
    assert err.key == "field_required"


def test_next_order() -> None:
    records = {
        "a": {"order": 2, "room_id": "r"},
        "b": {"order": 5, "room_id": "s"},
    }
    assert m.next_order({}) == 0
    assert m.next_order(records) == 6
    assert m.next_order(records, room_id="r") == 3
    assert m.next_order(records, room_id="z") == 0


# ── Books ────────────────────────────────────────────────────────────────────


def test_build_book_defaults() -> None:
    book = m.build_book({"title": "Dune"}, now=NOW)
    assert book["title"] == "Dune"
    assert book["cover"] == {"kind": "none", "file": None}
    assert book["created_at"] == book["updated_at"] == NOW
    assert book["needs_details"] is False and book["lookup_tries"] == 0
    assert m.build_book({"title": "Dune", "isbn": ""}, now=NOW)["isbn13"] is None
    assert book["wishlist"] is None and book["isbn13"] is None
    assert _err(m.build_book, {}, now=NOW).key == "field_required"


def test_build_book_isbn_forms() -> None:
    book = m.build_book({"title": "x", "isbn": "0441478123"}, now=NOW)
    assert (book["isbn13"], book["isbn10"]) == ("9780441478125", "0441478123")
    book = m.build_book({"title": "x", "isbn13": "9780441478125"}, now=NOW)
    assert book["isbn10"] == "0441478123"
    book = m.build_book({"title": "x", "isbn10": "0441478123"}, now=NOW)
    assert book["isbn13"] == "9780441478125"
    book = m.build_book({"title": "x", "isbn13": "9791032305690"}, now=NOW)
    assert book["isbn10"] is None
    assert _err(m.build_book, {"title": "x", "isbn": "123"}, now=NOW).key == (
        "invalid_isbn"
    )
    err = _err(m.build_book, {"title": "x", "isbn10": "0441478124"}, now=NOW)
    assert err.key == "invalid_isbn" and err.placeholders == {"isbn": "0441478124"}


def test_book_fields() -> None:
    assert m.book_field("isbn13", "") is None
    assert m.book_field("isbn10", None) is None
    assert m.book_field("pages", 300) == 300
    assert _err(m.book_field, "pages", 0).key == "out_of_range"
    assert m.book_field("language", " en ") == "en"
    assert m.book_field("series", "Dune") == {"name": "Dune", "number": None}
    assert m.book_field("series", {"name": "Dune", "number": 2}) == {
        "name": "Dune",
        "number": "2",
    }
    assert m.book_field("series", {"name": " "}) is None
    assert m.book_field("series", None) is None
    assert m.book_field("series", {"name": "D", "number": ""}) == {
        "name": "D",
        "number": None,
    }
    assert _err(m.book_field, "series", 3).key == "invalid_field"
    assert _err(m.book_field, "series", {"name": "D", "number": [1]}).key == (
        "invalid_field"
    )
    assert m.book_field("openlibrary", None) is None
    assert m.book_field("openlibrary", {}) is None
    assert m.book_field("openlibrary", {"work_key": "OL1W", "cover_id": 5}) == {
        "edition_key": None,
        "work_key": "OL1W",
        "cover_id": 5,
    }
    assert _err(m.book_field, "openlibrary", "x").key == "invalid_field"
    assert m.book_field("needs_details", True) is True
    assert m.book_field("tags", ["a", "a"]) == ["a"]
    assert _err(m.book_field, "nope", 1).key == "invalid_field"
    assert m.book_field("title", " T ") == "T"
    assert _err(m.book_field, "title", "").key == "field_required"
    assert m.book_field("subtitle", "") == ""


def test_update_book() -> None:
    book = m.build_book({"title": "Dune"}, now="t0")
    same, changed = m.update_book(book, {"title": "Dune"}, now="t1")
    assert changed == [] and same["updated_at"] == "t0"
    updated, changed = m.update_book(
        book, {"subtitle": "S", "pages": 10, "id": "x"}, now="t1"
    )
    assert changed == ["subtitle", "pages"]
    assert updated["updated_at"] == "t1" and updated["id"] == book["id"]
    updated, changed = m.update_book(book, {"isbn": "0441478123"}, now="t1")
    assert sorted(changed) == ["isbn10", "isbn13"]
    # A new ISBN-13 sets the ISBN-10 from it. An empty one clears both.
    other, changed = m.update_book(updated, {"isbn13": "9780306406157"}, now="t2")
    assert (other["isbn13"], other["isbn10"]) == ("9780306406157", "0306406152")
    assert sorted(changed) == ["isbn10", "isbn13"]
    other, changed = m.update_book(updated, {"isbn13": "0306406152"}, now="t2")
    assert (other["isbn13"], other["isbn10"]) == ("9780306406157", "0306406152")
    other, _ = m.update_book(updated, {"isbn13": "9791032305690"}, now="t2")
    assert (other["isbn13"], other["isbn10"]) == ("9791032305690", None)
    other, _ = m.update_book(updated, {"isbn13": None}, now="t2")
    assert (other["isbn13"], other["isbn10"]) == (None, None)
    other, _ = m.update_book(
        updated, {"isbn13": "9780306406157", "isbn10": "0441478123"}, now="t2"
    )
    assert (other["isbn13"], other["isbn10"]) == ("9780306406157", "0441478123")
    assert _err(m.update_book, updated, {"isbn13": "123"}, now="t2").key == (
        "invalid_isbn"
    )


def test_fill_from_draft_keeps_user_edits() -> None:
    book = m.build_book({"title": "Mine", "pages": 5, "needs_details": True}, now="t0")
    draft = {
        "title": "Theirs",
        "authors": ["A"],
        "pages": 300,
        "publisher": "",
        "subjects": [],
        "language": "en",
        "isbn13": "bad",
        "openlibrary": {"work_key": "OL1W"},
    }
    filled, changed = m.fill_from_draft(book, draft, now="t1")
    assert filled["title"] == "Mine" and filled["pages"] == 5
    assert filled["authors"] == ["A"] and filled["language"] == "en"
    assert filled["isbn13"] is None
    assert filled["openlibrary"]["work_key"] == "OL1W"
    assert filled["needs_details"] is False
    assert changed == ["authors", "language", "openlibrary", "needs_details"]
    assert filled["updated_at"] == "t1"
    again, changed = m.fill_from_draft(filled, draft, now="t2")
    assert changed == [] and again["updated_at"] == "t1"


def test_book_summary_and_keys() -> None:
    assert m.book_summary({"title": "Dune", "authors": ["Frank Herbert"]}) == (
        "Dune by Frank Herbert"
    )
    assert m.book_summary({"title": "Dune", "authors": []}) == "Dune"
    assert m.book_summary({"title": "Dune", "authors": ["F"]}, "{author}: {title}") == (
        "F: Dune"
    )
    assert m.fold("Élan, Vital!") == "elan vital"
    assert m.fold(None) == ""
    assert m.title_key("Dune: Messiah", ["Frank Herbert"]) == "dune|herbert"
    assert m.title_key("Dune", ["Herbert, Frank"]) == "dune|herbert"
    assert m.title_key("Dune", "Frank Herbert") == "dune|herbert"
    assert m.title_key("Dune", []) == "dune|"
    assert m.title_key(None, None) == "|"


# ── Copies ───────────────────────────────────────────────────────────────────


def test_build_and_update_copy() -> None:
    copy = m.build_copy({"book_id": "b"}, now=NOW)
    assert copy["format"] == m.DEFAULT_FORMAT and copy["shelf_id"] is None
    assert copy["signed"] is False and copy["created_at"] == NOW
    assert _err(m.build_copy, {}, now=NOW).key == "field_required"
    full = m.build_copy(
        {
            "book_id": "b",
            "shelf_id": "s",
            "format": "hardcover",
            "condition": "fine",
            "acquired": "2020-01-01",
            "acquired_from": "Shop",
            "price": 10,
            "value": 12.5,
            "signed": True,
            "first_edition": True,
            "note": "n",
        },
        now=NOW,
    )
    assert full["condition"] == "fine" and full["value"] == 12.5
    _same, changed = m.update_copy(full, {"format": "hardcover"})
    assert changed == []
    updated, changed = m.update_copy(full, {"shelf_id": None, "condition": ""})
    assert changed == ["shelf_id", "condition"] and updated["condition"] is None
    assert _err(m.copy_field, "format", "scroll").key == "invalid_choice"
    assert _err(m.copy_field, "nope", 1).key == "invalid_field"


@pytest.mark.parametrize(
    ("binding", "fmt"),
    [
        ("Hardcover", "hardcover"),
        ("Hardback", "hardcover"),
        ("Paperback", "paperback"),
        ("Mass Market Paperback", "paperback"),
        ("Kindle Edition", "ebook"),
        ("ebook", "ebook"),
        ("digital", "ebook"),
        ("Audible Audio", "audiobook"),
        ("Audiobook", "audiobook"),
        ("audio", "audiobook"),
        ("Board book", "other"),
        ("", "other"),
        (None, "other"),
    ],
)
def test_format_from_binding(binding: str | None, fmt: str) -> None:
    assert m.format_from_binding(binding) == fmt


# ── Reading ──────────────────────────────────────────────────────────────────


def test_apply_reading_new_row() -> None:
    row, changed = m.apply_reading(None, {}, now=NOW, today=TODAY)
    assert row["status"] == "want" and changed == ["status"]
    assert row["updated_at"] == NOW and row["read_count"] == 0


def test_apply_reading_read_sets_finished_and_count() -> None:
    row, changed = m.apply_reading(None, {"status": "read"}, now=NOW, today=TODAY)
    assert row["finished"] == TODAY and row["read_count"] == 1
    assert changed == ["status", "finished", "read_count"]
    again, changed = m.apply_reading(row, {"status": "read"}, now="t2", today="x")
    assert changed == [] and again["read_count"] == 1 and again["updated_at"] == NOW
    reread, _ = m.apply_reading(
        {**row, "status": "reading"}, {"status": "read"}, now="t2", today="2027-01-01"
    )
    assert reread["read_count"] == 2 and reread["finished"] == "2027-01-01"
    explicit, _ = m.apply_reading(
        None,
        {"status": "read", "finished": "2020-02-02", "read_count": 4},
        now=NOW,
        today=TODAY,
    )
    assert explicit["finished"] == "2020-02-02" and explicit["read_count"] == 4


def test_apply_reading_reading_sets_started() -> None:
    row, _ = m.apply_reading(None, {"status": "reading"}, now=NOW, today=TODAY)
    assert row["started"] == TODAY and row["finished"] is None
    row, _ = m.apply_reading(
        None, {"status": "reading", "started": "2026-01-01"}, now=NOW, today=TODAY
    )
    assert row["started"] == "2026-01-01"
    dnf, _ = m.apply_reading(row, {"status": "dnf"}, now=NOW, today=TODAY)
    assert dnf["started"] == "2026-01-01" and dnf["finished"] is None


def test_apply_reading_fields_and_errors() -> None:
    _row, changed = m.apply_reading(
        None,
        {"rating": 5, "page": 10, "private_notes": "p"},
        now=NOW,
        today=TODAY,
    )
    assert changed == ["status", "rating", "page", "private_notes"]
    assert _err(m.reading_field, "rating", 6).key == "out_of_range"
    assert _err(m.reading_field, "status", "maybe").key == "invalid_choice"
    assert _err(m.reading_field, "nope", 1).key == "invalid_field"
    assert _err(m.reading_field, "read_count", None).key == "field_required"
    assert m.reading_field("page", 0) == 0


# ── Loans ────────────────────────────────────────────────────────────────────


def _loan(**data):
    base = {"direction": "out", "copy_id": "c", "book_id": "b", "party": "Alex"}
    return m.build_loan({**base, **data}, today=TODAY)


def test_build_loan() -> None:
    loan = _loan()
    assert loan["started"] == TODAY and loan["due"] is None
    assert loan["add_task"] is True and loan["overdue_fired"] is False
    assert loan["returned"] is None and loan["hk_task_id"] is None
    assert _loan(add_task=False)["add_task"] is False
    assert _loan(format="ebook")["format"] == "ebook"
    assert _loan(format="")["format"] is None
    assert _err(_loan, copy_id=None).placeholders == {"field": "copy_id"}
    assert _err(_loan, party="").key == "field_required"
    assert _err(_loan, direction="sideways").key == "invalid_choice"
    assert _err(_loan, started="2026-10-05", due="2026-10-04").key == (
        "due_before_start"
    )
    assert _loan(started="2026-10-05", due="2026-10-05")["due"] == "2026-10-05"
    borrowed = _loan(direction="in", person_id="p")
    assert borrowed["copy_id"] is None and borrowed["person_id"] == "p"
    assert _err(_loan, direction="in").placeholders == {"field": "person_id"}


def test_update_loan() -> None:
    loan = {**_loan(due="2026-10-10"), "overdue_fired": True}
    same, changed = m.update_loan(loan, {"party": "Alex"})
    assert changed == [] and same["overdue_fired"] is True
    updated, changed = m.update_loan(
        loan, {"due": "2026-11-01", "note": "n", "format": "", "party": "Bo"}
    )
    assert changed == ["party", "due", "note"]
    assert updated["overdue_fired"] is False
    updated, changed = m.update_loan(loan, {"started": None, "format": "ebook"})
    assert updated["started"] == loan["started"] and changed == ["format"]
    assert _err(m.update_loan, loan, {"due": "2020-01-01"}).key == "due_before_start"
    cleared, changed = m.update_loan(loan, {"due": None})
    assert cleared["due"] is None and changed == ["due"]


def test_loan_state() -> None:
    loan = _loan(started="2026-10-01", due="2026-10-04")
    assert m.is_open(loan)
    assert m.is_overdue(loan, "2026-10-05")
    assert not m.is_overdue(loan, "2026-10-04")
    assert not m.is_overdue({**loan, "returned": "2026-10-05"}, "2026-10-06")
    assert not m.is_overdue({**loan, "due": None}, "2027-01-01")


# ── People and wishlist ──────────────────────────────────────────────────────


def test_person_settings() -> None:
    assert m.person_settings({}, "p") == m.default_person()
    stored = {"p": {"share_reading": False, "junk": 1}}
    assert m.person_settings(stored, "p") == {
        "share_reading": False,
        "wishlist_todo": None,
        "yearly_goal": None,
    }
    assert m.person_settings({"p": "bad"}, "p") == m.default_person()
    settings, changed = m.apply_person_settings(
        m.default_person(),
        {"share_reading": False, "wishlist_todo": "todo.books", "yearly_goal": 12},
    )
    assert changed == ["share_reading", "wishlist_todo", "yearly_goal"]
    assert settings["yearly_goal"] == 12
    _, changed = m.apply_person_settings(settings, {"yearly_goal": 12})
    assert changed == []
    err = _err(m.apply_person_settings, settings, {"wishlist_todo": "light.x"})
    assert err.key == "invalid_field"
    assert _err(m.apply_person_settings, settings, {"yearly_goal": 0}).key == (
        "out_of_range"
    )


def test_build_wishlist() -> None:
    entry = m.build_wishlist("p", buy=True, now=NOW)
    assert entry == {
        "person_id": "p",
        "buy": True,
        "added_at": NOW,
        "todo_uid": None,
        "todo_entity": None,
        "bought": False,
    }
    assert _err(m.build_wishlist, "", buy=True, now=NOW).key == "field_required"
    assert _err(m.build_wishlist, "p", buy="yes", now=NOW).key == "invalid_field"


def test_copy_clears_wishlist() -> None:
    state = m.empty_state()
    entry = m.build_wishlist("p", buy=False, now=NOW)
    state["books"]["w"] = {"id": "w", "wishlist": entry}
    state["books"]["plain"] = {"id": "plain", "wishlist": None}
    state["books"]["owned"] = {"id": "owned", "wishlist": dict(entry)}
    state["copies"]["c"] = {"id": "c", "book_id": "owned"}
    state["copies"]["d"] = {"id": "d", "book_id": "plain"}
    assert m.copy_clears_wishlist(state, "w") is True
    assert m.copy_clears_wishlist(state, "plain") is False
    assert m.copy_clears_wishlist(state, "owned") is False
    assert m.copy_clears_wishlist(state, "nope") is False


# ── Derived reads ────────────────────────────────────────────────────────────


def _state():
    state = m.empty_state()
    state["rooms"]["r"] = {"id": "r", "name": "Den"}
    state["bookcases"]["k"] = {"id": "k", "room_id": "r", "name": "Left"}
    state["shelves"]["s"] = {"id": "s", "bookcase_id": "k", "name": "Top"}
    state["books"]["b"] = {"id": "b", "isbn13": "9780441478125", "isbn10": None}
    state["books"]["c"] = {"id": "c", "isbn13": None, "isbn10": "080442957X"}
    state["copies"]["x2"] = {"id": "x2", "book_id": "b", "created_at": "2"}
    state["copies"]["x1"] = {"id": "x1", "book_id": "b", "created_at": "1"}
    state["copies"]["y"] = {"id": "y", "book_id": "c", "created_at": "0"}
    state["loans"]["l"] = {"id": "l", "copy_id": "x1", "returned": None}
    state["loans"]["old"] = {"id": "old", "copy_id": "y", "returned": "2020-01-01"}
    return state


def test_derived_reads() -> None:
    state = _state()
    assert [c["id"] for c in m.copies_of(state, "b")] == ["x1", "x2"]
    assert m.open_loan_of_copy(state, "x1")["id"] == "l"
    assert m.open_loan_of_copy(state, "y") is None
    assert m.location_path(state, "s") == ["Den", "Left", "Top"]
    assert m.location_path(state, None) == []
    assert m.location_path(state, "nope") == []
    assert m.find_shelf_by_path(state, ["den", "LEFT", "top"]) == "s"
    assert m.find_shelf_by_path(state, ["Den", "Left"]) is None
    assert m.find_shelf_by_path(state, ["Den", "Left", "Low"]) is None
    assert m.find_book_by_isbn(state, "9780441478125")["id"] == "b"
    assert m.find_book_by_isbn(state, None, "080442957X")["id"] == "c"
    assert m.find_book_by_isbn(state, "9780000000002", "0000000000") is None
