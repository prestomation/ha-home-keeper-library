"""The Home Assistant side of the wishlist to-do sync.

The pure planner is ``wishlist.py``. This module reads the lists with
``todo.get_items``, applies the plan with ``todo.add_item`` and
``todo.remove_item``, and writes the store steps through the store. A pass runs
after each store change, when a list in use changes state, and every 10
minutes. Each ``todo`` call is best effort: a failed call is tried again on the
next pass, and it never fails the change that started the pass.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .backend_i18n import resolve_string
from .wishlist import lists_to_read, plan_sync

if TYPE_CHECKING:
    from .coordinator import LibraryCoordinator

_LOGGER = logging.getLogger(__name__)
TODO_DOMAIN = "todo"
SWEEP_INTERVAL = timedelta(minutes=10)
# A pass after an add reads the list again to bind the new item.
_MAX_PASSES = 3


class WishlistSync:
    """Keeps the wishlist to-do lists in step with the wishlist."""

    def __init__(self, hass: HomeAssistant, coordinator: LibraryCoordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._lock = asyncio.Lock()
        self._unsubs: list[Callable[[], None]] = []
        self._track: Callable[[], None] | None = None
        self._tracked: tuple[str, ...] = ()
        self._pending: asyncio.Task[None] | None = None

    @callback
    def async_start(self) -> None:
        """Start the sweep and the store listener."""
        store = self._coordinator.store
        self._unsubs.append(store.async_add_listener(self.async_schedule))
        self._unsubs.append(
            async_track_time_interval(
                self._hass, self._sweep, SWEEP_INTERVAL, cancel_on_shutdown=True
            )
        )
        self.async_schedule()

    @callback
    def async_stop(self) -> None:
        """Stop the listeners."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._track is not None:
            self._track()
            self._track = None
        if self._pending is not None:
            self._pending.cancel()
            self._pending = None

    @callback
    def _sweep(self, _now: Any) -> None:
        self.async_schedule()

    @callback
    def async_schedule(self) -> None:
        """Run a pass soon. A pass that waits already covers this call."""
        if self._pending is not None and not self._pending.done():
            return
        self._pending = self._coordinator.entry.async_create_background_task(
            self._hass, self.async_run(), "home_keeper_library wishlist sync"
        )

    async def async_run(self) -> None:
        """Run passes until a pass has no step, at most ``_MAX_PASSES`` times."""
        async with self._lock:
            for _ in range(_MAX_PASSES):
                if not await self._pass():
                    break

    async def _read(self, entity_id: str) -> list[dict[str, Any]] | None:
        if self._hass.states.get(entity_id) is None:
            return None
        try:
            response = await self._hass.services.async_call(
                TODO_DOMAIN,
                "get_items",
                {},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.debug("Cannot read the list %s: %s", entity_id, err)
            return None
        block = (response or {}).get(entity_id)
        items = block.get("items") if isinstance(block, dict) else None
        return (
            [i for i in items if isinstance(i, dict)]
            if isinstance(items, list)
            else None
        )

    async def _call(self, service: str, entity_id: str, item: str) -> bool:
        try:
            await self._hass.services.async_call(
                TODO_DOMAIN,
                service,
                {"item": item},
                target={"entity_id": entity_id},
                blocking=True,
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.debug("todo.%s on %s failed: %s", service, entity_id, err)
            return False
        return True

    async def _pass(self) -> bool:
        """Run 1 pass. Return whether it added an item or changed the store."""
        state = self._coordinator.store.state
        wanted = lists_to_read(state)
        self._follow(tuple(wanted))
        if not wanted:
            return False
        lists = {entity_id: await self._read(entity_id) for entity_id in wanted}
        template = resolve_string(self._hass.config.language, "item.summary")
        plan = plan_sync(self._coordinator.store.state, lists, template)
        if plan.empty:
            return False
        for remove in plan.removes:
            await self._call("remove_item", remove.entity_id, remove.uid)
        added = False
        for add in plan.adds:
            added |= await self._call("add_item", add.entity_id, add.summary)
        await self._coordinator.store.apply_wishlist_plan(plan)
        return added or plan.store_changes

    @callback
    def _follow(self, entity_ids: tuple[str, ...]) -> None:
        """Run a pass when a list in use changes state."""
        if entity_ids == self._tracked:
            return
        if self._track is not None:
            self._track()
            self._track = None
        self._tracked = entity_ids
        if not entity_ids:
            return

        @callback
        def _changed(_event: Event[Any]) -> None:
            self.async_schedule()

        self._track = async_track_state_change_event(
            self._hass, list(entity_ids), _changed
        )
