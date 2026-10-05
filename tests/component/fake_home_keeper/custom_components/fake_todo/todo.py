"""The in-memory to-do list entity."""

from __future__ import annotations

import uuid

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the list."""
    async_add_entities([MemoryList(entry)])


class MemoryList(TodoListEntity):
    """A to-do list in memory."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id
        self._attr_todo_items: list[TodoItem] = []

    async def async_create_todo_item(self, item: TodoItem) -> None:
        self._attr_todo_items.append(
            TodoItem(
                summary=item.summary,
                uid=uuid.uuid4().hex,
                status=item.status or TodoItemStatus.NEEDS_ACTION,
            )
        )
        self.async_write_ha_state()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        for index, current in enumerate(self._attr_todo_items):
            if current.uid == item.uid:
                self._attr_todo_items[index] = item
        self.async_write_ha_state()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        self._attr_todo_items = [i for i in self._attr_todo_items if i.uid not in uids]
        self.async_write_ha_state()
