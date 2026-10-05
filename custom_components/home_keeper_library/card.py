"""Deliver the library card to every browser, by 1 path for each install.

1. A Lovelace **resource**. The frontend reads the resources over the websocket
   on each dashboard load, after the frontend has started. This is the path of
   each install that keeps its resources in storage, which is the default.
2. ``frontend.add_extra_js_url``, which puts an ``import("...")`` into the app
   shell. This is the path only when Lovelace has ``resource_mode: yaml``, where the
   library must not write resources, or when the resource write fails.

Both paths together are a race. Home Assistant 2026.9 replaces
``window.customElements`` with the ``@webcomponents/scoped-custom-element-registry``
polyfill, which does not see an element that the native registry got before the
polyfill. The shell import can run first, so the card goes into the native
registry, the resource import of the same URL does not run the module again, and
the dashboard shows "Custom element doesn't exist" on some loads. Home Keeper
found this first (Home Keeper #368, ``card.py``), and this module follows it.

The reconciliation expects 1 config entry, which ``single_config_entry`` makes
sure of.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from homeassistant.components import frontend
from homeassistant.components.lovelace.const import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_when_setup

if TYPE_CHECKING:  # pragma: no cover - typing only
    # For the annotation only. The resource collections are internal to Lovelace,
    # so a runtime import would turn a refactor of Home Assistant into an
    # ImportError of the whole integration.
    from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .card_resource import matching_ids, plan_card_resource, resource_payload
from .const import CARD_JS_FILENAME, DOMAIN, STATIC_URL

_LOGGER = logging.getLogger(__name__)

# The registered URL, so the removal can undo the registration. It is also the
# guard that keeps the registration to 1 time for each run of Home Assistant.
_CARD_REGISTERED = f"{DOMAIN}_card_registered"

# True only while the app shell imports the card (path 2).
_CARD_EXTRA_JS = f"{DOMAIN}_card_extra_js"

# The path of the bundle with no query. Stored resources match on this path, so a
# new `?v=` token updates the row and does not add a second row.
CARD_URL_PATH = f"{STATIC_URL}/{CARD_JS_FILENAME}"


def _storage_resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """The resource collection that the library can write, or None."""
    if (data := hass.data.get(LOVELACE_DATA)) is None:
        return None
    if data.resource_mode != MODE_STORAGE:
        return None
    return cast("ResourceStorageCollection", data.resources)


async def _async_sync_resource(resources: ResourceStorageCollection, url: str) -> None:
    """Leave exactly 1 resource row for *url*."""
    # The collection loads lazily: the items are empty until the store is read.
    await resources.async_get_info()
    plan = plan_card_resource(resources.async_items(), url)
    if plan.create:
        await resources.async_create_item(resource_payload(url))
        _LOGGER.info("Registered the library card as a Lovelace resource (%s)", url)
    elif plan.update_id is not None:
        await resources.async_update_item(plan.update_id, resource_payload(url))
        _LOGGER.info("Updated the library card Lovelace resource to %s", url)
    for duplicate in plan.delete_ids:
        await resources.async_delete_item(duplicate)
        _LOGGER.info("Removed a second library card Lovelace resource")


def _resource_urls(resources: ResourceStorageCollection) -> set[str]:
    return {str(item.get("url")) for item in resources.async_items()}


async def _async_delete_resources(resources: ResourceStorageCollection) -> None:
    await resources.async_get_info()
    for item_id in matching_ids(resources.async_items(), CARD_URL_PATH):
        await resources.async_delete_item(item_id)
        _LOGGER.info("Removed the library card Lovelace resource")


def _add_extra_js(hass: HomeAssistant, url: str) -> None:
    """Put the card import into the app shell (path 2), 1 time."""
    if hass.data.get(_CARD_EXTRA_JS):
        return
    frontend.add_extra_js_url(hass, url)
    hass.data[_CARD_EXTRA_JS] = True


async def async_register_card(hass: HomeAssistant, url: str) -> None:
    """Deliver the card bundle at *url* by the 1 path of this install."""
    if hass.data.get(_CARD_REGISTERED):
        return
    hass.data[_CARD_REGISTERED] = url

    async def _sync(hass: HomeAssistant, _component: str) -> None:
        if hass.data.get(_CARD_REGISTERED) != url:
            return
        if (resources := _storage_resources(hass)) is None:
            _LOGGER.debug("The Lovelace resources are in YAML; the card is a module")
            _add_extra_js(hass, url)
            return
        try:
            await _async_sync_resource(resources, url)
        except Exception:
            # A row that is written still delivers the card. The shell import too
            # would bring the race back.
            if url in _resource_urls(resources):
                _LOGGER.exception("Could not finish the library card resource update")
                return
            _LOGGER.exception(
                "Could not register the library card as a Lovelace resource. "
                "The card is a frontend module instead"
            )
            _add_extra_js(hass, url)
            return
        # A removal during the awaits found no row, so delete the row that this
        # sync wrote.
        if hass.data.get(_CARD_REGISTERED) != url:
            await _async_delete_resources(resources)

    # Not on the setup path: a storage write must not delay or fail the setup.
    async_when_setup(hass, LOVELACE_DOMAIN, _sync)


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Undo the card delivery. Only for the removal of the integration.

    An unload or a reload keeps the resource: it is shared state, and most unloads
    are half of a reload.
    """
    url = hass.data.pop(_CARD_REGISTERED, None)
    added_extra_js = hass.data.pop(_CARD_EXTRA_JS, False)
    try:
        if isinstance(url, str) and added_extra_js:
            frontend.remove_extra_js_url(hass, url)
        if (resources := _storage_resources(hass)) is None:
            return
        await _async_delete_resources(resources)
    except Exception:
        _LOGGER.exception("Could not remove the library card Lovelace resource")
