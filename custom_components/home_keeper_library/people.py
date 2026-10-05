"""The people of Home Assistant, and the caller of a service or a command.

A person in the library is a Home Assistant ``person``, by its collection id
(the ``id`` attribute of the ``person.*`` entity). That id stays the same when
the person gets a new name. The caller of a service or a websocket command is a
Home Assistant user. The person whose ``user_id`` is that user is the person of
the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

PERSON_DOMAIN = "person"


@dataclass(frozen=True)
class Actor:
    """The caller of an operation.

    ``user_id`` is None for an automation or for Home Assistant itself. Such a
    call is trusted, as Home Assistant core trusts it, so ``is_admin`` is True.
    """

    user_id: str | None
    is_admin: bool
    person_id: str | None
    name: str | None = None


def persons(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Each Home Assistant person: ``{person_id, name, entity_id, user_id}``."""
    out = []
    for state in hass.states.async_all(PERSON_DOMAIN):
        person_id = state.attributes.get("id")
        if not isinstance(person_id, str) or not person_id:
            continue
        out.append(
            {
                "person_id": person_id,
                "name": state.attributes.get("friendly_name") or state.entity_id,
                "entity_id": state.entity_id,
                "user_id": state.attributes.get("user_id"),
            }
        )
    out.sort(key=lambda p: (str(p["name"]).casefold(), p["person_id"]))
    return out


def person(hass: HomeAssistant, person_id: str | None) -> dict[str, Any] | None:
    """The person with this collection id."""
    if not person_id:
        return None
    return next((p for p in persons(hass) if p["person_id"] == person_id), None)


def person_for_user(hass: HomeAssistant, user_id: str | None) -> dict[str, Any] | None:
    """The person of a Home Assistant user."""
    if not user_id:
        return None
    return next((p for p in persons(hass) if p["user_id"] == user_id), None)


async def actor_for_user(hass: HomeAssistant, user_id: str | None) -> Actor:
    """The actor for a user id. None is a trusted internal caller."""
    if user_id is None:
        return Actor(user_id=None, is_admin=True, person_id=None)
    user = await hass.auth.async_get_user(user_id)
    found = person_for_user(hass, user_id)
    return Actor(
        user_id=user_id,
        is_admin=bool(user is not None and user.is_admin),
        person_id=found["person_id"] if found else None,
        name=found["name"] if found else None,
    )


async def actor_for_call(hass: HomeAssistant, call: ServiceCall) -> Actor:
    """The actor of a service call."""
    return await actor_for_user(hass, call.context.user_id)
