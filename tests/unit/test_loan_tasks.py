"""Unit tests for the pure loan task planner."""

from __future__ import annotations

import ex.loan_tasks as lt


def _loan(**fields) -> dict:
    base = {
        "id": "l1",
        "direction": "out",
        "due": "2026-11-01",
        "returned": None,
        "add_task": True,
        "hk_task_id": None,
    }
    return {**base, **fields}


def _task(task_id: str = "t1", loan_id: str | None = "l1", **fields) -> dict:
    source = {"home_keeper_library": {"loan_id": loan_id}} if loan_id else {}
    base = {"id": task_id, "source": source, "due": "2026-11-01", "next_due": None}
    base.setdefault("last_completed", None)
    base["next_due"] = base["due"]
    return {**base, **fields}


def test_helpers() -> None:
    assert lt.loan_id_of(_task()) == "l1"
    assert lt.loan_id_of({"source": None}) is None
    assert lt.loan_id_of({"source": {"home_keeper_library": "x"}}) is None
    assert lt.loan_id_of({"source": {"home_keeper_library": {"loan_id": ""}}}) is None
    assert lt.loan_id_of({"source": {"other": {"loan_id": "l1"}}}) is None
    assert lt.task_is_completed({"next_due": None, "last_completed": "t"})
    assert not lt.task_is_completed({"next_due": "d", "last_completed": "t"})
    assert not lt.task_is_completed({"next_due": None, "last_completed": None})
    assert lt.wants_task(_loan())
    assert not lt.wants_task(_loan(add_task=False))
    assert not lt.wants_task(_loan(due=None))
    assert not lt.wants_task(_loan(returned="2026-10-05"))
    assert lt.task_name_key(_loan()) == "loan_task.name_out"
    assert lt.task_name_key(_loan(direction="in")) == "loan_task.name_in"


def test_add_task_payload() -> None:
    payload = lt.add_task_payload(
        _loan(), name="Get Dune back", completion_prompt="Prompt", config_entry_id="e"
    )
    assert payload == {
        "name": "Get Dune back",
        "recurrence_type": "one-off",
        "due": "2026-11-01",
        "source": {"home_keeper_library": {"loan_id": "l1"}},
        "managed_by": {
            "integration": "home_keeper_library",
            "display_name": "Home Keeper Library",
            "icon": "mdi:bookshelf",
            "config_entry_id": "e",
            "locked_fields": ["name", "recurrence_type"],
            "completion_prompt": "Prompt",
        },
    }


def test_add_and_bind() -> None:
    plan = lt.plan_reconcile({"l1": _loan()}, [])
    assert plan.adds == [lt.AddTaskOp("l1")] and not plan.empty
    plan = lt.plan_reconcile({"l1": _loan()}, [_task()])
    assert plan.binds == [lt.BindTaskOp("l1", "t1")] and plan.adds == []
    assert lt.plan_reconcile({"l1": _loan(due=None)}, []).empty
    assert lt.plan_reconcile({"l1": _loan(add_task=False)}, []).empty


def test_bound_open_loan() -> None:
    loans = {"l1": _loan(hk_task_id="t1")}
    assert lt.plan_reconcile(loans, [_task()]).empty
    plan = lt.plan_reconcile(loans, [_task(due="2026-10-20T00:00:00+00:00")])
    assert plan.due_updates == [lt.UpdateDueOp("t1", "2026-11-01")]
    plan = lt.plan_reconcile(loans, [_task(next_due=None, last_completed="x")])
    assert plan.returns == [lt.ReturnLoanOp("l1")]
    plan = lt.plan_reconcile({"l1": _loan(hk_task_id="t1", due=None)}, [_task()])
    assert plan.deletes == [lt.DeleteTaskOp("t1")]
    assert plan.forgets == [lt.ForgetTaskOp("l1", disable=False)]
    plan = lt.plan_reconcile({"l1": _loan(hk_task_id="t1", add_task=False)}, [_task()])
    assert plan.deletes == [lt.DeleteTaskOp("t1")]


def test_missing_task_is_added_again() -> None:
    plan = lt.plan_reconcile({"l1": _loan(hk_task_id="t9")}, [])
    assert plan.adds == [lt.AddTaskOp("l1")] and plan.forgets == []
    plan = lt.plan_reconcile({"l1": _loan(hk_task_id="t9", add_task=False)}, [])
    assert plan.forgets == [lt.ForgetTaskOp("l1", disable=False)]
    assert plan.adds == []
    returned = _loan(hk_task_id="t9", returned="2026-10-05")
    assert lt.plan_reconcile({"l1": returned}, []).forgets == [
        lt.ForgetTaskOp("l1", disable=False)
    ]


def test_returned_loan_completes_its_task() -> None:
    loans = {"l1": _loan(hk_task_id="t1", returned="2026-10-05")}
    plan = lt.plan_reconcile(loans, [_task()])
    assert plan.completes == [lt.CompleteTaskOp("t1")]
    done = _task(next_due=None, last_completed="x")
    assert lt.plan_reconcile(loans, [done]).empty
    unbound = {"l1": _loan(returned="2026-10-05")}
    plan = lt.plan_reconcile(unbound, [_task()])
    assert plan.binds == [lt.BindTaskOp("l1", "t1")]
    assert plan.completes == [lt.CompleteTaskOp("t1")]
    assert lt.plan_reconcile(unbound, []).empty


def test_orphan_tasks_are_deleted() -> None:
    plan = lt.plan_reconcile({}, [_task("t1", "gone"), _task("t2", None)])
    assert plan.deletes == [lt.DeleteTaskOp("t1")]
    assert lt.plan_reconcile({}, [{"source": {}}]).empty


def test_tasks_with_no_id_are_left_alone() -> None:
    no_id = _task()
    del no_id["id"]
    for task in (no_id, _task("")):
        assert lt.plan_reconcile({}, [task]).empty
        plan = lt.plan_reconcile({"l1": _loan()}, [task])
        assert plan.adds == [lt.AddTaskOp("l1")] and plan.binds == []


def test_plan_empty_flag() -> None:
    assert lt.LoanTaskPlan().empty
    for field, op in (
        ("adds", lt.AddTaskOp("l")),
        ("binds", lt.BindTaskOp("l", "t")),
        ("completes", lt.CompleteTaskOp("t")),
        ("deletes", lt.DeleteTaskOp("t")),
        ("due_updates", lt.UpdateDueOp("t", "d")),
        ("forgets", lt.ForgetTaskOp("l")),
        ("returns", lt.ReturnLoanOp("l")),
    ):
        assert not lt.LoanTaskPlan(**{field: [op]}).empty, field
