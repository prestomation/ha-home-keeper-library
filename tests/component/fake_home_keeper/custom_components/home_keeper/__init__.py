"""A small fake of Home Keeper for the component tier of the library.

The library calls these Home Keeper services: ``add_task``, ``update_task``,
``complete_task``, ``delete_task``, ``list_tasks`` and ``register_companion``.
It also imports ``panel_tabs``. This fake has the same service names, fields
and events as Home Keeper (``docs/INTEGRATING.md`` sections 1 to 6), and keeps
the tasks in memory.

The fake is used in place of the real Home Keeper because the real one has its
own storage, frontend, entity platforms and the Babel requirement, and it
reloads its entry on some task changes. That makes each test slower and less
exact about which call the library made. The Docker tier runs the library with
the real Home Keeper, so the contract is also checked against the real code.
"""

from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.typing import ConfigType

DOMAIN = "home_keeper"
DATA = "home_keeper_fake"


def _tasks(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    return hass.data.setdefault(DATA, {"tasks": {}, "companions": {}, "calls": []})[
        "tasks"
    ]


def _event_data(task: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "name": task["name"],
        "source": task.get("source") or {},
        "managed_by": task.get("managed_by"),
        "origin": origin,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the fake services."""
    data = hass.data.setdefault(DATA, {"tasks": {}, "companions": {}, "calls": []})

    def _record(name: str, call: ServiceCall) -> None:
        data["calls"].append((name, dict(call.data)))

    async def add_task(call: ServiceCall) -> dict[str, Any]:
        _record("add_task", call)
        task = {
            "id": uuid.uuid4().hex,
            "name": call.data["name"],
            "recurrence_type": call.data.get("recurrence_type"),
            "due": call.data.get("due"),
            "next_due": call.data.get("due"),
            "last_completed": None,
            "source": dict(call.data.get("source") or {}),
            "managed_by": call.data.get("managed_by"),
        }
        _tasks(hass)[task["id"]] = task
        hass.bus.async_fire("home_keeper_task_created", _event_data(task))
        return {"task_id": task["id"]}

    async def update_task(call: ServiceCall) -> None:
        _record("update_task", call)
        task = _tasks(hass)[call.data["task_id"]]
        if "due" in call.data:
            task["due"] = task["next_due"] = call.data["due"]

    async def complete_task(call: ServiceCall) -> None:
        _record("complete_task", call)
        task = _tasks(hass)[call.data["task_id"]]
        task["last_completed"] = "2026-10-05T12:00:00+00:00"
        task["next_due"] = None
        hass.bus.async_fire(
            "home_keeper_task_completed", _event_data(task, call.data.get("origin"))
        )

    async def delete_task(call: ServiceCall) -> None:
        _record("delete_task", call)
        task = _tasks(hass).pop(call.data["task_id"], None)
        if task is not None:
            hass.bus.async_fire("home_keeper_task_deleted", _event_data(task))

    async def list_tasks(call: ServiceCall) -> dict[str, Any]:
        return {"tasks": [dict(t) for t in _tasks(hass).values()]}

    async def register_companion(call: ServiceCall) -> None:
        _record("register_companion", call)
        data["companions"][call.data["domain"]] = dict(call.data)

    for name, handler, response in (
        ("add_task", add_task, SupportsResponse.OPTIONAL),
        ("update_task", update_task, SupportsResponse.NONE),
        ("complete_task", complete_task, SupportsResponse.NONE),
        ("delete_task", delete_task, SupportsResponse.NONE),
        ("list_tasks", list_tasks, SupportsResponse.ONLY),
        ("register_companion", register_companion, SupportsResponse.NONE),
    ):
        hass.services.async_register(DOMAIN, name, handler, supports_response=response)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Any) -> bool:
    """Load the config entry. The services exist without it, as in Home Keeper."""
    hass.bus.async_fire("home_keeper_register_companions")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Any) -> bool:
    """Unload the config entry."""
    return True
