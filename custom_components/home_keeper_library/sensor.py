"""The library sensors.

Global sensors:

* ``books``: the number of books with 1 copy or more.
* ``loans_out``: the open loans that lend a copy out.
* ``loans_overdue``: the open loans past their due date.

Per person (the unique id holds the person id):

* ``books_read_this_year``: the books finished this year, with the attributes
  ``goal``, ``pages`` and ``year``.
* ``reading_now``: the number of books with status ``reading``, with the
  attribute ``books`` (at most 10 titles).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import LibraryConfigEntry
from .const import READING_NOW_MAX_TITLES
from .coordinator import LibraryCoordinator
from .entity import LibraryEntity, PersonEntity, async_track_people
from .models import person_settings
from .projections import (
    books_read_in_year,
    loans_out_count,
    loans_overdue_count,
    owned_book_count,
    reading_now,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LibraryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the global sensors and the sensors of each person."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            BooksSensor(coordinator),
            LoansOutSensor(coordinator),
            LoansOverdueSensor(coordinator),
        ]
    )

    def _build(person: dict[str, Any]) -> list[SensorEntity]:
        return [
            BooksReadThisYearSensor(coordinator, person),
            ReadingNowSensor(coordinator, person),
        ]

    entry.async_on_unload(
        async_track_people(hass, coordinator, _build, async_add_entities)
    )


class BooksSensor(LibraryEntity, SensorEntity):
    """The number of books with 1 copy or more."""

    _attr_translation_key = "books"
    _attr_icon = "mdi:bookshelf"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LibraryCoordinator) -> None:
        super().__init__(coordinator, "books")

    @property
    def native_value(self) -> int:
        return owned_book_count(self.state_doc)


class LoansOutSensor(LibraryEntity, SensorEntity):
    """The number of open loans that lend a copy out."""

    _attr_translation_key = "loans_out"
    _attr_icon = "mdi:book-arrow-right"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LibraryCoordinator) -> None:
        super().__init__(coordinator, "loans_out")

    @property
    def native_value(self) -> int:
        return loans_out_count(self.state_doc)


class LoansOverdueSensor(LibraryEntity, SensorEntity):
    """The number of open loans past their due date."""

    _attr_translation_key = "loans_overdue"
    _attr_icon = "mdi:book-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LibraryCoordinator) -> None:
        super().__init__(coordinator, "loans_overdue")

    @property
    def native_value(self) -> int:
        return loans_overdue_count(self.state_doc, dt_util.now().date().isoformat())


class BooksReadThisYearSensor(PersonEntity, SensorEntity):
    """The books that a person finished this year."""

    _attr_translation_key = "books_read_this_year"
    _attr_icon = "mdi:book-check"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: LibraryCoordinator, person: dict[str, Any]) -> None:
        super().__init__(coordinator, person, "books_read_this_year")

    @property
    def native_value(self) -> int:
        year = dt_util.now().year
        return books_read_in_year(self.state_doc, self.person_id, year)[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        year = dt_util.now().year
        _, pages = books_read_in_year(self.state_doc, self.person_id, year)
        goal = person_settings(self.state_doc["people"], self.person_id)["yearly_goal"]
        return {
            **super().extra_state_attributes,
            "goal": goal,
            "pages": pages,
            "year": year,
        }


class ReadingNowSensor(PersonEntity, SensorEntity):
    """The number of books that a person reads now."""

    _attr_translation_key = "reading_now"
    _attr_icon = "mdi:book-open-page-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LibraryCoordinator, person: dict[str, Any]) -> None:
        super().__init__(coordinator, person, "reading_now")

    @property
    def native_value(self) -> int:
        return len(reading_now(self.state_doc, self.person_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        titles = reading_now(self.state_doc, self.person_id)
        return {
            **super().extra_state_attributes,
            "books": titles[:READING_NOW_MAX_TITLES],
        }
