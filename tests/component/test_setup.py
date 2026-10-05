"""Component tests: setup, unload, the Home Keeper tab, the companion, diagnostics."""

from __future__ import annotations

import sys

from homeassistant.helpers import issue_registry as ir

from custom_components.home_keeper_library.api_surface import SERVICE_NAMES
from custom_components.home_keeper_library.const import DOMAIN, LANGUAGES
from custom_components.home_keeper_library.diagnostics import (
    async_get_config_entry_diagnostics,
)

ALICE = "p_alice"

TABS = "home_keeper_panel_tabs"


async def test_setup_registers_every_service(hass, setup_entry) -> None:
    for service in SERVICE_NAMES:
        assert hass.services.has_service(DOMAIN, service), service


async def test_tab_is_registered_with_home_keeper(hass, setup_entry) -> None:
    tabs = hass.data[TABS].tabs()
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab.companion == DOMAIN and tab.id == "library"
    assert tab.element == "home-keeper-library-tab"
    assert tab.icon == "mdi:bookshelf" and tab.order == 50 and tab.host_api == 1
    assert tab.module_url.startswith("/home_keeper_library_static/library-tab.js?v=")
    assert set(tab.titles) == set(LANGUAGES)
    assert tab.titles["en"] == "Library" and tab.titles["de"] == "Bibliothek"
    assert setup_entry.runtime_data.tab_registered is True
    assert _issues(hass) == set()


async def test_unload_removes_services_and_the_tab(hass, setup_entry) -> None:
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    for service in SERVICE_NAMES:
        assert not hass.services.has_service(DOMAIN, service)
    assert hass.data[TABS].tabs() == []
    assert await hass.config_entries.async_setup(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.data[TABS].tabs()) == 1


async def test_companion_registration(hass, setup_entry) -> None:
    companion = hass.data["home_keeper_fake"]["companions"][DOMAIN]
    assert companion == {
        "domain": DOMAIN,
        "name": "Home Keeper Library",
        "icon": "mdi:bookshelf",
        "description": "Books, shelves, loans and reading status.",
        "config_entry_id": setup_entry.entry_id,
        "docs_url": "https://github.com/prestomation/ha-home-keeper-library",
    }
    calls = hass.data["home_keeper_fake"]["calls"]
    before = sum(1 for name, _ in calls if name == "register_companion")
    hass.bus.async_fire("home_keeper_register_companions")
    await hass.async_block_till_done()
    after = sum(1 for name, _ in calls if name == "register_companion")
    assert after == before + 1


def _issues(hass) -> set[str]:
    registry = ir.async_get(hass)
    return {
        issue_id
        for (domain, issue_id) in registry.issues
        if domain == DOMAIN and registry.issues[(domain, issue_id)].active
    }


async def _library_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, options={"currency": "EUR"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_repair_issue_cycle(hass, persons, monkeypatch) -> None:
    """No Home Keeper entry, then a loaded one, then an old one, then none."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = await _library_entry(hass)
    link = entry.runtime_data.home_keeper
    assert _issues(hass) == {"home_keeper_not_set_up"}
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "home_keeper_not_set_up")
    assert issue.translation_key == "home_keeper_not_set_up"
    assert issue.learn_more_url.startswith("https://github.com/prestomation/")
    assert entry.runtime_data.tab_registered is False
    assert entry.runtime_data.loan_sync.enabled is False
    assert hass.services.has_service(DOMAIN, "add_room")

    hk = MockConfigEntry(domain="home_keeper", title="Home Keeper")
    hk.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hk.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _issues(hass) == set()
    assert entry.runtime_data.tab_registered is True
    assert link.available and entry.runtime_data.loan_sync.enabled
    assert len(hass.data[TABS].tabs()) == 1

    # A Home Keeper with no panel_tabs module is too old.
    monkeypatch.setitem(sys.modules, "custom_components.home_keeper.panel_tabs", None)
    await link.async_refresh()
    assert _issues(hass) == {"home_keeper_too_old"}
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "home_keeper_too_old")
    assert issue.translation_placeholders == {"version": "0.30.0b2"}
    assert hass.data[TABS].tabs() == []
    monkeypatch.delitem(sys.modules, "custom_components.home_keeper.panel_tabs")

    await link.async_refresh()
    assert _issues(hass) == set() and len(hass.data[TABS].tabs()) == 1

    assert await hass.config_entries.async_unload(hk.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _issues(hass) == {"home_keeper_not_set_up"}
    assert hass.data[TABS].tabs() == []
    assert entry.runtime_data.loan_sync.enabled is False


async def test_old_home_keeper_version(hass, persons, hk_entry, monkeypatch) -> None:
    from homeassistant import loader

    integration = await loader.async_get_integration(hass, "home_keeper")
    monkeypatch.setitem(integration.manifest, "version", "0.29.0")
    entry = await _library_entry(hass)
    assert _issues(hass) == {"home_keeper_too_old"}
    assert entry.runtime_data.tab_registered is False


async def test_missing_home_keeper(hass, persons, monkeypatch) -> None:
    from homeassistant.loader import IntegrationNotFound

    from custom_components.home_keeper_library import home_keeper

    async def _not_found(hass, domain):
        raise IntegrationNotFound(domain)

    monkeypatch.setattr(home_keeper, "async_get_integration", _not_found)
    entry = await _library_entry(hass)
    assert entry.state.value == "loaded"
    assert _issues(hass) == {"home_keeper_missing"}
    room = await hass.services.async_call(
        DOMAIN, "add_room", {"name": "Den"}, blocking=True, return_response=True
    )
    assert room["room"]["name"] == "Den"
    assert hass.states.get("sensor.home_keeper_library_books").state == "0"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "home_keeper_missing")
    assert issue.translation_placeholders == {
        "url": "https://github.com/prestomation/ha-home-keeper#installation"
    }


def _card_resources(hass) -> list[dict]:
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    return [
        item
        for item in hass.data[LOVELACE_DATA].resources.async_items()
        if "library-card.js" in str(item.get("url"))
    ]


def _extra_card_urls(hass) -> list[str]:
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    return [u for u in hass.data[DATA_EXTRA_MODULE_URL].urls if "library-card.js" in u]


async def test_card_is_a_lovelace_resource_and_not_a_module(hass, setup_entry) -> None:
    """Storage mode uses only the resource: both paths race (Home Keeper #368)."""
    await hass.async_block_till_done()
    rows = _card_resources(hass)
    assert len(rows) == 1
    assert rows[0]["type"] == "module"
    assert rows[0]["url"].startswith("/home_keeper_library_static/library-card.js?v=")
    assert _extra_card_urls(hass) == []
    # A reload keeps the 1 row and adds no module URL.
    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert _card_resources(hass) == rows
    assert _extra_card_urls(hass) == []
    # The removal of the integration removes the row.
    assert await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert _card_resources(hass) == []
    # A new entry in the same run delivers the card again.
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    again = MockConfigEntry(domain=DOMAIN, data={}, options={}, unique_id=DOMAIN)
    again.add_to_hass(hass)
    assert await hass.config_entries.async_setup(again.entry_id)
    await hass.async_block_till_done()
    assert len(_card_resources(hass)) == 1


async def test_card_is_a_module_when_resources_are_yaml(
    hass, persons, hk_entry, monkeypatch
) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.home_keeper_library import card

    monkeypatch.setattr(card, "_storage_resources", lambda hass: None)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    urls = _extra_card_urls(hass)
    assert len(urls) == 1
    assert urls[0].startswith("/home_keeper_library_static/library-card.js?v=")
    assert _card_resources(hass) == []
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _extra_card_urls(hass) == []


async def test_diagnostics_redact_names_and_notes(hass, setup_entry, call) -> None:
    room = (await call("add_room", {"name": "Den"}))["room"]
    case = (await call("add_bookcase", {"room_id": room["id"], "name": "L"}))[
        "bookcase"
    ]
    book = (
        await call(
            "add_book", {"title": "Dune", "shared_notes": "kittens", "lookup": False}
        )
    )["book"]
    copy = (await call("add_copy", {"book_id": book["id"], "acquired_from": "Shop"}))[
        "copy"
    ]
    await call("lend_book", {"copy_id": copy["id"], "party": "Zed", "note": "n"})
    await call(
        "set_reading",
        {"book_id": book["id"], "person_id": ALICE, "private_notes": "secret"},
    )
    data = await async_get_config_entry_diagnostics(hass, setup_entry)
    text = str(data)
    for secret in ("Zed", "Shop", "secret", "kittens"):
        assert secret not in text, secret
    assert data["counts"]["books"] == 1 and data["tab_registered"] is True
    assert case["name"] in text
