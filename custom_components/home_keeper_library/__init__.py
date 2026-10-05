"""Home Keeper Library: the books of a household, as a companion of Home Keeper.

Setup order:

1. Load the string tables and the store.
2. Make the coordinator, the Open Library client and the syncs.
3. Register the frontend, the websocket commands and the cover views.
4. Set up the entity platforms and register the services.
5. Add the tab to the Home Keeper panel and register as a companion.
6. Start the lookup queue, the to-do and loan syncs and the overdue check.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from . import backend_i18n, covers, frontend_assets, home_keeper, websocket_api
from .api_surface import SERVICE_NAMES
from .book_lookup import BookLookup
from .const import DOMAIN, OVERDUE_CHECK_INTERVAL_S, PLATFORMS
from .coordinator import LibraryCoordinator
from .loan_sync import LoanSync
from .openlibrary_client import OpenLibraryClient
from .services import async_register_services
from .store import LibraryStore, today
from .wishlist_sync import WishlistSync

_LOGGER = logging.getLogger(__name__)
_VIEWS_REGISTERED = f"{DOMAIN}_views_registered"

type LibraryConfigEntry = ConfigEntry[LibraryCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration. It has only a config entry."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LibraryConfigEntry) -> bool:
    """Set up Home Keeper Library from its config entry."""
    await hass.async_add_executor_job(backend_i18n.preload, hass.config.language)
    store = LibraryStore(hass)
    await store.load()
    store.on_cover_released = partial(covers.release_cover, hass)

    coordinator = LibraryCoordinator(hass, entry, store)
    coordinator.client = OpenLibraryClient(hass)
    coordinator.lookup = BookLookup(hass, coordinator)
    coordinator.wishlist_sync = WishlistSync(hass, coordinator)
    coordinator.loan_sync = LoanSync(hass, coordinator)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(store.async_add_listener(coordinator.async_store_changed))

    await frontend_assets.async_register(hass)
    websocket_api.async_register(hass)
    if not hass.data.get(_VIEWS_REGISTERED):
        hass.http.register_view(covers.CoverView())
        hass.http.register_view(covers.CoverUploadView())
        hass.data[_VIEWS_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)

    coordinator.tab_registered = await home_keeper.async_register_tab(hass, entry)
    await home_keeper.async_register_companion(hass, entry)
    entry.async_on_unload(home_keeper.async_listen_register(hass, entry))

    coordinator.lookup.async_start()
    entry.async_on_unload(coordinator.lookup.async_stop)
    coordinator.wishlist_sync.async_start()
    entry.async_on_unload(coordinator.wishlist_sync.async_stop)
    coordinator.loan_sync.async_start()
    entry.async_on_unload(coordinator.loan_sync.async_stop)

    await store.fire_overdue(today())

    @callback
    def _check_overdue(_now: Any) -> None:
        # The date sensors read the date, so they update with the hourly check.
        coordinator.async_update_listeners()
        hass.async_create_task(store.fire_overdue(today()))

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _check_overdue,
            timedelta(seconds=OVERDUE_CHECK_INTERVAL_S),
            cancel_on_shutdown=True,
        )
    )
    await covers.async_cleanup_pending(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LibraryConfigEntry) -> bool:
    """Unload the config entry and remove the services."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # The model is the list of services, so a new service is removed here
        # with no second edit.
        for service in SERVICE_NAMES:
            hass.services.async_remove(DOMAIN, service)
    return unloaded
