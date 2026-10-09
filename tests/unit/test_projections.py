"""Unit tests for the read projections: a reply never leaks."""

from __future__ import annotations

import json
import time

import ex.models as m
import ex.projections as pr
import pytest

NOW = "2026-10-05T12:00:00+00:00"
PERSONS = [
    {"person_id": "alice", "name": "Alice", "entity_id": "person.alice"},
    {"person_id": "bob", "name": "Bob", "entity_id": "person.bob"},
    {"person_id": "carol", "name": "Carol", "entity_id": "person.carol"},
]


def _state() -> dict:
    state = m.empty_state()
    state["rooms"]["r"] = {"id": "r", "name": "Den", "area_id": None, "order": 1}
    state["rooms"]["q"] = {"id": "q", "name": "Attic", "area_id": None, "order": 0}
    state["bookcases"]["k"] = {
        "id": "k",
        "room_id": "r",
        "name": "Left",
        "note": "",
        "order": 0,
    }
    state["shelves"]["s"] = {"id": "s", "bookcase_id": "k", "name": "Top", "order": 0}
    dune = m.build_book(
        {"title": "Dune", "authors": ["Frank Herbert"], "tags": ["sf"], "pages": 600},
        now=NOW,
    )
    dune["id"] = "dune"
    dune["isbn13"] = "9780441013593"
    emma = m.build_book({"title": "Emma", "series": "Austen"}, now=NOW)
    emma["id"] = "emma"
    emma["cover"] = {"kind": "custom", "file": "emma-0a1b2c3d.jpg"}
    state["books"] = {"dune": dune, "emma": emma}
    copy = m.build_copy(
        {
            "book_id": "dune",
            "shelf_id": "s",
            "price": 10,
            "value": 20,
            "acquired_from": "Shop",
        },
        now=NOW,
    )
    copy["id"] = "c1"
    state["copies"]["c1"] = copy
    loan = m.build_loan(
        {"direction": "out", "copy_id": "c1", "book_id": "dune", "party": "Zed"},
        today="2026-10-01",
    )
    loan["id"] = "l1"
    state["loans"]["l1"] = loan
    row = {**m.empty_reading(now=NOW), "status": "read", "private_notes": "secret"}
    state["reading"] = {
        "alice": {"dune": dict(row)},
        "bob": {"dune": {**row, "status": "reading"}},
        "carol": {"dune": {**row, "status": "want"}},
    }
    state["people"] = {"carol": {"share_reading": False}}
    return state


def test_cover_url() -> None:
    assert pr.cover_url({"id": "b", "cover": {"kind": "none", "file": None}}) is None
    assert pr.cover_url({"id": "b"}) is None
    assert pr.cover_url({"id": "b", "cover": {"kind": "custom", "file": None}}) is None
    assert pr.cover_url({"id": "b", "cover": {"kind": "none", "file": "b-1.jpg"}}) is (
        None
    )
    assert (
        pr.cover_url(
            {"id": "b", "cover": {"kind": "openlibrary", "file": "b-ab12.jpg"}}
        )
        == "/api/home_keeper_library/cover/b?v=ab12"
    )


def test_admin_reads_everything() -> None:
    state = _state()
    reply = pr.project_state(
        state,
        persons=PERSONS,
        viewer="alice",
        is_admin=True,
        viewer_name="Alice",
        currency="EUR",
        tab=True,
        revision=7,
    )
    assert reply["revision"] == 7 and reply["currency"] == "EUR"
    assert reply["me"] == {"person_id": "alice", "name": "Alice", "is_admin": True}
    assert reply["home_keeper"] == {"tab": True}
    assert [r["id"] for r in reply["rooms"]] == ["q", "r"]
    assert reply["copies"][0]["price"] == 10
    assert reply["loans"][0]["party"] == "Zed"
    dune = next(b for b in reply["books"] if b["id"] == "dune")
    assert set(dune["reading"]) == {"alice", "bob", "carol"}
    assert dune["reading"]["carol"]["private_notes"] == "secret"
    assert dune["owned"] is True and dune["copy_count"] == 1
    emma = next(b for b in reply["books"] if b["id"] == "emma")
    assert emma["owned"] is False and emma["cover_url"].endswith("?v=0a1b2c3d")
    assert [b["id"] for b in reply["books"]] == ["dune", "emma"]
    assert list(reply["people"]) == ["alice", "bob", "carol"]
    carol = reply["people"]["carol"]
    assert carol["share_reading"] is False and "wishlist_todo" in carol


def test_non_admin_projection_never_leaks() -> None:
    state = _state()
    reply = pr.project_state(
        state,
        persons=PERSONS,
        viewer="bob",
        is_admin=False,
        currency="EUR",
        tab=False,
        revision=1,
    )
    text = json.dumps(reply)
    for secret in ("Zed", "Shop", '"price"', '"value"', '"party"'):
        assert secret not in text, secret
    dune = next(b for b in reply["books"] if b["id"] == "dune")
    assert set(dune["reading"]) == {"alice", "bob"}
    assert dune["reading"]["bob"]["private_notes"] == "secret"
    assert "private_notes" not in dune["reading"]["alice"]
    copy = reply["copies"][0]
    assert not {"price", "value", "acquired_from"} & set(copy)
    assert "party" not in reply["loans"][0]
    alice = reply["people"]["alice"]
    bob = reply["people"]["bob"]
    assert "wishlist_todo" not in alice and "wishlist_todo" in bob
    assert reply["me"]["is_admin"] is False
    assert state["copies"]["c1"]["price"] == 10, "the projection must copy"


def test_wishlist_todo_ids_of_another_person_are_hidden() -> None:
    state = _state()
    entry = m.build_wishlist("alice", buy=True, now=NOW)
    entry |= {"todo_entity": "todo.alice", "todo_uid": "u1"}
    state["books"]["emma"]["wishlist"] = entry
    emma = state["books"]["emma"]
    for viewer, is_admin, hidden in (
        ("bob", False, True),
        (None, False, True),
        ("alice", False, False),
        ("bob", True, False),
    ):
        out = pr.project_book(state, emma, viewer=viewer, is_admin=is_admin)
        assert out["wishlist"]["person_id"] == "alice" and out["wishlist"]["buy"]
        assert ("todo_entity" in out["wishlist"]) is not hidden
        assert ("todo_uid" in out["wishlist"]) is not hidden
    assert emma["wishlist"]["todo_entity"] == "todo.alice", "the projection must copy"
    assert (
        pr.project_book(state, state["books"]["dune"], viewer="bob", is_admin=False)[
            "wishlist"
        ]
        is None
    )
    assert state["reading"]["alice"]["dune"]["private_notes"] == "secret"


def test_viewer_with_no_person() -> None:
    state = _state()
    rows = pr.visible_reading(state, "dune", viewer=None, is_admin=False)
    assert set(rows) == {"alice", "bob"}
    assert all("private_notes" not in row for row in rows.values())


def test_book_detail() -> None:
    state = _state()
    detail = pr.book_detail(state, "dune", viewer="bob", is_admin=False)
    assert detail["copies"][0]["location"] == ["Den", "Left", "Top"]
    assert "price" not in detail["copies"][0]
    assert "party" not in detail["loans"][0]
    assert pr.book_detail(state, "nope", viewer=None, is_admin=True) is None
    admin = pr.book_detail(state, "dune", viewer=None, is_admin=True)
    assert admin["copies"][0]["price"] == 10 and admin["loans"][0]["party"] == "Zed"


@pytest.mark.parametrize(
    ("filters", "ids"),
    [
        ({}, ["dune", "emma"]),
        ({"query": "herbert"}, ["dune"]),
        ({"query": "SF"}, ["dune"]),
        ({"query": "9780441013593"}, ["dune"]),
        ({"query": "austen"}, ["emma"]),
        ({"query": "zzz"}, []),
        ({"owned": True}, ["dune"]),
        ({"owned": False}, ["emma"]),
        ({"shelf_id": "s"}, ["dune"]),
        ({"shelf_id": "x"}, []),
        ({"room_id": "r"}, ["dune"]),
        ({"room_id": "q"}, []),
        ({"status": "read", "person_id": "alice"}, ["dune"]),
        ({"status": "want", "person_id": "alice"}, []),
        ({"limit": 1}, ["dune"]),
    ],
)
def test_list_books_filters(filters: dict, ids: list[str]) -> None:
    rows = pr.list_books(_state(), filters, viewer="alice", is_admin=True)
    assert [b["id"] for b in rows] == ids


def test_people_projection() -> None:
    rows = pr.project_people(_state(), PERSONS, viewer="alice", is_admin=True)
    assert rows[0] == {
        "person_id": "alice",
        "name": "Alice",
        "entity_id": "person.alice",
        "share_reading": True,
        "wishlist_todo": None,
        "yearly_goal": None,
    }


def test_stats() -> None:
    state = _state()
    state["reading"]["alice"]["dune"]["finished"] = "2026-03-01"
    state["reading"]["alice"]["emma"] = {
        **m.empty_reading(now=NOW),
        "status": "read",
        "finished": "2025-12-31",
    }
    assert pr.books_read_in_year(state, "alice", 2026) == (1, 600)
    assert pr.books_read_in_year(state, "alice", 2025) == (1, 0)
    assert pr.books_read_in_year(state, "nobody", 2026) == (0, 0)
    state["reading"]["bob"]["emma"] = {
        **m.empty_reading(now="2026-10-06"),
        "status": "reading",
    }
    state["reading"]["bob"]["gone"] = {**m.empty_reading(now=NOW), "status": "reading"}
    assert pr.reading_now(state, "bob") == ["Emma", "Dune"]
    state["reading"]["carol"]["emma"] = {**m.empty_reading(now="2026-01-01")}
    assert [b["id"] for b in pr.want_to_read(state, "carol")] == ["emma", "dune"]
    assert pr.owned_book_count(state) == 1
    assert pr.loans_out_count(state) == 1
    state["loans"]["l1"]["due"] = "2026-10-04"
    assert pr.loans_overdue_count(state, "2026-10-05") == 1
    assert pr.loans_overdue_count(state, "2026-10-04") == 0
    state["loans"]["l1"]["returned"] = "2026-10-05"
    assert pr.loans_out_count(state) == 0


def test_project_state_is_fast_for_5000_books() -> None:
    state = m.empty_state()
    for index in range(5000):
        book = m.build_book({"title": f"Book {index}", "authors": ["A"]}, now=NOW)
        state["books"][book["id"]] = book
        copy = m.build_copy({"book_id": book["id"]}, now=NOW)
        state["copies"][copy["id"]] = copy
        state["reading"].setdefault("alice", {})[book["id"]] = m.empty_reading(now=NOW)
    start = time.perf_counter()
    reply = pr.project_state(
        state,
        persons=PERSONS,
        viewer="bob",
        is_admin=False,
        currency="EUR",
        tab=True,
        revision=1,
    )
    pr.list_books(state, {"query": "book 4999"}, viewer="bob", is_admin=False)
    assert len(reply["books"]) == 5000
    assert time.perf_counter() - start < 2.0
