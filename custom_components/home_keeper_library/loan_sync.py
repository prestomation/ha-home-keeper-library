"""The Home Assistant side of the loan tasks in Home Keeper.

The pure planner is ``loan_tasks.py``. This module reads the tasks with
``home_keeper.list_tasks``, applies the plan with the Home Keeper services, and
writes the loan changes through the store. The contract is sections 1 to 6 of
``docs/INTEGRATING.md`` in Home Keeper:

* Each call to Home Keeper is guarded with ``has_service`` and sends
  ``origin: "home_keeper_library"``.
* ``home_keeper_task_completed`` with the source of a loan returns the loan.
  The event of a completion that the library sent itself has the library origin
  and is ignored, so there is no loop.
* ``home_keeper_task_deleted`` with the source of a loan clears its task id.
* A reconcile pass runs at setup, after each change of a loan, and when Home
  Keeper asks the companions to register again.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import loan_tasks
from .backend_i18n import resolve_string
from .const import (
    HOME_KEEPER_DOMAIN,
    HOME_KEEPER_EVENT_TASK_COMPLETED,
    HOME_KEEPER_EVENT_TASK_DELETED,
    ORIGIN,
)
from .models import LibraryError

if TYPE_CHECKING:
    from .coordinator import LibraryCoordinator

_LOGGER = logging.getLogger(__name__)


class LoanSync:
    """Keeps the Home Keeper tasks of the loans in step with the loans."""

    def __init__(self, hass: HomeAssistant, coordinator: LibraryCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._lock = asyncio.Lock()
        self._unsubs: list[Callable[[], None]] = []
        self._loans_seen: str = ""
        self._pending: asyncio.Task[None] | None = None
        # The Home Keeper link turns this on while Home Keeper takes loan tasks.
        self.enabled = False

    @callback
    def async_start(self) -> None:
        """Listen for the Home Keeper task events and the store changes."""
        bus = self._hass.bus
        self._unsubs.append(
            bus.async_listen(HOME_KEEPER_EVENT_TASK_COMPLETED, self._on_completed)
        )
        self._unsubs.append(
            bus.async_listen(HOME_KEEPER_EVENT_TASK_DELETED, self._on_deleted)
        )
        self._unsubs.append(
            self._coordinator.store.async_add_listener(self._on_store_change)
        )
        self.async_schedule()

    @callback
    def async_stop(self) -> None:
        """Stop the listeners."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._pending is not None:
            self._pending.cancel()
            self._pending = None

    def _loans_key(self) -> str:
        loans = self._coordinator.store.state["loans"]
        return repr(sorted((k, sorted(v.items())) for k, v in loans.items()))

    @callback
    def _on_store_change(self) -> None:
        key = self._loans_key()
        if key != self._loans_seen:
            self.async_schedule()

    @callback
    def async_schedule(self) -> None:
        """Run a reconcile pass soon."""
        if self._pending is not None and not self._pending.done():
            return
        self._pending = self._coordinator.config_entry.async_create_background_task(
            self._hass, self.async_reconcile(), "home_keeper_library loan sync"
        )

    def _available(self) -> bool:
        return self.enabled and self._hass.services.has_service(
            HOME_KEEPER_DOMAIN, "list_tasks"
        )

    async def _hk(
        self, service: str, data: dict[str, Any], *, response: bool = False
    ) -> Any:
        """Call a Home Keeper service. Return None if the call fails."""
        if not self._hass.services.has_service(HOME_KEEPER_DOMAIN, service):
            return None
        try:
            return await self._hass.services.async_call(
                HOME_KEEPER_DOMAIN,
                service,
                data,
                blocking=True,
                return_response=response,
            )
        except (HomeAssistantError, ValueError, vol.Invalid) as err:
            _LOGGER.debug("home_keeper.%s failed: %s", service, err)
            return None

    async def async_reconcile(self) -> None:
        """Make the Home Keeper tasks match the loans."""
        async with self._lock:
            for _ in range(2):
                if not await self._pass():
                    break
            self._loans_seen = self._loans_key()

    async def _pass(self) -> bool:
        if not self._available():
            return False
        response = await self._hk("list_tasks", {}, response=True)
        if not isinstance(response, dict) or not isinstance(
            response.get("tasks"), list
        ):
            return False
        store = self._coordinator.store
        plan = loan_tasks.plan_reconcile(store.state["loans"], response["tasks"])
        if plan.empty:
            return False
        lang = self._hass.config.language
        for op in plan.binds:
            await store.set_loan_task(op.loan_id, op.task_id)
        for add in plan.adds:
            loan = store.state["loans"].get(add.loan_id)
            if loan is None:
                continue
            book = store.state["books"].get(loan["book_id"]) or {}
            payload = loan_tasks.add_task_payload(
                loan,
                name=resolve_string(
                    lang,
                    loan_tasks.task_name_key(loan),
                    title=book.get("title", ""),
                    party=loan.get("party", ""),
                ),
                completion_prompt=resolve_string(lang, "loan_task.completion_prompt"),
                config_entry_id=self._coordinator.config_entry.entry_id,
            )
            result = await self._hk("add_task", payload, response=True)
            task_id = (
                (result or {}).get("task_id") if isinstance(result, dict) else None
            )
            if isinstance(task_id, str):
                await store.set_loan_task(add.loan_id, task_id)
        for complete in plan.completes:
            await self._hk(
                "complete_task", {"task_id": complete.task_id, "origin": ORIGIN}
            )
        for delete in plan.deletes:
            await self._hk("delete_task", {"task_id": delete.task_id, "force": True})
        for update in plan.due_updates:
            await self._hk(
                "update_task", {"task_id": update.task_id, "due": update.due}
            )
        for forget in plan.forgets:
            await store.forget_loan_task(forget.loan_id, disable=forget.disable)
        for ret in plan.returns:
            try:
                await store.return_loan(ret.loan_id, origin=ORIGIN)
            except LibraryError:
                continue
        return bool(plan.adds or plan.binds or plan.forgets or plan.returns)

    def _loan_of_event(self, event: Event[Any]) -> str | None:
        return loan_tasks.loan_id_of({"source": event.data.get("source")})

    @callback
    def _on_completed(self, event: Event[Any]) -> None:
        if not self.enabled or event.data.get("origin") == ORIGIN:
            return
        loan_id = self._loan_of_event(event)
        if loan_id is None:
            return
        self._hass.async_create_task(self._return(loan_id))

    async def _return(self, loan_id: str) -> None:
        store = self._coordinator.store
        loan = store.state["loans"].get(loan_id)
        if loan is None or loan.get("returned"):
            return
        await store.return_loan(loan_id, origin=ORIGIN)
        self._loans_seen = self._loans_key()

    @callback
    def _on_deleted(self, event: Event[Any]) -> None:
        if not self.enabled:
            return
        loan_id = self._loan_of_event(event)
        if loan_id is None:
            return
        loan = self._coordinator.store.state["loans"].get(loan_id)
        if loan is None or loan.get("hk_task_id") != event.data.get("task_id"):
            return
        self._hass.async_create_task(
            self._coordinator.store.forget_loan_task(loan_id, disable=True)
        )
