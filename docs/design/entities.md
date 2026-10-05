---
title: Coordinator and entities
summary: The coordinator that pushes each store change to the entities, the library and per-person sensors, the To read list of each person, and the service device.
implements:
  - custom_components/home_keeper_library/coordinator.py
  - custom_components/home_keeper_library/entity.py
  - custom_components/home_keeper_library/sensor.py
  - custom_components/home_keeper_library/todo.py
related: [store-models, people-privilege, events-api]
source_hash: e36c5bc237d7
---

# Coordinator and entities

The entities are the usage surface for automations, dashboards and voice: counts of the
library, the reading of each person, and a native to-do list of the books that each
person wants to read.

## Goals

- **G1. Push, never poll.** Each store change reaches the entities at once.
- **G2. Native usage.** A person uses the To read list in the Home Assistant to-do panel,
  on a phone and by voice, with no custom UI.
- **G3. Rename-safe.** A per-person entity is anchored to the person id, so a new name
  keeps the entity and its history.
- **G4. 1 device.** All entities of the config entry are on 1 service device.

## Non-goals

- 1 entity for each book. A library of thousands of books would flood the entity
  registry.
- A calendar of due dates. The loan tasks put due dates in Home Keeper.
- Device triggers. The events cover the changes ([events-api](events-api.md)).

## Design

### Coordinator

`LibraryCoordinator` is a `DataUpdateCoordinator` with no interval. The store calls
`async_store_changed` after each change, and the coordinator sends the document with
`async_set_updated_data`. The coordinator also holds the parts of the loaded entry that
the services, the websocket commands and the views use: the store, the Open Library
client, the lookup queue, the 2 syncs, the Home Keeper link and the currency option.
`coordinator.find_coordinator` returns it for a call, or None while no entry is loaded.

### Device and people

`entity.device_info` gives 1 service device for the config entry.
`entity.async_track_people` adds the entities of each Home Assistant person now, and of a
new person on the next store change. A `PersonEntity` has the person id in its
`unique_id`, the person name in the `{person}` placeholder of its translated name, and the
attribute `person_id`. It is unavailable while the person does not exist.

### Sensors

| Key | State | Attributes |
|---|---|---|
| `books` | Books with 1 copy or more | |
| `loans_out` | Open loans that lend a copy out | |
| `loans_overdue` | Open loans past their due date | |
| `books_read_this_year` | Books that the person finished this year | `goal`, `pages`, `year` |
| `reading_now` | Books with status `reading` | `books`: at most 10 titles |

The counts come from the pure functions of `projections.py`. The hourly overdue check
also updates the listeners, so the date-based states change at midnight within 1 hour.

### To read list

`ToReadList` is a `todo` entity for each person. Its items are the books with status
`want`, oldest first. The summary is "Title by Author" from `backend_strings` and the uid
is the book id.

- Completing an item sets the status `read`, and the store sets `finished` to today.
- Adding an item gives a `want` row to the book with that title, or to the book with that
  summary. If no book matches, the list adds a book with `needs_details: true`, and the
  lookup queue reads Open Library for it.
- Deleting an item removes the `want` row.

## Trade-offs

- **Per-person entities for every person** over **an opt-in list**: each person gets the
  list and the sensors with no setup. The entities are open to every user like all Home
  Assistant entities, so `share_reading` does not hide them
  ([IDEAS.md](../../IDEAS.md#private-per-person-entities)).
- **A to-do list for want** over **a list for each status**: want is the status that a
  person works through.
- **Counts as sensors** over **attributes on 1 sensor**: each count has its own history
  and can drive an automation.

## One-way doors

- The unique ids `home_keeper_library_<key>` and `home_keeper_library_<person_id>_<key>`.
- The sensor keys and the attributes `goal`, `pages`, `year`, `books` and `person_id`.
- The uid of a To read item is the book id.
