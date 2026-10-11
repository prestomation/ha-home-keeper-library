"""Unit tests for the pure build and plan of the Home Keeper export section."""

from __future__ import annotations

import os

import ex.import_export as iex
import ex.models as m
import pytest
from asserts import raises_exactly

NOW = "2026-10-11T12:00:00+00:00"
LATER = "2026-10-12T08:00:00+00:00"
ALICE = "p_alice"
BOB = "p_bob"
PERSONS = {ALICE: "Alice", BOB: "Bob"}
AREAS = {"living_room": "Living room"}
TODOS = {"todo.books": "Books to buy"}

ROOM = "a" * 32
CASE = "b" * 32
SHELF = "c" * 32
DUNE = "d" * 32
EMMA = "e" * 32
COPY = "f" * 32
LOAN_OUT = "1" * 32
LOAN_IN = "2" * 32


def _state() -> dict:
    """A document with 1 record in each section, and the install-only values."""
    state = m.empty_state()
    state["rooms"][ROOM] = {
        "id": ROOM,
        "name": "Study",
        "area_id": "living_room",
        "order": 0,
    }
    state["bookcases"][CASE] = {
        "id": CASE,
        "room_id": ROOM,
        "name": "Oak",
        "note": "By the window",
        "order": 0,
    }
    state["shelves"][SHELF] = {
        "id": SHELF,
        "bookcase_id": CASE,
        "name": "Top",
        "order": 0,
    }
    dune = m.build_book(
        {"title": "Dune", "authors": ["Frank Herbert"], "isbn": "9780441013593"},
        now=NOW,
    )
    dune["id"] = DUNE
    dune["cover"] = {"kind": "custom", "file": f"{DUNE}-0a1b2c3d.jpg"}
    dune["lookup_tries"] = 2
    emma = m.build_book({"title": "Emma", "authors": ["Jane Austen"]}, now=NOW)
    emma["id"] = EMMA
    emma["wishlist"] = {
        "person_id": BOB,
        "buy": True,
        "added_at": NOW,
        "todo_uid": "uid-1",
        "todo_entity": "todo.books",
        "bought": False,
    }
    state["books"] = {DUNE: dune, EMMA: emma}
    copy = m.build_copy(
        {"book_id": DUNE, "shelf_id": SHELF, "format": "hardcover", "price": 12},
        now=NOW,
    )
    copy["id"] = COPY
    state["copies"][COPY] = copy
    out = m.build_loan(
        {"direction": "out", "book_id": DUNE, "copy_id": COPY, "party": "Sam"},
        today="2026-10-01",
    )
    out["id"] = LOAN_OUT
    out["hk_task_id"] = "hk-task-9"
    borrowed = m.build_loan(
        {"direction": "in", "book_id": EMMA, "party": "Lib", "person_id": BOB},
        today="2026-10-02",
    )
    borrowed["id"] = LOAN_IN
    state["loans"] = {LOAN_OUT: out, LOAN_IN: borrowed}
    row, _ = m.apply_reading(
        None, {"status": "read", "rating": 5}, now=NOW, today="2026-10-03"
    )
    row["private_notes"] = "Mine"
    state["reading"] = {ALICE: {DUNE: row}}
    state["people"] = {
        ALICE: {"share_reading": False, "wishlist_todo": None, "yearly_goal": 20},
        BOB: {
            "share_reading": True,
            "wishlist_todo": "todo.books",
            "yearly_goal": None,
        },
    }
    state["todo_orphans"] = [{"entity_id": "todo.books", "uid": "old"}]
    return state


def _export(state: dict, covers: dict | None = None) -> tuple[dict, dict]:
    return iex.build_export(
        state,
        person_names=PERSONS,
        area_names=AREAS,
        entity_names=TODOS,
        cover_files=covers or {},
    )


def _plan(state: dict, document: object, **kwargs: object) -> iex.ImportPlan:
    args = {"persons": PERSONS, "areas": AREAS, "todo_entities": TODOS, "now": LATER}
    args.update(kwargs)
    return iex.plan_import(state, document, **args)  # type: ignore[arg-type]


def _problems(plan: iex.ImportPlan) -> list[tuple[str, str, str]]:
    return [(p.level, p.path, p.key) for p in plan.problems]


# ── Export ───────────────────────────────────────────────────────────────────


def test_export_shape_and_names() -> None:
    data, skipped = _export(_state())
    assert data["format"] == iex.FORMAT == 1
    assert list(data) == ["format", *iex.SECTIONS]
    assert data["rooms"] == [
        {
            "id": ROOM,
            "name": "Study",
            "area_id": "living_room",
            "order": 0,
            "area_name": "Living room",
        }
    ]
    assert data["bookcases"][0]["note"] == "By the window"
    assert data["shelves"][0]["bookcase_id"] == CASE
    assert [b["id"] for b in data["books"]] == [DUNE, EMMA]
    assert data["books"][1]["wishlist"] == {
        "person_id": BOB,
        "buy": True,
        "added_at": NOW,
        "bought": False,
        "person_name": "Bob",
    }
    assert data["books"][0]["wishlist"] is None
    assert data["reading"] == [
        {
            "person_id": ALICE,
            "person_name": "Alice",
            "books": [{"book_id": DUNE, **_state()["reading"][ALICE][DUNE]}],
        }
    ]
    assert data["people"] == [
        {
            "person_id": ALICE,
            "person_name": "Alice",
            "share_reading": False,
            "wishlist_todo": None,
            "yearly_goal": 20,
            "wishlist_todo_name": None,
        },
        {
            "person_id": BOB,
            "person_name": "Bob",
            "share_reading": True,
            "wishlist_todo": "todo.books",
            "yearly_goal": None,
            "wishlist_todo_name": "Books to buy",
        },
    ]
    loans = {loan["id"]: loan for loan in data["loans"]}
    assert loans[LOAN_IN]["person_name"] == "Bob"
    assert loans[LOAN_OUT]["person_name"] is None
    assert skipped == {"covers": 1}


def test_export_drops_each_install_only_value() -> None:
    data, _ = _export(_state())
    assert "todo_orphans" not in data
    assert all("lookup_tries" not in book for book in data["books"])
    assert all("hk_task_id" not in loan for loan in data["loans"])
    wish = data["books"][1]["wishlist"]
    assert "todo_uid" not in wish
    assert "todo_entity" not in wish


def test_every_stored_key_is_exported_or_excluded_with_a_reason() -> None:
    """A new stored field must travel, or be excluded here with a reason."""
    state = _state()
    data, _ = _export(state, {DUNE: "covers/x.jpg"})
    sections = {
        "rooms": "rooms",
        "bookcases": "bookcases",
        "shelves": "shelves",
        "books": "books",
        "copies": "copies",
        "loans": "loans",
    }
    for section, key in sections.items():
        stored = set().union(*(set(r) for r in state[key].values()))
        exported = set().union(*(set(r) for r in data[section]))
        excluded = {k for k, _ in iex.EXCLUDED_KEYS.get(section, ())}
        assert stored - excluded <= exported, section
        assert not (excluded & exported), section
    wish_keys = set(state["books"][EMMA]["wishlist"])
    wish_excluded = {k for k, _ in iex.EXCLUDED_KEYS["wishlist"]}
    assert wish_keys - wish_excluded <= set(data["books"][1]["wishlist"])
    top = set(state) - set(iex.SECTIONS)
    assert top == {k for k, _ in iex.EXCLUDED_KEYS["document"]}
    for pairs in iex.EXCLUDED_KEYS.values():
        assert all(reason.strip() for _, reason in pairs)


def test_export_cover_with_files() -> None:
    data, skipped = _export(_state(), {DUNE: iex.cover_export_path(DUNE)})
    assert data["books"][0]["cover"] == {"kind": "custom", "file": f"covers/{DUNE}.jpg"}
    assert data["books"][1]["cover"] is None
    assert skipped == {"covers": 0}


def test_covers_to_copy() -> None:
    state = _state()
    state["books"][EMMA]["cover"] = {"kind": "none", "file": "stale.jpg"}
    assert iex.covers_to_copy(state) == [(DUNE, f"{DUNE}-0a1b2c3d.jpg")]


# ── Round trip ───────────────────────────────────────────────────────────────


def test_round_trip_into_an_empty_library() -> None:
    state = _state()
    data, _ = _export(state)
    plan = _plan(m.empty_state(), data)
    assert plan.ok, plan.problems
    assert plan.problems == []
    again, _ = _export(plan.state)
    assert again == data
    counts = plan.counts
    assert counts["rooms"] == {"created": 1, "updated": 0, "skipped": 0}
    assert counts["books"] == {"created": 2, "updated": 0, "skipped": 0}
    assert counts["copies"]["created"] == 1
    assert counts["loans"]["created"] == 2
    assert counts["reading"]["created"] == 1
    assert counts["people"]["created"] == 2
    # The syncs make the install-only values again.
    assert plan.state["loans"][LOAN_OUT]["hk_task_id"] is None
    assert plan.state["books"][EMMA]["wishlist"]["todo_uid"] is None
    assert plan.state["books"][DUNE]["lookup_tries"] == 0
    assert plan.state["todo_orphans"] == []


def test_import_does_not_change_its_arguments() -> None:
    state = _state()
    data, _ = _export(state)
    before = m.clone(state)
    document = m.clone(data)
    _plan(state, data)
    assert state == before
    assert data == document


def test_import_into_the_same_library_changes_no_record() -> None:
    state = _state()
    data, _ = _export(state)
    plan = _plan(state, data)
    assert plan.ok
    assert plan.state == state
    actions = {(r["section"], r["action"], r["matched_by"]) for r in plan.records}
    assert ("books", "update", "id") in actions
    assert ("rooms", "update", "id") in actions
    assert all(r["action"] == "update" for r in plan.records)


def test_import_keeps_the_task_id_of_a_loan_that_exists() -> None:
    state = _state()
    data, _ = _export(state)
    data["loans"][0]["party"] = "Sam Smith"
    plan = _plan(state, data)
    assert plan.state["loans"][LOAN_OUT]["party"] == "Sam Smith"
    assert plan.state["loans"][LOAN_OUT]["hk_task_id"] == "hk-task-9"


def test_records_report_names_and_matches() -> None:
    plan = _plan(m.empty_state(), _export(_state())[0])
    assert plan.records[0] == {
        "section": "rooms",
        "index": 0,
        "id": ROOM,
        "name": "Study",
        "action": "create",
        "matched_by": None,
    }
    books = [r for r in plan.records if r["section"] == "books"]
    assert [b["name"] for b in books] == ["Dune", "Emma"]


# ── Matching ─────────────────────────────────────────────────────────────────


def test_books_match_by_isbn_then_title() -> None:
    state = m.empty_state()
    stored = m.build_book({"title": "Dune", "isbn": "9780441013593"}, now=NOW)
    other = m.build_book({"title": "Emma", "authors": ["Jane Austen"]}, now=NOW)
    old10 = m.build_book({"title": "Old", "isbn10": "0441478123"}, now=NOW)
    old10["isbn13"] = None
    state["books"] = {b["id"]: b for b in (stored, other, old10)}
    document = {
        "books": [
            {"id": "x" * 32, "title": "Dune Messiah", "isbn13": "9780441013593"},
            {"title": "Emma: A Novel", "authors": ["Austen"]},
            {"title": "Old again", "isbn10": "0441478123", "isbn13": None},
            {"title": "Dune", "isbn13": "9780441013593"},
        ]
    }
    plan = _plan(state, document)
    assert plan.ok, plan.problems
    matched = [(r["id"], r["matched_by"]) for r in plan.records]
    assert matched == [
        (stored["id"], "isbn13"),
        (other["id"], "title"),
        (old10["id"], "isbn10"),
        (stored["id"], "isbn13"),
    ]
    assert len(plan.state["books"]) == 3
    assert plan.state["books"][stored["id"]]["title"] == "Dune"
    assert plan.state["books"][stored["id"]]["updated_at"] == LATER


def test_two_books_with_one_isbn_in_the_document_make_one_book() -> None:
    document = {
        "books": [
            {"title": "Dune", "isbn13": "9780441013593"},
            {"title": "Dune (2nd)", "isbn13": "9780441013593"},
        ]
    }
    plan = _plan(m.empty_state(), document)
    assert len(plan.state["books"]) == 1
    assert [r["action"] for r in plan.records] == ["create", "update"]
    assert plan.counts["books"] == {"created": 1, "updated": 1, "skipped": 0}


def test_new_book_needs_details_goes_to_lookup() -> None:
    document = {
        "books": [{"title": "X", "isbn13": "9780441013593", "needs_details": True}]
    }
    plan = _plan(m.empty_state(), document)
    assert plan.lookup_ids == list(plan.state["books"])


def test_locations_match_by_name_within_the_parent() -> None:
    state = _state()
    document = {
        "rooms": [{"id": "r1", "name": " study "}],
        "bookcases": [
            {"id": "c1", "room_id": "r1", "name": "OAK", "note": "Moved"},
            {"id": "c2", "room_id": "r1", "name": "Pine"},
        ],
        "shelves": [{"id": "s1", "bookcase_id": "c2", "name": "Top"}],
    }
    plan = _plan(state, document)
    assert plan.ok, plan.problems
    by = [(r["section"], r["action"], r["matched_by"]) for r in plan.records]
    assert by == [
        ("rooms", "update", "name"),
        ("bookcases", "update", "name"),
        ("bookcases", "create", None),
        ("shelves", "create", None),
    ]
    assert plan.state["bookcases"][CASE]["note"] == "Moved"
    # A new id that is not a record id gets a new id.
    pine = next(b for b in plan.state["bookcases"].values() if b["name"] == "Pine")
    assert pine["id"] != "c2"
    assert len(pine["id"]) == 32
    assert pine["order"] == 1
    top = [s for s in plan.state["shelves"].values() if s["name"] == "Top"]
    assert len(top) == 2


def test_a_missing_parent_is_an_error() -> None:
    plan = _plan(m.empty_state(), {"bookcases": [{"name": "Oak", "room_id": "nope"}]})
    assert not plan.ok
    assert _problems(plan) == [
        ("error", "bookcases[0].room_id", "import_reference_missing")
    ]
    assert plan.problems[0].placeholders == {"field": "room_id", "id": "nope"}


# ── People, areas and to-do lists ────────────────────────────────────────────


def test_person_matches_by_name_on_another_install() -> None:
    data, _ = _export(_state())
    plan = _plan(m.empty_state(), data, persons={"p_new_alice": "ALICE", BOB: "Bob"})
    assert plan.ok
    assert set(plan.state["reading"]) == {"p_new_alice"}
    assert "p_new_alice" in plan.state["people"]


def test_unknown_person_warns_and_skips_the_rows() -> None:
    data, _ = _export(_state())
    plan = _plan(
        m.empty_state(), data, persons={ALICE: "Alice"}, todo_entities={}, areas={}
    )
    assert plan.ok
    warnings = _problems(plan)
    assert ("warning", "rooms[0].area_id", "import_area_not_found") in warnings
    assert ("warning", "books[1].wishlist.person_id", "import_person_not_found") in (
        warnings
    )
    in_loan = next(i for i, x in enumerate(data["loans"]) if x["id"] == LOAN_IN)
    assert ("warning", f"loans[{in_loan}].person_id", "import_person_not_found") in (
        warnings
    )
    assert ("warning", "people[1].person_id", "import_person_not_found") in warnings
    assert plan.counts["loans"]["skipped"] == 1
    assert plan.counts["people"]["skipped"] == 1
    assert LOAN_IN not in plan.state["loans"]
    assert plan.state["books"][EMMA]["wishlist"] is None
    assert plan.state["rooms"][ROOM]["area_id"] is None
    assert BOB not in plan.state["people"]
    message = next(p for p in plan.problems if p.path == "people[1].person_id")
    assert message.placeholders == {"name": "Bob"}


def test_unknown_reader_skips_each_row() -> None:
    data, _ = _export(_state())
    plan = _plan(m.empty_state(), data, persons={BOB: "Bob"})
    assert plan.counts["reading"] == {"created": 0, "updated": 0, "skipped": 1}
    assert ("warning", "reading[0].person_id", "import_person_not_found") in (
        _problems(plan)
    )
    assert plan.state["reading"] == {}


def test_two_people_with_one_name_match_neither() -> None:
    document = {"people": [{"person_id": "gone", "person_name": "Sam"}]}
    plan = _plan(m.empty_state(), document, persons={"a": "Sam", "b": "sam"})
    assert _problems(plan) == [
        ("warning", "people[0].person_id", "import_person_not_found")
    ]


def test_area_and_todo_match_by_name() -> None:
    document = {
        "rooms": [{"name": "Den", "area_id": "old_area", "area_name": "living ROOM"}],
        "people": [
            {
                "person_id": ALICE,
                "wishlist_todo": "todo.old",
                "wishlist_todo_name": "Books to buy",
            }
        ],
    }
    plan = _plan(m.empty_state(), document)
    assert plan.ok and plan.problems == []
    room = next(iter(plan.state["rooms"].values()))
    assert room["area_id"] == "living_room"
    assert plan.state["people"][ALICE]["wishlist_todo"] == "todo.books"


def test_unknown_area_or_todo_keeps_the_stored_value() -> None:
    state = _state()
    document = {
        "rooms": [{"id": ROOM, "name": "Study", "area_name": "Attic"}],
        "people": [
            {"person_id": BOB, "wishlist_todo": "todo.x", "wishlist_todo_name": "X"}
        ],
    }
    plan = _plan(state, document)
    assert plan.state["rooms"][ROOM]["area_id"] == "living_room"
    assert plan.state["people"][BOB]["wishlist_todo"] == "todo.books"
    assert _problems(plan) == [
        ("warning", "rooms[0].area_id", "import_area_not_found"),
        ("warning", "people[0].wishlist_todo", "import_todo_not_found"),
    ]


def test_people_can_clear_the_wishlist_list() -> None:
    document = {"people": [{"person_id": BOB, "wishlist_todo": None}]}
    plan = _plan(_state(), document)
    assert plan.state["people"][BOB]["wishlist_todo"] is None


# ── Upsert, never delete ─────────────────────────────────────────────────────


def test_records_not_in_the_document_stay() -> None:
    state = _state()
    plan = _plan(state, {"books": [{"title": "New book"}]})
    assert set(state["books"]) < set(plan.state["books"])
    assert plan.state["rooms"] == state["rooms"]
    assert plan.state["loans"] == state["loans"]


def test_wishlist_none_keeps_the_stored_entry() -> None:
    state = _state()
    data, _ = _export(state)
    data["books"][1]["wishlist"] = None
    plan = _plan(state, data)
    assert plan.state["books"][EMMA]["wishlist"] == state["books"][EMMA]["wishlist"]


def test_wishlist_update_keeps_the_todo_binding() -> None:
    state = _state()
    data, _ = _export(state)
    data["books"][1]["wishlist"]["buy"] = False
    plan = _plan(state, data)
    entry = plan.state["books"][EMMA]["wishlist"]
    assert entry["buy"] is False
    assert entry["todo_uid"] == "uid-1"


def test_reading_row_update_moves_the_time_stamp() -> None:
    state = _state()
    data, _ = _export(state)
    row = data["reading"][0]["books"][0]
    row["rating"] = 3
    del row["updated_at"]
    plan = _plan(state, data)
    stored = plan.state["reading"][ALICE][DUNE]
    assert stored["rating"] == 3
    assert stored["updated_at"] == LATER
    assert stored["private_notes"] == "Mine"


def test_copy_on_a_missing_shelf_goes_to_no_shelf() -> None:
    document = {
        "books": [{"id": DUNE, "title": "Dune"}],
        "copies": [{"id": COPY, "book_id": DUNE, "shelf_id": "gone"}],
    }
    plan = _plan(m.empty_state(), document)
    assert plan.ok
    assert plan.state["copies"][COPY]["shelf_id"] is None
    assert _problems(plan) == [
        ("warning", "copies[0].shelf_id", "import_reference_missing")
    ]


def test_copy_update_by_id() -> None:
    state = _state()
    document = {"copies": [{"id": COPY, "book_id": DUNE, "format": "ebook"}]}
    plan = _plan(state, document)
    assert plan.state["copies"][COPY]["format"] == "ebook"
    assert plan.state["copies"][COPY]["shelf_id"] is None
    assert plan.records[0]["matched_by"] == "id"


def test_existing_person_settings_update() -> None:
    plan = _plan(_state(), {"people": [{"person_id": ALICE, "yearly_goal": 30}]})
    assert plan.state["people"][ALICE]["yearly_goal"] == 30
    assert plan.state["people"][ALICE]["share_reading"] is False
    assert plan.records[0]["action"] == "update"


# ── Refusals ─────────────────────────────────────────────────────────────────


def test_higher_format_is_refused() -> None:
    plan = _plan(m.empty_state(), {"format": 2, "books": [{"title": "X"}]})
    assert not plan.ok
    assert _problems(plan) == [("error", "format", "import_format_too_new")]
    assert plan.problems[0].placeholders == {"format": "2", "max": "1"}
    assert plan.state["books"] == {}


@pytest.mark.parametrize("fmt", [0, "1", True, None])
def test_bad_format_is_refused(fmt: object) -> None:
    plan = _plan(m.empty_state(), {"format": fmt})
    assert _problems(plan) == [("error", "format", "invalid_field")]


def test_document_must_be_an_object() -> None:
    plan = _plan(m.empty_state(), ["books"])
    assert _problems(plan) == [("error", "", "import_not_an_object")]


def test_section_and_record_shapes() -> None:
    plan = _plan(
        m.empty_state(),
        {"rooms": "x", "books": ["x"], "reading": [{"person_id": ALICE, "books": 1}]},
    )
    assert _problems(plan) == [
        ("error", "rooms", "import_not_a_list"),
        ("error", "books[0]", "import_not_an_object"),
        ("error", "reading[0].books", "import_not_a_list"),
    ]


def test_field_errors_name_the_path_and_block_the_import() -> None:
    document = {
        "rooms": [{"name": ""}],
        "books": [
            {"title": "Ok"},
            {"title": "Bad", "isbn13": "123", "pages": -1},
            {"title": ""},
        ],
        "copies": [{"book_id": "nope", "format": "scroll"}],
        "loans": [{"direction": "out", "book_id": "nope", "copy_id": "nope"}],
        "reading": [
            {"person_id": ALICE, "books": [{"book_id": "nope", "rating": 9}, "x"]}
        ],
        "people": [{"person_id": ALICE, "yearly_goal": 0}],
    }
    plan = _plan(m.empty_state(), document)
    assert not plan.ok
    assert _problems(plan) == [
        ("error", "rooms[0].name", "field_required"),
        ("error", "books[1].isbn13", "invalid_isbn"),
        ("error", "books[1].pages", "out_of_range"),
        ("error", "books[2].title", "field_required"),
        ("error", "copies[0].book_id", "import_reference_missing"),
        ("error", "copies[0].format", "invalid_choice"),
        ("error", "loans[0].book_id", "import_reference_missing"),
        ("error", "loans[0].copy_id", "import_reference_missing"),
        ("error", "reading[0].books[0].book_id", "import_reference_missing"),
        ("error", "reading[0].books[0].rating", "out_of_range"),
        ("error", "reading[0].books[1]", "import_not_an_object"),
        ("error", "people[0]", "out_of_range"),
    ]


def test_bad_loan_and_wishlist_values() -> None:
    document = {
        "books": [
            {"id": DUNE, "title": "Dune", "wishlist": {"person_id": ALICE, "buy": 1}},
            {"title": "Emma", "wishlist": "yes"},
        ],
        "loans": [{"direction": "in", "book_id": DUNE, "person_id": ALICE}],
    }
    plan = _plan(m.empty_state(), document)
    assert _problems(plan) == [
        ("error", "books[0].wishlist.buy", "invalid_field"),
        ("error", "books[1].wishlist", "import_not_an_object"),
        ("error", "loans[0]", "field_required"),
    ]


def test_cover_with_a_bad_path_is_a_warning() -> None:
    document = {
        "books": [
            {"title": "A", "cover": {"kind": "custom", "file": "../../secrets.yaml"}},
            {"title": "B", "cover": {"kind": "openlibrary", "file": "covers/b.jpg"}},
            {"title": "C", "cover": {"kind": "none", "file": "covers/c.jpg"}},
            {"title": "D", "cover": {"kind": "custom", "file": None}},
        ]
    }
    plan = _plan(m.empty_state(), document)
    assert plan.ok
    assert _problems(plan) == [
        ("warning", "books[0].cover.file", "import_cover_unreadable")
    ]
    assert [(c.kind, c.file, c.path) for c in plan.covers] == [
        ("openlibrary", "covers/b.jpg", "books[1].cover.file")
    ]
    assert plan.covers[0].book_id in plan.state["books"]


@pytest.mark.parametrize(
    "value",
    ["covers/a.jpg", "covers/A_b-1.webp", "covers/x.png", "covers/x.jpeg"],
)
def test_cover_path_accepted(value: str) -> None:
    assert iex.is_cover_path(value)


@pytest.mark.parametrize(
    "value",
    ["../covers/a.jpg", "covers/../a.jpg", "/covers/a.jpg", "covers/a.gif", 3, ""],
)
def test_cover_path_refused(value: object) -> None:
    assert not iex.is_cover_path(value)


# ── files_dir ────────────────────────────────────────────────────────────────

CONFIG = "/config"
BASE = "/config/.storage/home_keeper_import_export"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BASE, BASE),
        (f"{BASE}/bundle-1", f"{BASE}/bundle-1"),
        (f"{BASE}/bundle-1/", f"{BASE}/bundle-1"),
        (".storage/home_keeper_import_export/b", f"{BASE}/b"),
        (f"  {BASE}/b  ", f"{BASE}/b"),
    ],
)
def test_files_dir_accepted(value: str, expected: str) -> None:
    assert iex.check_files_dir(value, CONFIG) == os.path.normpath(expected)


@pytest.mark.parametrize(
    "value",
    [
        "/config/.storage",
        "/tmp/x",
        f"{BASE}/../home_keeper",
        f"{BASE}-evil/x",
        ".storage/home_keeper_import_export/../x",
        "../config/.storage/home_keeper_import_export/x",
        ".storage/home_keeper_import_export/a/../b",
        "",
        "   ",
        None,
        f"{BASE}/\0",
    ],
)
def test_files_dir_refused(value: object) -> None:
    with raises_exactly(m.LibraryError, "files_dir_invalid"):
        iex.check_files_dir(value, CONFIG)


# ── Report ───────────────────────────────────────────────────────────────────


def test_report_shape() -> None:
    plan = _plan(m.empty_state(), {"format": 9})
    reply = iex.report(plan, dry_run=True, messages={0: "Too new"})
    assert reply == {
        "ok": False,
        "dry_run": True,
        "counts": {
            name: {"created": 0, "updated": 0, "skipped": 0} for name in iex.SECTIONS
        },
        "records": [],
        "problems": [{"level": "error", "path": "format", "message": "Too new"}],
    }
    fallback = iex.report(plan, dry_run=False, messages={})
    assert fallback["problems"][0]["message"] == "import_format_too_new"
    assert fallback["dry_run"] is False


def test_export_orders_locations_by_order_then_name() -> None:
    state = m.empty_state()
    for key, name, order in (("r3", "b", 1), ("r1", "Zed", 0), ("r2", "alpha", 1)):
        state["rooms"][key] = {"id": key, "name": name, "area_id": None, "order": order}
    state["rooms"]["r4"] = {"id": "r4", "name": "Alpha", "area_id": None, "order": 1}
    data, _ = _export(state)
    assert [r["id"] for r in data["rooms"]] == ["r1", "r2", "r4", "r3"]
    assert data["rooms"][0]["area_name"] is None


def test_export_skips_no_cover_without_a_file() -> None:
    state = _state()
    state["books"][DUNE]["cover"] = {"kind": "openlibrary", "file": None}
    _, skipped = _export(state)
    assert skipped == {"covers": 0}
    assert iex.covers_to_copy(state) == []
