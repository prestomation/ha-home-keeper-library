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

from .const import (
    CONF_CURRENCY,
    CONF_OPENLIBRARY_USERNAME,
    DEFAULT_CURRENCY,
    DOMAIN,
)
from .openlibrary_account import account_keys
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
        self._account_seen = self.openlibrary_account

    @property
    def currency(self) -> str:
        """The currency option of the entry."""
        entry = self.config_entry
        value = entry.options.get(CONF_CURRENCY) or entry.data.get(CONF_CURRENCY)
        return str(value or self.hass.config.currency or DEFAULT_CURRENCY)

    @property
    def openlibrary_account(self) -> dict[str, Any]:
        """The Open Library account, with no keys: ``{connected, username}``."""
        data = self.config_entry.data
        connected = account_keys(data) is not None
        username = data.get(CONF_OPENLIBRARY_USERNAME) if connected else None
        return {
            "connected": connected,
            "username": username if isinstance(username, str) else None,
        }

    @callback
    def async_check_settings(self) -> None:
        """Fire ``settings_updated`` once when the currency or the account changed.

        The ``set_settings`` service, the ``disconnect_openlibrary`` service and
        the update listener of the entry (the options flow) call this. The second
        call finds no change.
        """
        changed: list[str] = []
        currency = self.currency
        if currency != self._currency_seen:
            self._currency_seen = currency
            changed.append(CONF_CURRENCY)
        account = self.openlibrary_account
        if account != self._account_seen:
            self._account_seen = account
            changed.append("openlibrary_account")
        if changed:
            self.store.async_settings_updated(changed, currency)

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
