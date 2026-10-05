"""Pure planner for the wishlist to-do sync.

Each person can have a ``wishlist_todo``: an existing ``todo.*`` entity that an
admin selects. A wishlist book with ``buy: true`` and not ``bought`` puts 1 item
``Title by Author`` on the list of its person. ``wishlist_sync.py`` reads the
lists with ``todo.get_items``, calls :func:`plan_sync`, and applies the plan with
``todo.add_item`` and ``todo.remove_item`` and through the store.

The rules follow the shopping sync of Home Keeper (``shopping.py``):

* **The list holds what the wishlist wants bought now.** An item goes away when
  its book leaves the wishlist, when ``buy`` turns off, or when the person gets
  another list.
* **A completed item is never touched.** A completed item marks the book
  ``bought``. After that the sync leaves the item and the book alone.
* **An unreadable list is not an empty list.** The plan has no step for a list
  that the caller could not read.
* ``todo.add_item`` returns no uid, so an added item is bound on the next read:
  an open item with the same summary that no other book holds.
* If a bound item is deleted from the list, ``buy`` turns off. The sync does not
  add the item again against the choice of the person who deleted it.

This module imports no Home Assistant code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import SUMMARY_TEMPLATE, book_summary, person_settings

STATUS_COMPLETED = "completed"


@dataclass(frozen=True)
class AddOp:
    """Add an item to a list."""

    book_id: str
    entity_id: str
    summary: str


@dataclass(frozen=True)
class BindOp:
    """Record the uid of the item that holds a book."""

    book_id: str
    entity_id: str
    uid: str


@dataclass(frozen=True)
class RemoveOp:
    """Remove an open item from a list."""

    entity_id: str
    uid: str


@dataclass(frozen=True)
class BoughtOp:
    """The item of a book is completed: mark the book bought."""

    book_id: str


@dataclass(frozen=True)
class UnbindOp:
    """Forget the item of a book. ``buy_off`` also turns ``buy`` off."""

    book_id: str
    buy_off: bool = False


@dataclass(frozen=True)
class DropOrphanOp:
    """Forget an orphan item, after its removal or when it is completed."""

    entity_id: str
    uid: str


@dataclass
class SyncPlan:
    """The steps of 1 sync pass."""

    adds: list[AddOp] = field(default_factory=list)
    binds: list[BindOp] = field(default_factory=list)
    removes: list[RemoveOp] = field(default_factory=list)
    bought: list[BoughtOp] = field(default_factory=list)
    unbinds: list[UnbindOp] = field(default_factory=list)
    drop_orphans: list[DropOrphanOp] = field(default_factory=list)

    @property
    def store_changes(self) -> bool:
        """Whether the plan changes the stored document."""
        return bool(self.binds or self.bought or self.unbinds or self.drop_orphans)

    @property
    def empty(self) -> bool:
        """Whether the plan has no step."""
        return not (self.adds or self.removes or self.store_changes)


def target_list(state: dict[str, Any], book: dict[str, Any]) -> str | None:
    """The list that the item of a wishlist book belongs on, or None."""
    entry = book.get("wishlist")
    if not entry or not entry.get("buy") or entry.get("bought"):
        return None
    target = person_settings(state["people"], entry["person_id"])["wishlist_todo"]
    return target if isinstance(target, str) else None


def lists_to_read(state: dict[str, Any]) -> list[str]:
    """Every list that a sync pass reads, sorted."""
    wanted: set[str] = set()
    for book in state["books"].values():
        if target := target_list(state, book):
            wanted.add(target)
        entry = book.get("wishlist") or {}
        if entry.get("todo_entity"):
            wanted.add(entry["todo_entity"])
    for orphan in state.get("todo_orphans", []):
        wanted.add(orphan["entity_id"])
    return sorted(wanted)


def _find(items: list[dict[str, Any]], uid: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("uid") == uid:
            return item
    return None


def _is_open(item: dict[str, Any]) -> bool:
    return item.get("status") != STATUS_COMPLETED


def plan_sync(
    state: dict[str, Any],
    lists: dict[str, list[dict[str, Any]] | None],
    template: str = SUMMARY_TEMPLATE,
) -> SyncPlan:
    """The steps that make the lists match the wishlist.

    *lists* maps an entity id to its items from ``todo.get_items``, or to None if
    the list could not be read. *template* is the item text template.
    """
    plan = SyncPlan()
    claimed: set[tuple[str, str]] = set()
    # The uids that a book holds now. A summary match never takes one of them.
    for book in state["books"].values():
        entry = book.get("wishlist") or {}
        if entry.get("todo_uid") and entry.get("todo_entity"):
            claimed.add((entry["todo_entity"], entry["todo_uid"]))

    for book_id in sorted(state["books"]):
        book = state["books"][book_id]
        entry = book.get("wishlist") or {}
        target = target_list(state, book)
        bound_entity = entry.get("todo_entity")
        bound_uid = entry.get("todo_uid")

        if bound_entity and bound_uid:
            items = lists.get(bound_entity)
            if items is None:
                continue
            item = _find(items, bound_uid)
            if target == bound_entity:
                if item is None:
                    plan.unbinds.append(UnbindOp(book_id, buy_off=True))
                elif not _is_open(item):
                    plan.bought.append(BoughtOp(book_id))
                continue
            # The book does not want this item now.
            if item is not None and _is_open(item):
                plan.removes.append(RemoveOp(bound_entity, bound_uid))
            plan.unbinds.append(UnbindOp(book_id))
            continue

        if target is None:
            continue
        items = lists.get(target)
        if items is None:
            continue
        summary = book_summary(book, template)
        match = next(
            (
                item
                for item in items
                if item.get("summary") == summary
                and _is_open(item)
                and isinstance(item.get("uid"), str)
                and (target, item["uid"]) not in claimed
            ),
            None,
        )
        if match is not None:
            claimed.add((target, match["uid"]))
            plan.binds.append(BindOp(book_id, target, match["uid"]))
        else:
            plan.adds.append(AddOp(book_id, target, summary))

    for orphan in state.get("todo_orphans", []):
        items = lists.get(orphan["entity_id"])
        if items is None:
            continue
        item = _find(items, orphan["uid"])
        if item is not None and _is_open(item):
            plan.removes.append(RemoveOp(orphan["entity_id"], orphan["uid"]))
        plan.drop_orphans.append(DropOrphanOp(orphan["entity_id"], orphan["uid"]))
    return plan


__all__ = [
    "AddOp",
    "BindOp",
    "BoughtOp",
    "DropOrphanOp",
    "RemoveOp",
    "SyncPlan",
    "UnbindOp",
    "lists_to_read",
    "plan_sync",
    "target_list",
]
