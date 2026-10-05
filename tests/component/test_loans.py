"""Component tests: loans, their Home Keeper tasks and the overdue event."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

BOB = "p_bob"


def _fake(hass) -> dict:
    return hass.data["home_keeper_fake"]


def _calls(hass, name: str) -> list[dict]:
    return [data for call, data in _fake(hass)["calls"] if call == name]


async def _copy(call) -> dict:
    book = (await call("add_book", {"title": "Dune", "lookup": False}))["book"]
    return (await call("add_copy", {"book_id": book["id"]}))["copy"]


async def test_lend_adds_a_home_keeper_task(hass, setup_entry, call) -> None:
    copy = await _copy(call)
    started = async_capture_events(hass, "home_keeper_library_loan_started")
    reply = await call(
        "lend_book", {"copy_id": copy["id"], "party": "Zed", "due": "2026-12-01"}
    )
    loan = reply["loan"]
    assert loan["direction"] == "out" and loan["hk_task_id"]
    assert started[0].data["party"] == "Zed" and started[0].data["due"] == "2026-12-01"
    add = _calls(hass, "add_task")[0]
    assert add["name"] == "Get Dune back from Zed"
    assert add["recurrence_type"] == "one-off" and add["due"] == "2026-12-01"
    assert add["source"] == {"home_keeper_library": {"loan_id": loan["id"]}}
    assert add["managed_by"]["integration"] == "home_keeper_library"
    assert add["managed_by"]["config_entry_id"] == setup_entry.entry_id
    assert add["managed_by"]["locked_fields"] == ["name", "recurrence_type"]
    assert add["managed_by"]["completion_prompt"] == "Completing returns the loan."
    returned = async_capture_events(hass, "home_keeper_library_loan_returned")
    reply = await call("return_loan", {"loan_id": loan["id"]})
    assert reply["loan"]["returned"] == dt_util.now().date().isoformat()
    complete = _calls(hass, "complete_task")
    assert complete == [
        {"task_id": loan["hk_task_id"], "origin": "home_keeper_library"}
    ]
    assert len(returned) == 1, "the echo of our completion returns nothing again"
    await call("return_loan", {"loan_id": loan["id"]})
    assert len(returned) == 1


async def test_no_task_without_a_due_date_or_add_task(hass, setup_entry, call) -> None:
    copy = await _copy(call)
    loan = (await call("lend_book", {"copy_id": copy["id"], "party": "Zed"}))["loan"]
    assert loan["hk_task_id"] is None and _calls(hass, "add_task") == []
    reply = await call("update_loan", {"loan_id": loan["id"], "due": "2026-12-01"})
    assert reply["loan"]["hk_task_id"]
    reply = await call("update_loan", {"loan_id": loan["id"], "due": "2026-12-24"})
    assert _calls(hass, "update_task")[-1] == {
        "task_id": reply["loan"]["hk_task_id"],
        "due": "2026-12-24",
    }
    await call("return_loan", {"loan_id": loan["id"]})
    second = await _copy(call)
    other = await call(
        "lend_book",
        {
            "copy_id": second["id"],
            "party": "Al",
            "due": "2026-12-01",
            "add_task": False,
        },
    )
    assert other["loan"]["hk_task_id"] is None


async def test_completion_in_home_keeper_returns_the_loan(
    hass, setup_entry, call
) -> None:
    copy = await _copy(call)
    loan = (
        await call(
            "lend_book", {"copy_id": copy["id"], "party": "Zed", "due": "2026-12-01"}
        )
    )["loan"]
    await hass.services.async_call(
        "home_keeper", "complete_task", {"task_id": loan["hk_task_id"]}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    stored = setup_entry.runtime_data.store.state["loans"][loan["id"]]
    assert stored["returned"] is not None
    assert len(_calls(hass, "complete_task")) == 1, "no echo back to Home Keeper"


async def test_delete_in_home_keeper_and_in_the_library(
    hass, setup_entry, call
) -> None:
    copy = await _copy(call)
    loan = (
        await call(
            "lend_book", {"copy_id": copy["id"], "party": "Zed", "due": "2026-12-01"}
        )
    )["loan"]
    await hass.services.async_call(
        "home_keeper", "delete_task", {"task_id": loan["hk_task_id"]}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    stored = setup_entry.runtime_data.store.state["loans"][loan["id"]]
    assert stored["hk_task_id"] is None and stored["add_task"] is False
    await setup_entry.runtime_data.loan_sync.async_reconcile()
    assert len(_calls(hass, "add_task")) == 1, "a deleted task is not added again"
    second = await _copy(call)
    other = (
        await call(
            "lend_book", {"copy_id": second["id"], "party": "Al", "due": "2026-12-01"}
        )
    )["loan"]
    await call("delete_loan", {"loan_id": other["id"]})
    assert {"task_id": other["hk_task_id"], "force": True} in _calls(
        hass, "delete_task"
    )


async def test_borrow_book_sets_reading(hass, setup_entry, call) -> None:
    reply = await call(
        "borrow_book",
        {
            "title": "Emma",
            "authors": ["Jane Austen"],
            "party": "City library",
            "person_id": BOB,
            "due": "2026-11-01",
            "format": "ebook",
        },
    )
    loan = reply["loan"]
    assert loan["direction"] == "in" and loan["copy_id"] is None
    assert loan["person_id"] == BOB and loan["format"] == "ebook"
    assert reply["book"]["owned"] is False
    assert reply["book"]["reading"][BOB]["status"] == "reading"
    add = _calls(hass, "add_task")[0]
    assert add["name"] == "Return Emma to City library"


async def test_reconcile_at_setup(hass, setup_entry, call) -> None:
    copy = await _copy(call)
    loan = (
        await call(
            "lend_book", {"copy_id": copy["id"], "party": "Zed", "due": "2026-12-01"}
        )
    )["loan"]
    # A task with our source but no loan is deleted. A completed task returns
    # the loan. Both happen at the next setup.
    tasks = _fake(hass)["tasks"]
    tasks["orphan"] = {
        "id": "orphan",
        "name": "x",
        "source": {"home_keeper_library": {"loan_id": "gone"}},
        "next_due": "2026-01-01",
        "last_completed": None,
    }
    tasks[loan["hk_task_id"]].update(next_due=None, last_completed="2026-10-05")
    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "orphan" not in tasks
    stored = setup_entry.runtime_data.store.state["loans"][loan["id"]]
    assert stored["returned"] is not None


async def test_overdue_fires_once(hass, setup_entry, call, freezer) -> None:
    copy = await _copy(call)
    today = dt_util.now().date()
    loan = (
        await call(
            "lend_book",
            {
                "copy_id": copy["id"],
                "party": "Zed",
                "started": (today - timedelta(days=10)).isoformat(),
                "due": (today + timedelta(days=1)).isoformat(),
                "add_task": False,
            },
        )
    )["loan"]
    overdue = async_capture_events(hass, "home_keeper_library_loan_overdue")
    freezer.tick(timedelta(days=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(overdue) == 1 and overdue[0].data["loan_id"] == loan["id"]
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(overdue) == 1
    entity = "sensor.home_keeper_library_loans_overdue"
    assert hass.states.get(entity).state == "1"
    assert hass.states.get("sensor.home_keeper_library_loans_out").state == "1"


async def test_home_keeper_removed_and_back(hass, setup_entry, call, hk_entry) -> None:
    """Home Keeper goes away and comes back: issue, tab, companion and tasks."""
    from homeassistant.helpers import issue_registry as ir
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    first = await _copy(call)
    kept = (
        await call(
            "lend_book", {"copy_id": first["id"], "party": "Zed", "due": "2026-12-01"}
        )
    )["loan"]
    second = await _copy(call)
    lost = (
        await call(
            "lend_book", {"copy_id": second["id"], "party": "Al", "due": "2026-12-02"}
        )
    )["loan"]
    assert await hass.config_entries.async_remove(hk_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    registry = ir.async_get(hass)
    assert registry.async_get_issue("home_keeper_library", "home_keeper_not_set_up")
    assert hass.data["home_keeper_panel_tabs"].tabs() == []
    assert setup_entry.runtime_data.loan_sync.enabled is False
    # Loan changes while Home Keeper is gone make no Home Keeper call.
    calls = len(_fake(hass)["calls"])
    await call("return_loan", {"loan_id": kept["id"]})
    await call("update_loan", {"loan_id": kept["id"], "note": "x"})
    assert len(_fake(hass)["calls"]) == calls
    # The task of the open loan is gone when Home Keeper comes back.
    _fake(hass)["tasks"].pop(lost["hk_task_id"])
    registered = len(_calls(hass, "register_companion"))
    entry = MockConfigEntry(domain="home_keeper", title="Home Keeper")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not registry.async_get_issue("home_keeper_library", "home_keeper_not_set_up")
    assert len(hass.data["home_keeper_panel_tabs"].tabs()) == 1
    assert len(_calls(hass, "register_companion")) > registered
    loans = setup_entry.runtime_data.store.state["loans"]
    assert loans[lost["id"]]["hk_task_id"] not in (None, lost["hk_task_id"])
    assert loans[lost["id"]]["hk_task_id"] in _fake(hass)["tasks"]
    # The returned loan keeps its task id and its task is completed now.
    assert loans[kept["id"]]["hk_task_id"] == kept["hk_task_id"]
    assert _fake(hass)["tasks"][kept["hk_task_id"]]["next_due"] is None


async def test_disabled_home_keeper_entry(hass, setup_entry, hk_entry) -> None:
    from homeassistant.config_entries import ConfigEntryDisabler
    from homeassistant.helpers import issue_registry as ir

    await hass.config_entries.async_set_disabled_by(
        hk_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    issue = ir.async_get(hass).async_get_issue(
        "home_keeper_library", "home_keeper_not_set_up"
    )
    assert issue is not None and issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert setup_entry.runtime_data.tab_registered is False
    await hass.config_entries.async_set_disabled_by(hk_entry.entry_id, None)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert setup_entry.runtime_data.tab_registered is True
