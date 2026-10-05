"""Docker integration: the integration loads and its surfaces are live in real HA."""

from __future__ import annotations


def test_config_entry_loaded(api):
    """The home_keeper_library config entry is set up (states API responds)."""
    resp = api.get("/api/states")
    assert resp.status_code == 200


def test_services_registered(api):
    """The automation-facing services exist on the running instance."""
    resp = api.get("/api/services")
    assert resp.status_code == 200
    domains = {block["domain"]: block for block in resp.json()}
    assert "home_keeper_library" in domains
    services = domains["home_keeper_library"]["services"]
    for name in ("add_item", "update_item", "delete_item"):
        assert name in services


def test_panel_bundle_served(api):
    """The sidebar panel JS bundle is served from the static path."""
    resp = api.get("/home_keeper_library_static/home-keeper-library-panel.js")
    assert resp.status_code == 200
    assert (
        "HomeKeeperLibraryPanelBundle" in resp.text
        or "home-keeper-library-panel" in resp.text
    )


def test_card_bundle_served(api):
    """The dashboard card JS bundle is served from the static path."""
    resp = api.get("/home_keeper_library_static/home-keeper-library-card.js")
    assert resp.status_code == 200
