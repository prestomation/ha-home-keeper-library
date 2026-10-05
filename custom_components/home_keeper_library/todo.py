"""The ``To read`` to-do list of each person.

The items are the books with status ``want`` for the person. The summary is
``Title by Author`` and the uid is the book id.

* Completing an item sets the status to ``read``, with ``finished`` today.
* Adding an item by name gives a ``want`` row to the book with that title. If no
  book has that title, a new book with ``needs_details: true`` is added, and the
  lookup queue reads Open Library for it.
* Deleting an item removes the ``want`` row.

Home Assistant lets each user call the ``todo`` services on each list. So a
change must come from the user of the person, from an admin user or from Home
Assistant itself (no user). Other users get ``todo_not_allowed``. While the
person does not share their reading, the list is unavailable and has no items.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LibraryConfigEntry, people
from .backend_i18n import resolve_string
from .const import DOMAIN
from .coordinator import LibraryCoordinator
from .entity import PersonEntity, async_track_people
from .models import LibraryError, book_summary, fold
from .projections import want_to_read


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LibraryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the to-do list of each person."""
    coordinator = entry.runtime_data

    def _build(person: dict[str, Any]) -> list[TodoListEntity]:
        return [ToReadList(coordinator, person)]

    entry.async_on_unload(
        async_track_people(hass, coordinator, _build, async_add_entities)
    )


def _error(err: LibraryError) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=err.key,
        translation_placeholders=err.placeholders,
    )


class ToReadList(PersonEntity, TodoListEntity):
    """The books that a person wants to read."""

    _attr_translation_key = "to_read"
    _attr_icon = "mdi:book-heart"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: LibraryCoordinator, person: dict[str, Any]) -> None:
        super().__init__(coordinator, person, "to_read")

    async def _check_caller(self) -> None:
        """Refuse a change from a user who is not the person or an admin.

        The entity service call of Home Assistant sets the context of the call
        on the entity before it calls the item method.
        """
        context = self._context
        actor = await people.actor_for_user(
            self.hass, context.user_id if context else None
        )
        if actor.is_admin or actor.person_id == self.person_id:
            return
        found = people.person(self.hass, self.person_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="todo_not_allowed",
            translation_placeholders={
                "person": str(found["name"] if found else self.person_id)
            },
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        if not self.available:
            return []
        template = resolve_string(self.hass.config.language, "item.summary")
        return [
            TodoItem(
                summary=book_summary(book, template),
                uid=book["id"],
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for book in want_to_read(self.state_doc, self.person_id)
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Give the book with this title a ``want`` row, or add a new book."""
        await self._check_caller()
        summary = (item.summary or "").strip()
        if not summary:
            return
        store = self.coordinator.store
        template = resolve_string(self.hass.config.language, "item.summary")
        wanted = fold(summary)
        match = next(
            (
                book
                for book in store.state["books"].values()
                if wanted
                in (fold(book.get("title")), fold(book_summary(book, template)))
            ),
            None,
        )
        try:
            if match is None:
                match, _ = await store.add_book(
                    {"title": summary, "needs_details": True}
                )
                self.coordinator.lookup.async_enqueue(match["id"])
            await store.set_reading(match["id"], self.person_id, {"status": "want"})
        except LibraryError as err:
            raise _error(err) from err

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """A completed item sets the status to ``read``."""
        await self._check_caller()
        if item.uid is None or item.status != TodoItemStatus.COMPLETED:
            return
        try:
            await self.coordinator.store.set_reading(
                item.uid, self.person_id, {"status": "read"}
            )
        except LibraryError as err:
            raise _error(err) from err

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove the ``want`` row of each item."""
        await self._check_caller()
        store = self.coordinator.store
        for uid in uids:
            row = store.reading_row(self.person_id, uid)
            if row is None or row["status"] != "want":
                continue
            try:
                await store.set_reading(uid, self.person_id, {"status": "none"})
            except LibraryError as err:
                raise _error(err) from err
