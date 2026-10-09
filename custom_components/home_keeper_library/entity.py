"""The shared parts of the library entities: the device and the person list."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import people
from .const import DOMAIN, NAME
from .coordinator import LibraryCoordinator
from .models import person_settings


def device_info(entry_id: str) -> DeviceInfo:
    """The 1 service device of the library entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=NAME,
        entry_type=DeviceEntryType.SERVICE,
    )


class LibraryEntity(CoordinatorEntity[LibraryCoordinator]):
    """An entity on the library device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LibraryCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_device_info = device_info(coordinator.config_entry.entry_id)

    @property
    def state_doc(self) -> dict[str, Any]:
        """The library document."""
        return self.coordinator.store.state


class PersonEntity(LibraryEntity):
    """An entity for 1 person. Its unique id holds the person id."""

    def __init__(
        self, coordinator: LibraryCoordinator, person: dict[str, Any], key: str
    ) -> None:
        super().__init__(coordinator, f"{person['person_id']}_{key}")
        self.person_id: str = person["person_id"]
        self._attr_translation_placeholders = {"person": str(person["name"])}

    @property
    def available(self) -> bool:
        """Whether the person exists and shares their reading.

        Home Assistant shows each entity to each user. So while a person does
        not share their reading (``share_reading: false``), the per-person
        entities are unavailable and show no reading.
        """
        if people.person(self.hass, self.person_id) is None:
            return False
        settings = person_settings(self.state_doc["people"], self.person_id)
        return bool(settings["share_reading"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The person of the entity."""
        return {"person_id": self.person_id}


@callback
def async_track_people(
    hass: HomeAssistant,
    coordinator: LibraryCoordinator,
    build: Callable[[dict[str, Any]], Iterable[Any]],
    add: Callable[[list[Any]], None],
) -> Callable[[], None]:
    """Add the entities of each person now and of each new person later."""
    known: set[str] = set()

    @callback
    def _reconcile() -> None:
        new: list[Any] = []
        for person in people.persons(hass):
            if person["person_id"] in known:
                continue
            known.add(person["person_id"])
            new.extend(build(person))
        if new:
            add(new)

    _reconcile()
    return coordinator.async_add_listener(_reconcile)
