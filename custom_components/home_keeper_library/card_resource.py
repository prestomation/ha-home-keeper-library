"""The pure plan for the Lovelace resource of the library card.

This module follows ``card_resource.py`` of Home Keeper (Home Keeper #368). It
imports no Home Assistant code, so the unit tier tests it. It decides which rows
change. ``card.py`` makes the calls to the ``ResourceStorageCollection`` of
Lovelace.

The create and update payloads of Lovelace name the resource type ``res_type``.
``ResourceStorageCollection._process_create_data`` renames it, so a stored row has
``type``. Read ``type`` and write ``res_type``. The other way round, no stored row
matches, and each restart adds 1 more row.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# The Lovelace resource type of an ES module bundle. The type `js` loads the file
# as a classic script, which does not define the custom element.
RESOURCE_TYPE = "module"


def resource_path(url: str) -> str:
    """The path of a resource URL, with no ``?v=`` cache token.

    A match on the path lets a new build update the stored row, and add no second
    row. An absolute URL that a user typed for this bundle
    (``http://homeassistant.local:8123/...``) also matches. The plan then writes
    the relative URL into that row, which works from each host. A copy at another
    path, such as ``/local/library-card.js``, is a different resource and stays.
    """
    return urlsplit(url).path


@dataclass(frozen=True, slots=True)
class ResourcePlan:
    """The changes that leave exactly 1 resource row for the card."""

    create: bool = False
    update_id: str | None = None
    delete_ids: tuple[str, ...] = ()


def _serves_bundle(item: Mapping[str, Any], wanted: str) -> bool:
    """Whether the stored row *item* serves the bundle at the path *wanted*.

    A user can write the collection, so a row can have any shape. A row with no
    string URL does not match.
    """
    url = item.get("url")
    return isinstance(url, str) and resource_path(url) == wanted


def matching_ids(items: Iterable[Mapping[str, Any]], url: str) -> tuple[str, ...]:
    """The ids of each stored row that serves the card bundle, at any token.

    The removal uses this. It has only the path to clear, and no URL to keep.
    """
    wanted = resource_path(url)
    return tuple(str(item["id"]) for item in items if _serves_bundle(item, wanted))


def plan_card_resource(
    items: Iterable[Mapping[str, Any]], desired_url: str
) -> ResourcePlan:
    """The plan that leaves 1 stored row with *desired_url*.

    * no matching row                 -> create a row
    * 1 row with the URL and the type -> no change, so a restart writes no row
    * 1 row with an old URL or type   -> update that row
    * 2 rows or more                  -> keep and update the first, delete the rest
    """
    wanted = resource_path(desired_url)
    matches = [item for item in items if _serves_bundle(item, wanted)]
    if not matches:
        return ResourcePlan(create=True)

    # `keep` matched, so its URL is a string.
    keep, *extra = matches
    stale = keep["url"] != desired_url or keep.get("type") != RESOURCE_TYPE
    return ResourcePlan(
        update_id=str(keep["id"]) if stale else None,
        delete_ids=tuple(str(item["id"]) for item in extra),
    )


def resource_payload(url: str) -> dict[str, str]:
    """The create and update body of Lovelace, with ``res_type`` and not ``type``."""
    return {"res_type": RESOURCE_TYPE, "url": url}
