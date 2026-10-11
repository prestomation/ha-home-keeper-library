"""Diagnostics of Home Keeper Library.

The download has the config entry, the counts and the library document. The
names of the loan parties and all notes are redacted. The Open Library keys are
in the entry data, which the download does not have. It only says if an account
is connected.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import LibraryConfigEntry
from .const import OPENLIBRARY_SECRET_KEYS

TO_REDACT = {
    "party",
    "note",
    "private_notes",
    "shared_notes",
    "acquired_from",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LibraryConfigEntry
) -> dict[str, Any]:
    """The diagnostics of the config entry."""
    coordinator = entry.runtime_data
    state = coordinator.store.state
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": async_redact_data(dict(entry.options), OPENLIBRARY_SECRET_KEYS),
        },
        "openlibrary_connected": coordinator.openlibrary_account["connected"],
        "tab_registered": coordinator.tab_registered,
        "revision": coordinator.store.revision,
        "counts": {
            name: len(value)
            for name, value in state.items()
            if isinstance(value, dict | list)
        },
        "library": async_redact_data(state, TO_REDACT),
    }
