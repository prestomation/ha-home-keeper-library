"""The config flow of the fake to-do lists. The tests add the entry directly."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow


class FakeTodoFlow(ConfigFlow, domain="fake_todo"):
    """A flow with no steps."""

    VERSION = 1
