"""Unit tests for the pure wishlist to-do sync planner."""

from __future__ import annotations

import ex.models as m
import ex.wishlist as w

NOW = "2026-10-05T12:00:00+00:00"
LIST = "todo.books"


def _state(**entry) -> dict:
    state = m.empty_state()
    book = m.build_book({"title": "Dune", "authors": ["Frank Herbert"]}, now=NOW)
    book["id"] = "dune"
    book["wishlist"] = {**m.build_wishlist("p", buy=True, now=NOW), **entry}
    state["books"]["dune"] = book
    state["people"]["p"] = {"wishlist_todo": LIST}
    return state


def _item(uid: str, summary: str = "Dune by Frank Herbert", done: bool = False):
    return {
        "uid": uid,
        "summary": summary,
        "status": "completed" if done else "needs_action",
    }


def test_target_list() -> None:
    state = _state()
    assert w.target_list(state, state["books"]["dune"]) == LIST
    assert w.target_list(_state(buy=False), _state(buy=False)["books"]["dune"]) is None
    bought = _state(bought=True)
    assert w.target_list(bought, bought["books"]["dune"]) is None
    state["people"]["p"] = {"wishlist_todo": None}
    assert w.target_list(state, state["books"]["dune"]) is None
    state["books"]["dune"]["wishlist"] = None
    assert w.target_list(state, state["books"]["dune"]) is None


def test_lists_to_read() -> None:
    state = _state(todo_entity="todo.old", todo_uid="u")
    state["todo_orphans"] = [{"entity_id": "todo.gone", "uid": "x"}]
    assert w.lists_to_read(state) == ["todo.books", "todo.gone", "todo.old"]
    assert w.lists_to_read(m.empty_state()) == []


def test_add_then_bind() -> None:
    state = _state()
    plan = w.plan_sync(state, {LIST: []})
    assert plan.adds == [w.AddOp("dune", LIST, "Dune by Frank Herbert")]
    assert not plan.store_changes and not plan.empty
    plan = w.plan_sync(state, {LIST: [_item("u1")]})
    assert plan.binds == [w.BindOp("dune", LIST, "u1")] and plan.adds == []
    assert plan.store_changes


def test_template_changes_the_summary() -> None:
    plan = w.plan_sync(_state(), {LIST: []}, "{title} von {author}")
    assert plan.adds[0].summary == "Dune von Frank Herbert"


def test_bind_skips_completed_and_claimed_items() -> None:
    state = _state()
    other = m.build_book({"title": "Dune", "authors": ["Frank Herbert"]}, now=NOW)
    other["id"] = "aaa"
    other["wishlist"] = {
        **m.build_wishlist("p", buy=True, now=NOW),
        "todo_entity": LIST,
        "todo_uid": "u1",
    }
    state["books"]["aaa"] = other
    items = [_item("u1"), _item("u0", done=True), {"summary": "Dune by Frank Herbert"}]
    plan = w.plan_sync(state, {LIST: items})
    assert plan.binds == [] and plan.adds == [
        w.AddOp("dune", LIST, plan.adds[0].summary)
    ]


def test_unreadable_list_plans_nothing() -> None:
    assert w.plan_sync(_state(), {LIST: None}).empty
    assert w.plan_sync(_state(), {}).empty
    bound = _state(todo_entity=LIST, todo_uid="u1")
    assert w.plan_sync(bound, {LIST: None}).empty


def test_bound_item_states() -> None:
    bound = _state(todo_entity=LIST, todo_uid="u1")
    assert w.plan_sync(bound, {LIST: [_item("u1")]}).empty
    plan = w.plan_sync(bound, {LIST: [_item("u1", done=True)]})
    assert plan.bought == [w.BoughtOp("dune")] and plan.removes == []
    plan = w.plan_sync(bound, {LIST: []})
    assert plan.unbinds == [w.UnbindOp("dune", buy_off=True)]


def test_unwanted_item_is_removed_unless_completed() -> None:
    off = _state(buy=False, todo_entity=LIST, todo_uid="u1")
    plan = w.plan_sync(off, {LIST: [_item("u1")]})
    assert plan.removes == [w.RemoveOp(LIST, "u1")]
    assert plan.unbinds == [w.UnbindOp("dune")]
    plan = w.plan_sync(off, {LIST: [_item("u1", done=True)]})
    assert plan.removes == [] and plan.unbinds == [w.UnbindOp("dune")]
    moved = _state(todo_entity="todo.old", todo_uid="u1")
    plan = w.plan_sync(moved, {LIST: [], "todo.old": [_item("u1")]})
    assert plan.removes == [w.RemoveOp("todo.old", "u1")]
    assert plan.unbinds == [w.UnbindOp("dune")]


def test_orphans() -> None:
    state = m.empty_state()
    state["todo_orphans"] = [
        {"entity_id": LIST, "uid": "open"},
        {"entity_id": LIST, "uid": "done"},
        {"entity_id": LIST, "uid": "gone"},
        {"entity_id": "todo.x", "uid": "y"},
    ]
    items = [_item("open"), _item("done", done=True)]
    plan = w.plan_sync(state, {LIST: items, "todo.x": None})
    assert plan.removes == [w.RemoveOp(LIST, "open")]
    assert plan.drop_orphans == [
        w.DropOrphanOp(LIST, "open"),
        w.DropOrphanOp(LIST, "done"),
        w.DropOrphanOp(LIST, "gone"),
    ]
    assert plan.store_changes


def test_plan_flags() -> None:
    assert w.SyncPlan().empty and not w.SyncPlan().store_changes
    assert not w.SyncPlan(removes=[w.RemoveOp(LIST, "u")]).empty
    assert w.SyncPlan(unbinds=[w.UnbindOp("b")]).store_changes
    assert w.SyncPlan(bought=[w.BoughtOp("b")]).store_changes
