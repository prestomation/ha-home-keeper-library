"""An in-memory to-do list integration for the wishlist sync tests.

Each config entry adds 1 list, ``todo.<title>``. The list is a plain
``TodoListEntity`` that keeps its items in memory, like a list from another
integration that the library writes to.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 1 list."""
    await hass.config_entries.async_forward_entry_setups(entry, ["todo"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the list."""
    return await hass.config_entries.async_unload_platforms(entry, ["todo"])
