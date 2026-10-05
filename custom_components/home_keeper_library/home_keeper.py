"""The link to Home Keeper: the check, the panel tab, the companion and the repair.

Home Keeper is an ``after_dependency``, so the library loads also when Home
Keeper is absent. :func:`async_check` returns the reason why Home Keeper cannot
take the library tab, or None:

* ``home_keeper_missing``: Home Keeper is not installed.
* ``home_keeper_not_set_up``: Home Keeper has no loaded config entry.
* ``home_keeper_too_old``: the installed Home Keeper is older than
  ``HOME_KEEPER_MIN_VERSION``, or it has no ``panel_tabs`` module.

The config flow aborts with that reason. :class:`HomeKeeperLink` runs the same
check at setup and each time a Home Keeper config entry changes state. While
the check fails, the library has a repair issue with the reason, and it has no
tab and no loan tasks. The store, the services, the card and the entities still
work. ``ConfigEntryNotReady`` is not used, because a retry cannot install or
update Home Keeper. When the check passes, the issue is deleted, the tab is
registered, the library registers as a companion and the loan sync runs.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .backend_i18n import all_strings, resolve_string
from .const import (
    DOCS_URL,
    DOMAIN,
    HOME_KEEPER_DOMAIN,
    HOME_KEEPER_EVENT_REGISTER_COMPANIONS,
    HOME_KEEPER_INSTALL_URL,
    HOME_KEEPER_MIN_VERSION,
    HOME_KEEPER_REASONS,
    ICON,
    NAME,
    STATIC_URL,
    TAB_ELEMENT,
    TAB_HOST_API,
    TAB_ID,
    TAB_JS_FILENAME,
    TAB_ORDER,
)

if TYPE_CHECKING:
    from .coordinator import LibraryCoordinator

_LOGGER = logging.getLogger(__name__)
DIST_DIR = Path(__file__).parent / "frontend" / "dist"
PANEL_TABS_MODULE = "custom_components.home_keeper.panel_tabs"


def content_hash(path: Path) -> str:
    """The first 12 hex digits of the SHA-256 of a file, or ``"missing"``.

    This call blocks: run it in an executor job.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "missing"


def placeholders(reason: str) -> dict[str, str]:
    """The message placeholders of a reason."""
    if reason == "home_keeper_missing":
        return {"url": HOME_KEEPER_INSTALL_URL}
    if reason == "home_keeper_too_old":
        return {"version": HOME_KEEPER_MIN_VERSION}
    return {}


async def async_panel_tabs(hass: HomeAssistant) -> Any | None:
    """The ``panel_tabs`` module of Home Keeper, or None if it has none."""
    try:
        return await hass.async_add_import_executor_job(
            importlib.import_module, PANEL_TABS_MODULE
        )
    except ImportError:
        return None


async def async_check(hass: HomeAssistant) -> str | None:
    """The reason why Home Keeper cannot take the tab, or None."""
    try:
        integration = await async_get_integration(hass, HOME_KEEPER_DOMAIN)
    except IntegrationNotFound:
        return "home_keeper_missing"
    if not hass.config_entries.async_loaded_entries(HOME_KEEPER_DOMAIN):
        return "home_keeper_not_set_up"
    version = integration.version
    if version is not None and version < AwesomeVersion(HOME_KEEPER_MIN_VERSION):
        return "home_keeper_too_old"
    if await async_panel_tabs(hass) is None:
        return "home_keeper_too_old"
    return None


@callback
def async_set_issue(hass: HomeAssistant, reason: str | None) -> None:
    """Show the repair issue of *reason*, and delete the issues of the others."""
    for other in HOME_KEEPER_REASONS:
        if other != reason:
            ir.async_delete_issue(hass, DOMAIN, other)
    if reason is None:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        reason,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=reason,
        translation_placeholders=placeholders(reason),
        learn_more_url=HOME_KEEPER_INSTALL_URL,
    )


async def async_register_companion(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the library as a Home Keeper companion. Best effort."""
    if not hass.services.has_service(HOME_KEEPER_DOMAIN, "register_companion"):
        return
    data = {
        "domain": DOMAIN,
        "name": NAME,
        "icon": ICON,
        "description": resolve_string(hass.config.language, "companion.description"),
        "config_entry_id": entry.entry_id,
        "docs_url": DOCS_URL,
    }
    try:
        await hass.services.async_call(
            HOME_KEEPER_DOMAIN, "register_companion", data, blocking=True
        )
    except (HomeAssistantError, ValueError) as err:
        _LOGGER.debug("Cannot register with Home Keeper: %s", err)


class HomeKeeperLink:
    """Follows Home Keeper, and adds or removes the tab and the loan tasks."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, coordinator: LibraryCoordinator
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._unregister_tab: Callable[[], None] | None = None
        self._unsubs: list[Callable[[], None]] = []
        self.reason: str | None = "home_keeper_not_set_up"
        # A state change of an entry sends several signals. The lock runs the
        # checks 1 at a time, so a stale check never wins.
        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        """Whether Home Keeper takes the tab and the loan tasks now."""
        return self.reason is None

    async def async_start(self) -> None:
        """Run the check now, and again when Home Keeper changes."""

        @callback
        def _entry_changed(change: ConfigEntryChange, changed: ConfigEntry) -> None:
            if changed.domain == HOME_KEEPER_DOMAIN:
                self._schedule()

        @callback
        def _component_loaded(event: Event[Any]) -> None:
            if event.data.get("component") == HOME_KEEPER_DOMAIN:
                self._schedule()

        @callback
        def _register_again(_event: Event[Any]) -> None:
            if self.available:
                self._hass.async_create_task(
                    async_register_companion(self._hass, self._entry)
                )

        self._unsubs += [
            async_dispatcher_connect(
                self._hass, SIGNAL_CONFIG_ENTRY_CHANGED, _entry_changed
            ),
            self._hass.bus.async_listen(EVENT_COMPONENT_LOADED, _component_loaded),
            self._hass.bus.async_listen(
                HOME_KEEPER_EVENT_REGISTER_COMPANIONS, _register_again
            ),
        ]
        await self.async_refresh()

    @callback
    def async_stop(self) -> None:
        """Stop the listeners and remove the tab."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._remove_tab()

    @callback
    def _schedule(self) -> None:
        self._entry.async_create_background_task(
            self._hass, self.async_refresh(), "home_keeper_library home keeper check"
        )

    def _remove_tab(self) -> None:
        if self._unregister_tab is not None:
            self._unregister_tab()
            self._unregister_tab = None
        self._coordinator.tab_registered = False

    async def async_refresh(self) -> None:
        """Run the check and apply its result."""
        async with self._lock:
            await self._refresh()

    async def _refresh(self) -> None:
        reason = await async_check(self._hass)
        was_available = self.available
        self.reason = reason
        async_set_issue(self._hass, reason)
        self._coordinator.loan_sync.enabled = reason is None
        if reason is not None:
            self._remove_tab()
            return
        if self._unregister_tab is None:
            self._coordinator.tab_registered = await self._register_tab()
        if not was_available:
            await async_register_companion(self._hass, self._entry)
            self._coordinator.loan_sync.async_schedule()

    async def _register_tab(self) -> bool:
        module = await async_panel_tabs(self._hass)
        if module is None:
            return False

        def _prepare() -> tuple[str, dict[str, str]]:
            return content_hash(DIST_DIR / TAB_JS_FILENAME), all_strings("tab.title")

        digest, titles = await self._hass.async_add_executor_job(_prepare)
        tab = module.PanelTab(
            companion=DOMAIN,
            id=TAB_ID,
            titles=titles,
            icon=ICON,
            module_url=f"{STATIC_URL}/{TAB_JS_FILENAME}?v={digest}",
            element=TAB_ELEMENT,
            host_api=TAB_HOST_API,
            order=TAB_ORDER,
        )
        try:
            self._unregister_tab = module.async_register_panel_tab(self._hass, tab)
        except ValueError as err:
            _LOGGER.error("Home Keeper refused the library tab: %s", err)
            return False
        return True
