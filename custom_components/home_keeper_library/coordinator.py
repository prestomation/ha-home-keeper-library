"""The coordinator: the read path of the entities, and the runtime data of the entry.

The library has no external data to poll. The store tells the coordinator about
each change, and the coordinator sends the document to its entities. The
coordinator also holds the parts of a loaded entry that the services, the
websocket commands and the views use.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CURRENCY, DEFAULT_CURRENCY, DOMAIN
from .store import LibraryStore

if TYPE_CHECKING:
    from .book_lookup import BookLookup
    from .home_keeper import HomeKeeperLink
    from .loan_sync import LoanSync
    from .openlibrary_client import OpenLibraryClient
    from .wishlist_sync import WishlistSync

_LOGGER = logging.getLogger(__name__)


class LibraryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Sends the library document to the entities after each change."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: LibraryStore
    ) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.store = store
        # Set by async_setup_entry.
        self.client: OpenLibraryClient
        self.lookup: BookLookup
        self.wishlist_sync: WishlistSync
        self.loan_sync: LoanSync
        self.home_keeper: HomeKeeperLink
        self.tab_registered = False
        self._currency_seen = self.currency

    @property
    def currency(self) -> str:
        """The currency option of the entry."""
        entry = self.config_entry
        value = entry.options.get(CONF_CURRENCY) or entry.data.get(CONF_CURRENCY)
        return str(value or self.hass.config.currency or DEFAULT_CURRENCY)

    @callback
    def async_check_settings(self) -> None:
        """Fire ``settings_updated`` once when the currency option changed.

        The ``set_settings`` service and the update listener of the entry (the
        options flow) both call this. The second call finds no change.
        """
        currency = self.currency
        if currency == self._currency_seen:
            return
        self._currency_seen = currency
        self.store.async_settings_updated([CONF_CURRENCY], currency)

    async def _async_update_data(self) -> dict[str, Any]:
        """Return the document. A local read never fails."""
        return self.store.state

    @callback
    def async_store_changed(self) -> None:
        """Send the changed document to the entities."""
        self.async_set_updated_data(self.store.state)


def find_coordinator(hass: HomeAssistant) -> LibraryCoordinator | None:
    """The coordinator of the loaded entry, or None."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator = getattr(entry, "runtime_data", None)
        if isinstance(coordinator, LibraryCoordinator):
            return coordinator
    return None
