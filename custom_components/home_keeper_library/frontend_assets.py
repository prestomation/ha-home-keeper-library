"""The built frontend: the static path, and the card as a frontend module.

Home Assistant serves ``frontend/dist/`` at ``/home_keeper_library_static``. It
serves a static path before authentication, so only the built bundles are in
that directory. CI builds them, and git ignores them.

The card bundle is added to the extra module URLs of the frontend, so that the
card is in the card picker of each dashboard with no resource to add by hand. The
``?v=`` query is the content hash of the bundle, so a new build is never read
from a browser cache. The library has no sidebar panel of its own: its admin UI
is a tab in the Home Keeper panel (see ``home_keeper.py``).
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import CARD_JS_FILENAME, DOMAIN, STATIC_URL
from .home_keeper import content_hash

_LOGGER = logging.getLogger(__name__)
DIST_DIR = Path(__file__).parent / "frontend" / "dist"
_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register(hass: HomeAssistant) -> None:
    """Register the static path and the card module, once for each run."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(DIST_DIR), False)]
    )
    digest = await hass.async_add_executor_job(
        content_hash, DIST_DIR / CARD_JS_FILENAME
    )
    url = f"{STATIC_URL}/{CARD_JS_FILENAME}?v={digest}"
    frontend.add_extra_js_url(hass, url)
    _LOGGER.debug("Registered the library card module at %s", url)
