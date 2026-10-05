"""The websocket commands of the library tab and the card.

* ``home_keeper_library/get_state`` returns the whole library, projected for the
  caller (see ``projections.project_state``).
* ``home_keeper_library/subscribe`` sends ``{"type": "changed", "revision": n}``
  after each store change. The client then calls ``get_state`` again.
* ``home_keeper_library/list_todo_entities`` lists the to-do entities for the
  wishlist list picker. Admin only.
* Each other command is the twin of a service, with the same name, the same
  fields and the same gate. It calls the same handler in ``services.py``. The
  table of twins is ``api_surface.WEBSOCKET_COMMANDS``.

A websocket error shows its message as is, so the message is resolved here in
the language of Home Assistant (``backend_i18n``).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er

from . import people, projections
from .api_surface import SERVICES, WEBSOCKET_COMMANDS
from .backend_i18n import resolve_exception
from .const import DOMAIN
from .coordinator import find_coordinator
from .models import LibraryError
from .services import SERVICE_FIELDS, async_run

_SPECS = {spec.name: spec for spec in SERVICES}


def _error(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    hass: HomeAssistant,
    key: str,
    **placeholders: Any,
) -> None:
    connection.send_error(
        msg_id, key, resolve_exception(hass.config.language, key, **placeholders)
    )


async def _actor(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection
) -> people.Actor:
    actor = await people.actor_for_user(hass, connection.user.id)
    # The connection user is the authority on the admin flag.
    return people.Actor(
        user_id=actor.user_id,
        is_admin=connection.user.is_admin,
        person_id=actor.person_id,
        name=actor.name,
    )


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the commands. A second call replaces them with the same ones."""
    websocket_api.async_register_command(hass, ws_get_state)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_list_todo_entities)
    for command in WEBSOCKET_COMMANDS:
        if command.service is None:
            continue
        schema = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {
                vol.Required("type"): command.type,
                **SERVICE_FIELDS[command.service],
            }
        )
        websocket_api.async_register_command(
            hass, command.type, _service_command(command.service), schema
        )


def _service_command(service: str) -> websocket_api.const.WebSocketCommandHandler:
    spec = _SPECS[service]

    async def handle(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        # Home Assistant answers ``Unauthorized`` with the ``unauthorized`` code.
        if spec.admin_only and not connection.user.is_admin:
            raise Unauthorized
        data = {k: v for k, v in msg.items() if k not in ("id", "type")}
        try:
            result = await async_run(hass, spec, await _actor(hass, connection), data)
        except LibraryError as err:
            _error(connection, msg["id"], hass, err.key, **err.placeholders)
            return
        except ServiceValidationError as err:
            _error(connection, msg["id"], hass, err.translation_key or "not_loaded")
            return
        connection.send_result(msg["id"], result)

    return websocket_api.async_response(handle)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_state"})
@websocket_api.async_response
async def ws_get_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the library, projected for the caller."""
    coordinator = find_coordinator(hass)
    if coordinator is None:
        _error(connection, msg["id"], hass, "not_loaded")
        return
    actor = await _actor(hass, connection)
    connection.send_result(
        msg["id"],
        projections.project_state(
            coordinator.store.state,
            persons=people.persons(hass),
            viewer=actor.person_id,
            is_admin=actor.is_admin,
            viewer_name=actor.name,
            currency=coordinator.currency,
            tab=coordinator.tab_registered,
            revision=coordinator.store.revision,
        ),
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send ``{"type": "changed", "revision": n}`` after each store change."""
    coordinator = find_coordinator(hass)
    if coordinator is None:
        _error(connection, msg["id"], hass, "not_loaded")
        return
    store = coordinator.store

    @callback
    def _changed() -> None:
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"type": "changed", "revision": store.revision}
            )
        )

    connection.subscriptions[msg["id"]] = store.async_add_listener(_changed)
    connection.send_result(msg["id"], {"revision": store.revision})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list_todo_entities"})
@websocket_api.require_admin
@callback
def ws_list_todo_entities(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """The to-do entities that a wishlist can use. The library lists are left out."""
    registry = er.async_get(hass)
    out = []
    for state in hass.states.async_all("todo"):
        entry = registry.async_get(state.entity_id)
        if entry is not None and entry.platform == DOMAIN:
            continue
        out.append(
            {
                "entity_id": state.entity_id,
                "name": state.attributes.get("friendly_name") or state.entity_id,
            }
        )
    out.sort(key=lambda row: (str(row["name"]).casefold(), row["entity_id"]))
    connection.send_result(msg["id"], {"entities": out})
