"""The config flow and the options flow of Home Keeper Library.

The integration has 1 config entry. The flow first checks Home Keeper. If Home
Keeper is not installed, not set up or too old, the flow stops with the reason
and a link. The only setting is the currency of the prices and values of the
copies. Its default is the currency of Home Assistant.
The options flow is a menu with 2 steps. ``currency`` changes the currency. It
merges its input into the stored options, so a key that the form does not show
stays. ``openlibrary`` connects an Open Library account: it takes 2 Archive.org
S3 keys, logs in once to check them, and keeps them in the entry data. The keys
come in only here, so no service call, event or recorder row holds them.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CURRENCY,
    CONF_OPENLIBRARY_ACCESS,
    CONF_OPENLIBRARY_SECRET,
    CONF_OPENLIBRARY_USERNAME,
    DEFAULT_CURRENCY,
    DOMAIN,
    NAME,
)
from .home_keeper import async_check, placeholders
from .openlibrary_account import OpenLibraryAuthError, OpenLibraryWriter
from .openlibrary_client import OpenLibraryError

# The fields of the ``openlibrary`` options step.
ACCESS_KEY = "access_key"
SECRET_KEY = "secret_key"
OPTIONS_MENU = ("currency", "openlibrary")


def _currency_schema(default: str) -> vol.Schema:
    return vol.Schema({vol.Required(CONF_CURRENCY, default=default): str})


def clean_currency(value: Any) -> str | None:
    """An upper-case code of 3 letters, or None."""
    text = str(value or "").strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def merge_flow_input(entry: ConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    """The stored options with the form input on top."""
    return {**entry.options, **user_input}


class LibraryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the 1 config entry of the library."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the currency."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if (reason := await async_check(self.hass)) is not None:
            return self.async_abort(
                reason=reason, description_placeholders=placeholders(reason)
            )
        default = self.hass.config.currency or DEFAULT_CURRENCY
        errors: dict[str, str] = {}
        if user_input is not None:
            currency = clean_currency(user_input.get(CONF_CURRENCY))
            if currency is not None:
                return self.async_create_entry(
                    title=NAME, data={}, options={CONF_CURRENCY: currency}
                )
            errors[CONF_CURRENCY] = "invalid_currency"
        return self.async_show_form(
            step_id="user", data_schema=_currency_schema(default), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return LibraryOptionsFlow()


def _openlibrary_schema() -> vol.Schema:
    secret = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
    return vol.Schema({vol.Required(ACCESS_KEY): str, vol.Required(SECRET_KEY): secret})


class LibraryOptionsFlow(OptionsFlow):
    """Change the currency, or connect an Open Library account."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the menu."""
        return self.async_show_menu(step_id="init", menu_options=list(OPTIONS_MENU))

    async def async_step_openlibrary(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take the 2 S3 keys, check them with a login, and keep them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            access = str(user_input.get(ACCESS_KEY) or "").strip()
            secret = str(user_input.get(SECRET_KEY) or "").strip()
            coordinator = getattr(self.config_entry, "runtime_data", None)
            if coordinator is None:
                return self.async_abort(reason="not_loaded")
            try:
                _, username = await OpenLibraryWriter(coordinator.client).async_login(
                    access, secret
                )
            except OpenLibraryAuthError:
                errors["base"] = "invalid_auth"
            except OpenLibraryError:
                errors["base"] = "cannot_connect"
            else:
                data = {
                    **self.config_entry.data,
                    CONF_OPENLIBRARY_ACCESS: access,
                    CONF_OPENLIBRARY_SECRET: secret,
                    CONF_OPENLIBRARY_USERNAME: username,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return self.async_create_entry(
                    data=merge_flow_input(self.config_entry, {})
                )
        return self.async_show_form(
            step_id="openlibrary", data_schema=_openlibrary_schema(), errors=errors
        )

    async def async_step_currency(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the currency form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            currency = clean_currency(user_input.get(CONF_CURRENCY))
            if currency is not None:
                return self.async_create_entry(
                    data=merge_flow_input(self.config_entry, {CONF_CURRENCY: currency})
                )
            errors[CONF_CURRENCY] = "invalid_currency"
        current = self.config_entry.options.get(CONF_CURRENCY) or (
            self.hass.config.currency or DEFAULT_CURRENCY
        )
        return self.async_show_form(
            step_id="currency", data_schema=_currency_schema(current), errors=errors
        )
