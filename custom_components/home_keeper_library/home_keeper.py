"""The link to Home Keeper: the companion entry and the panel tab.

* **Companion.** The library calls ``home_keeper.register_companion`` at setup
  and again on ``home_keeper_register_companions``, which Home Keeper fires at
  its own setup and reload. Home Keeper then lists the library under Settings,
  Companions.
* **Panel tab.** The admin UI of the library is a tab in the Home Keeper panel
  at ``/home-keeper/library``. The tab is added through the Python API
  ``custom_components.home_keeper.panel_tabs``. An older Home Keeper has no such
  module. The library then creates the ``home_keeper_too_old`` repair issue and
  finishes its setup with no tab, so the card, the entities and the services
  still work. ``ConfigEntryNotReady`` is not used, because a retry cannot add a
  module that is not installed.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .backend_i18n import all_strings, resolve_string
from .const import (
    DOCS_URL,
    DOMAIN,
    HOME_KEEPER_DOMAIN,
    HOME_KEEPER_EVENT_REGISTER_COMPANIONS,
    ICON,
    ISSUE_HOME_KEEPER_TOO_OLD,
    NAME,
    STATIC_URL,
    TAB_ELEMENT,
    TAB_HOST_API,
    TAB_ID,
    TAB_JS_FILENAME,
    TAB_ORDER,
)

_LOGGER = logging.getLogger(__name__)
DIST_DIR = Path(__file__).parent / "frontend" / "dist"


def content_hash(path: Path) -> str:
    """The first 12 hex digits of the SHA-256 of a file, or ``"missing"``.

    This call blocks: run it in an executor job.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "missing"


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


@callback
def async_listen_register(
    hass: HomeAssistant, entry: ConfigEntry
) -> Callable[[], None]:
    """Register again each time Home Keeper asks the companions to register."""

    @callback
    def _register(_event: Event[Any]) -> None:
        hass.async_create_task(async_register_companion(hass, entry))

    return hass.bus.async_listen(HOME_KEEPER_EVENT_REGISTER_COMPANIONS, _register)


async def async_register_tab(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Add the library tab to the Home Keeper panel. Return whether it is added.

    On an ImportError the repair issue is created. A successful registration
    deletes the issue and is undone when the entry unloads.
    """
    try:
        from custom_components.home_keeper.panel_tabs import (  # type: ignore[import-not-found]
            PanelTab,
            async_register_panel_tab,
        )
    except ImportError:
        _LOGGER.warning(
            "Home Keeper has no panel tab API. Update Home Keeper to show the "
            "library tab"
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_HOME_KEEPER_TOO_OLD,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_HOME_KEEPER_TOO_OLD,
            learn_more_url=DOCS_URL,
        )
        return False
    ir.async_delete_issue(hass, DOMAIN, ISSUE_HOME_KEEPER_TOO_OLD)

    def _prepare() -> tuple[str, dict[str, str]]:
        return content_hash(DIST_DIR / TAB_JS_FILENAME), all_strings("tab.title")

    digest, titles = await hass.async_add_executor_job(_prepare)
    tab = PanelTab(
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
        unregister = async_register_panel_tab(hass, tab)
    except ValueError as err:
        _LOGGER.error("Home Keeper refused the library tab: %s", err)
        return False
    entry.async_on_unload(unregister)
    return True
