"""The config flow of the fake Home Keeper. The tests add the entry directly."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow


class FakeHomeKeeperFlow(ConfigFlow, domain="home_keeper"):
    """A flow with no steps."""

    VERSION = 1
