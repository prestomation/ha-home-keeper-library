"""Pure planner for the Home Keeper tasks of the loans.

A loan with ``add_task: true`` and a due date has 1 one-off task in Home Keeper.
The task holds ``source = {"home_keeper_library": {"loan_id": <id>}}``.
``loan_sync.py`` reads the tasks with ``home_keeper.list_tasks``, calls
:func:`plan_reconcile`, and applies the plan through the Home Keeper services
and the store. The contract is ``docs/INTEGRATING.md`` of Home Keeper.

* An open loan that wants a task and has none gets 1. A task that already holds
  the loan id in its source is bound and not added again.
* A returned loan completes its open task.
* A task whose loan is deleted is deleted.
* A task that the user deletes in Home Keeper while the library runs is not
  added again: the event turns ``add_task`` off. A task that is gone for another
  reason, for example while Home Keeper was not loaded, is added again.
* A task that the user completed in Home Keeper returns its loan.

This module imports no Home Assistant code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import DOMAIN, ICON, NAME
from .models import is_open

SOURCE_KEY = DOMAIN


@dataclass(frozen=True)
class AddTaskOp:
    """Add the task of a loan."""

    loan_id: str


@dataclass(frozen=True)
class BindTaskOp:
    """Record the id of the task that holds a loan."""

    loan_id: str
    task_id: str


@dataclass(frozen=True)
class CompleteTaskOp:
    """Complete the task of a returned loan."""

    task_id: str


@dataclass(frozen=True)
class DeleteTaskOp:
    """Delete a task whose loan does not exist or wants no task."""

    task_id: str


@dataclass(frozen=True)
class UpdateDueOp:
    """Move the due date of a task to the due date of its loan."""

    task_id: str
    due: str


@dataclass(frozen=True)
class ForgetTaskOp:
    """Clear the task id of a loan.

    ``disable`` also turns ``add_task`` off, so that the planner adds no other
    task. It is set when the user deleted the task in Home Keeper.
    """

    loan_id: str
    disable: bool = True


@dataclass(frozen=True)
class ReturnLoanOp:
    """The task of an open loan is completed: return the loan."""

    loan_id: str


@dataclass
class LoanTaskPlan:
    """The steps of 1 reconcile pass."""

    adds: list[AddTaskOp] = field(default_factory=list)
    binds: list[BindTaskOp] = field(default_factory=list)
    completes: list[CompleteTaskOp] = field(default_factory=list)
    deletes: list[DeleteTaskOp] = field(default_factory=list)
    due_updates: list[UpdateDueOp] = field(default_factory=list)
    forgets: list[ForgetTaskOp] = field(default_factory=list)
    returns: list[ReturnLoanOp] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        """Whether the plan has no step."""
        return not any(
            (
                self.adds,
                self.binds,
                self.completes,
                self.deletes,
                self.due_updates,
                self.forgets,
                self.returns,
            )
        )


def loan_id_of(task: dict[str, Any]) -> str | None:
    """The loan id in the source of a Home Keeper task, if it has one."""
    source = task.get("source")
    if not isinstance(source, dict):
        return None
    ours = source.get(SOURCE_KEY)
    if not isinstance(ours, dict):
        return None
    loan_id = ours.get("loan_id")
    return loan_id if isinstance(loan_id, str) and loan_id else None


def task_is_completed(task: dict[str, Any]) -> bool:
    """Whether a one-off task is completed: it has a completion and no due date."""
    return task.get("next_due") is None and bool(task.get("last_completed"))


def wants_task(loan: dict[str, Any]) -> bool:
    """Whether a loan needs a task now."""
    return bool(loan.get("add_task")) and is_open(loan) and bool(loan.get("due"))


def task_name_key(loan: dict[str, Any]) -> str:
    """The backend string key of the task name of a loan."""
    return (
        "loan_task.name_out" if loan.get("direction") == "out" else "loan_task.name_in"
    )


def add_task_payload(
    loan: dict[str, Any],
    *,
    name: str,
    completion_prompt: str,
    config_entry_id: str,
) -> dict[str, Any]:
    """The data of the ``home_keeper.add_task`` call for a loan."""
    return {
        "name": name,
        "recurrence_type": "one-off",
        "due": loan["due"],
        "source": {SOURCE_KEY: {"loan_id": loan["id"]}},
        "managed_by": {
            "integration": DOMAIN,
            "display_name": NAME,
            "icon": ICON,
            "config_entry_id": config_entry_id,
            "locked_fields": ["name", "recurrence_type"],
            "completion_prompt": completion_prompt,
        },
    }


def _due_date(task: dict[str, Any]) -> str | None:
    value = task.get("due") or task.get("next_due")
    return value[:10] if isinstance(value, str) else None


def plan_reconcile(
    loans: dict[str, dict[str, Any]], tasks: list[dict[str, Any]]
) -> LoanTaskPlan:
    """The steps that make the Home Keeper tasks match the loans."""
    plan = LoanTaskPlan()
    by_id = {t["id"]: t for t in tasks if isinstance(t.get("id"), str)}
    ours: dict[str, list[dict[str, Any]]] = {}
    for item in tasks:
        if (loan_id := loan_id_of(item)) is not None:
            ours.setdefault(loan_id, []).append(item)

    for loan_id in sorted(loans):
        loan = loans[loan_id]
        task_id = loan.get("hk_task_id")
        task: dict[str, Any] | None = by_id.get(task_id) if task_id else None
        if task_id and task is None:
            # The task is gone, for example while Home Keeper was not loaded. A
            # loan that still wants a task gets a new one. A deletion while the
            # library runs turns add_task off first (loan_sync._on_deleted).
            if wants_task(loan):
                plan.adds.append(AddTaskOp(loan_id))
            else:
                plan.forgets.append(ForgetTaskOp(loan_id, disable=False))
            continue
        if task is None:
            candidates = [t for t in ours.get(loan_id, []) if t.get("id")]
            if candidates:
                task = candidates[0]
                plan.binds.append(BindTaskOp(loan_id, task["id"]))
            elif wants_task(loan):
                plan.adds.append(AddTaskOp(loan_id))
                continue
            else:
                continue
        if is_open(loan):
            if task_is_completed(task):
                plan.returns.append(ReturnLoanOp(loan_id))
            elif not loan.get("due") or not loan.get("add_task"):
                plan.deletes.append(DeleteTaskOp(task["id"]))
                plan.forgets.append(ForgetTaskOp(loan_id, disable=False))
            elif _due_date(task) != loan["due"]:
                plan.due_updates.append(UpdateDueOp(task["id"], loan["due"]))
        elif not task_is_completed(task):
            plan.completes.append(CompleteTaskOp(task["id"]))

    for loan_id, owned in sorted(ours.items()):
        if loan_id in loans:
            continue
        for task in owned:
            plan.deletes.append(DeleteTaskOp(task["id"]))
    return plan


__all__ = [
    "AddTaskOp",
    "BindTaskOp",
    "CompleteTaskOp",
    "DeleteTaskOp",
    "ForgetTaskOp",
    "LoanTaskPlan",
    "ReturnLoanOp",
    "UpdateDueOp",
    "add_task_payload",
    "loan_id_of",
    "plan_reconcile",
    "task_is_completed",
    "task_name_key",
    "wants_task",
]
