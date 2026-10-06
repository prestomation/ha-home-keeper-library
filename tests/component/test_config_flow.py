"""Component tests: the config flow and the options flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.home_keeper_library.const import DOMAIN


async def test_user_flow_creates_the_entry(hass, persons, hk_entry) -> None:
    hass.config.currency = "USD"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    default = next(k for k in schema if str(k) == "currency").default()
    assert default == "USD"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"currency": "eur"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {"currency": "EUR"}
    assert result["title"] == "Home Keeper Library"


async def test_user_flow_rejects_a_bad_currency(hass, persons, hk_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"currency": "euro"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"currency": "invalid_currency"}


async def test_single_instance(hass, setup_entry) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] in ("already_configured", "single_instance_allowed")


async def test_options_flow_merges(hass, setup_entry) -> None:
    hass.config_entries.async_update_entry(
        setup_entry, options={"currency": "EUR", "other": 1}
    )
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"currency": "x"}
    )
    assert result["errors"] == {"currency": "invalid_currency"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"currency": "gbp"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.options == {"currency": "GBP", "other": 1}
    assert setup_entry.runtime_data.currency == "GBP"


async def _abort_reason(hass) -> tuple[str, dict]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    return result["reason"], result.get("description_placeholders") or {}


async def test_abort_when_home_keeper_is_not_set_up(hass, persons) -> None:
    assert await _abort_reason(hass) == ("home_keeper_not_set_up", {})


async def test_abort_when_home_keeper_is_missing(hass, persons, monkeypatch) -> None:
    from homeassistant.loader import IntegrationNotFound

    from custom_components.home_keeper_library import home_keeper

    async def _not_found(hass, domain):
        raise IntegrationNotFound(domain)

    monkeypatch.setattr(home_keeper, "async_get_integration", _not_found)
    assert await _abort_reason(hass) == (
        "home_keeper_missing",
        {"url": "https://github.com/prestomation/ha-home-keeper#installation"},
    )


async def test_abort_when_home_keeper_is_too_old(
    hass, persons, hk_entry, monkeypatch
) -> None:
    import sys

    from homeassistant import loader

    integration = await loader.async_get_integration(hass, "home_keeper")
    monkeypatch.setitem(integration.manifest, "version", "0.30.0")
    monkeypatch.setitem(sys.modules, "custom_components.home_keeper.panel_tabs", None)
    assert await _abort_reason(hass) == ("home_keeper_too_old", {"version": "0.30.0b2"})
