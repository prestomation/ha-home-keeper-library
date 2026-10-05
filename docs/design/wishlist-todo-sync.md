---
title: Wishlist and to-do sync
summary: How a book goes on the wishlist of a person, and how the books to buy go to a to-do list of that person and come back as bought.
implements:
  - custom_components/home_keeper_library/wishlist.py
  - custom_components/home_keeper_library/wishlist_sync.py
related: [store-models, entities, events-api]
source_hash: a0c544ba23be
---

# Wishlist and to-do sync

Each book can be on the wishlist of 1 person. An admin can link a person to an existing
`todo` entity, such as a shopping list. A wishlist book with **Buy** set then shows on
that list as "Title by Author". When the person completes the item, the book is marked
bought. The sync follows the design of the shopping sync of Home Keeper.

## Goals

- **G1. The list holds what to buy now.** An item goes away when its book leaves the
  wishlist, when **Buy** turns off, or when the person gets another list.
- **G2. A completed item is never touched.** It marks the book bought, and then the sync
  leaves the item and the book alone.
- **G3. An unreadable list is not an empty list.** A list that the sync cannot read gets
  no step, so a list that is offline loses no item.
- **G4. Best effort.** A failed `todo` call never fails the change that started the pass.

## Non-goals

- The shopping list of Home Keeper. The library uses any `todo` entity that the admin
  picks for the person.
- Reading the items that a user adds to the list by hand. The sync reads only its own
  items.
- A wishlist shared by 2 people. A book is on 1 wishlist at a time.

## Design

### Records

A book on a wishlist has `wishlist: {person_id, buy, added_at, todo_uid, todo_entity,
bought}`. `add_to_wishlist` takes a `book_id`, an ISBN or a title, and adds the book when
none matches. `update_wishlist` changes `buy` or the person. `remove_from_wishlist`
removes the entry. `got_wishlist_book` adds a copy and removes the entry in 1 change. A
person's list is `wishlist_todo` in the `people` section.

### Planner

`wishlist.lists_to_read` names the lists in use. `wishlist.plan_sync` takes the
document, the items of each list and the summary template, and returns a `SyncPlan`. A
list that the sync could not read is None:

- an entry that wants an item and has none gets an add step;
- the `add_item` service of the `todo` domain returns no uid, so the next pass binds the
  new item: an open item with the same summary that no other book holds;
- a bound item that is gone turns `buy` off, so the sync does not add it again against
  the choice of the user who deleted it;
- a bound item that is completed marks the book `bought` and fires `book_updated`;
- an entry that wants no item, and each orphan in `todo_orphans`, gets a remove step.

### Sync

`WishlistSync` runs a pass after each store change, when a list in use changes state, and
every 10 minutes. A pass reads each list with the `todo` service `get_items`, applies the
remove and add steps with `remove_item` and `add_item`, and writes the store steps with
`LibraryStore.apply_wishlist_plan`. A pass that added an item or changed the store runs
again, at most 3 times, so a new item is bound in the same run. A lock runs 1 run at a
time.

The summary comes from `backend_strings` `item.summary` in the Home Assistant language.
`list_todo_entities` gives the tab the lists to pick from, without the library's own
To read lists.

## Trade-offs

- **Bind by summary** over **store the uid at once**: `add_item` gives no uid back.
  2 books with the same summary on 1 list bind in order.
- **Buy turns off on a deleted item** over **add it again**: the user who deleted the item
  decided. An admin turns **Buy** on again to put it back.
- **A sweep every 10 minutes** over **only state changes**: a missed state change delays
  the list by 10 minutes at most.

## One-way doors

- The `wishlist` block of a book and the `wishlist_todo` setting of a person.
- The item summary format, because the bind step matches it.
- `bought` as the end state of an entry.
