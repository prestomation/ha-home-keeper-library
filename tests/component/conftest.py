"""Fixtures for the component tier: a real Home Assistant in the test process.

``pytest-homeassistant-custom-component`` gives a real ``hass`` with real
registries and config entries, and mocks the I/O. This tier pulls in
``pytest-socket``, so it never runs in the same pytest call as the Docker tier.

Home Keeper is a fake here (``fake_home_keeper/custom_components/home_keeper``).
``custom_components`` is a namespace package, so the fake directory on
``sys.path`` adds ``home_keeper`` next to the library. The fake module explains
why the tier uses a fake.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_FAKE = Path(__file__).parent / "fake_home_keeper"
if str(_FAKE) not in sys.path:
    sys.path.insert(0, str(_FAKE))

# Import the namespace package now. Home Assistant imports ``custom_components``
# when it starts, with the test config directory of the harness first on
# ``sys.path``, and that directory has a regular ``custom_components`` package
# that would hide the library and the fake.
import custom_components  # noqa: E402, F401

pytest_plugins = "pytest_homeassistant_custom_component"

ALICE = "p_alice"
BOB = "p_bob"
CAROL = "p_carol"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> Any:
    """Load the custom integrations in each test."""
    return enable_custom_integrations


@pytest.fixture
async def persons(hass, hass_admin_user, hass_read_only_user) -> dict[str, Any]:
    """3 people: Alice is the admin user, Bob a non-admin user, Carol has no user."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {"id": ALICE, "name": "Alice", "user_id": hass_admin_user.id},
                {"id": BOB, "name": "Bob", "user_id": hass_read_only_user.id},
                {"id": CAROL, "name": "Carol"},
            ]
        },
    )
    await hass.async_block_till_done()
    return {"admin": hass_admin_user, "user": hass_read_only_user}


@pytest.fixture
async def hk_entry(hass):
    """A loaded config entry of the fake Home Keeper."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="home_keeper", title="Home Keeper")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def setup_entry(hass, persons, hk_entry):
    """Set up the library from a new config entry and return the entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.home_keeper_library.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Keeper Library",
        data={},
        options={"currency": "EUR"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.client._min_interval = 0
    return entry


@pytest.fixture
def call(hass, persons):
    """Call a library service as `admin`, `user` or no user. Return the reply."""
    from homeassistant.core import Context

    from custom_components.home_keeper_library.const import DOMAIN

    async def _call(
        service: str, data: dict[str, Any] | None = None, *, as_: str | None = "admin"
    ) -> Any:
        context = Context(user_id=persons[as_].id) if as_ else Context()
        return await hass.services.async_call(
            DOMAIN,
            service,
            data or {},
            blocking=True,
            return_response=True,
            context=context,
        )

    return _call


def coordinator(entry: Any) -> Any:
    """The coordinator of the entry."""
    return entry.runtime_data


@pytest.fixture
async def todo_list(hass) -> str:
    """An in-memory to-do list from the fake ``fake_todo`` integration."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="fake_todo", title="Books")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return "todo.books"


@pytest.fixture
def ws(hass, hass_ws_client, hass_access_token, hass_read_only_access_token):
    """A websocket client as ``admin`` or as ``user``."""

    async def _client(as_: str = "admin") -> Any:
        token = hass_access_token if as_ == "admin" else hass_read_only_access_token
        return await hass_ws_client(hass, access_token=token)

    return _client


async def settle(hass) -> None:
    """Wait for the background syncs of the library."""
    await hass.async_block_till_done(wait_background_tasks=True)
