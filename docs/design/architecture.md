---
title: Architecture
summary: The split of Home Keeper Library into a pure core and Home Assistant glue. The setup steps. The index of the design docs.
implements:
  - custom_components/home_keeper_library/__init__.py
  - custom_components/home_keeper_library/const.py
  - custom_components/home_keeper_library/config_flow.py
  - custom_components/home_keeper_library/diagnostics.py
  - custom_components/home_keeper_library/backend_i18n.py
  - custom_components/home_keeper_library/manifest.json
related: [store-models, people-privilege, events-api, home-keeper-dependency, frontend-tab-card]
source_hash: a2cc2b83c079
---

# Architecture

Home Keeper Library is a Home Assistant integration for the books of a household. It
records the rooms, bookcases and shelves of the home, the books and their copies, the
reading status of each person, the loans and a wishlist. It is a companion of Home
Keeper: admins manage the library in a tab of the Home Keeper panel. Every user reads and
updates their own reading status through a card, native entities and services.

## Goals

- **G1. Testable core.** The rules for records, ISBNs, Open Library replies, CSV files,
  projections and the sync plans run without Home Assistant, so the fast unit tier and
  the mutation gate can check them.
- **G2. One write path.** Every change goes through 1 store method. That method checks
  the input, saves the change and fires its events ([store-models](store-models.md)).
- **G3. Services first.** Each data action is a `home_keeper_library.*` service, so
  automations, scripts, voice and other integrations can do what the tab does.
- **G4. Per-person privacy.** A non-admin user changes only their own reading data, and
  reads only what the projections allow ([people-privilege](people-privilege.md)).
- **G5. Useful without the tab.** If Home Keeper is missing or too old, the store, the
  services, the card and the entities still work.

## Non-goals

- A sidebar panel of its own. The admin UI is a tab in the Home Keeper panel
  ([home-keeper-dependency](home-keeper-dependency.md)).
- More than 1 config entry. The manifest sets `single_config_entry`.
- A book catalog service other than Open Library. A cloud account or a sync between
  homes.

## Design

### Module map

| Layer | Modules | Rule |
|---|---|---|
| Pure core | `const.py`, `isbn.py`, `models.py`, `events.py`, `projections.py`, `openlibrary.py`, `csv_io.py`, `wishlist.py`, `loan_tasks.py`, `card_resource.py`, `backend_i18n.py`, `api_surface.py` | No `homeassistant` import. Time comes in as an argument. |
| Boundary | `store.py`, `coordinator.py`, `people.py`, `openlibrary_client.py` | Talks to Home Assistant storage, the bus, the person registry and HTTP. |
| Glue | `__init__.py`, `services.py`, `websocket_api.py`, `covers.py`, `book_lookup.py`, `home_keeper.py`, `loan_sync.py`, `wishlist_sync.py`, `frontend_assets.py`, `card.py`, `config_flow.py`, `diagnostics.py` | Registers surfaces and runs the syncs. |
| Platforms | `sensor.py`, `todo.py`, with `entity.py` | `const.PLATFORMS` lists them. |

The mutation allowlist (`only_mutate` in `pyproject.toml`) holds the pure modules with
logic. `api_surface.py` declares each surface that an integrator sees
([events-api](events-api.md)).

### Setup

`async_setup` does nothing. The integration has no YAML configuration.
`CONFIG_SCHEMA` is `cv.config_entry_only_config_schema`.

The manifest has `lovelace` in `after_dependencies`, because the card writes a Lovelace
resource.

`async_setup_entry` runs these steps in order:

1. Read the string tables of the Home Assistant language in an executor job
   (`backend_i18n.preload`), and load the store.
2. Make `LibraryCoordinator` and give it the Open Library client, the lookup queue and
   the 2 syncs. Store it as `entry.runtime_data`. An update listener of the entry fires
   `settings_updated` when the options flow changes the currency.
3. Register the static path, the card delivery, the websocket commands and the cover
   views ([frontend-tab-card](frontend-tab-card.md#delivery)).
4. Forward `const.PLATFORMS` and register the services.
5. Start the lookup queue, and queue again each book that still needs a lookup
   ([open-library-covers](open-library-covers.md#lookup-queue)). Start the wishlist sync
   and the loan sync.
6. Start `home_keeper.HomeKeeperLink`, which adds the tab and the companion or shows a
   repair issue.
7. Fire the overdue loans, start the hourly overdue check, and delete the old uploads
   that no book uses.

### Unload

`async_unload_entry` unloads the platforms and removes each service in
`api_surface.SERVICE_NAMES`. Each sync, the queue and the Home Keeper link stop through
`entry.async_on_unload`. The link removes the tab. The static path and the card resource
stay, because most unloads are half of a reload. `async_remove_entry` deletes the card
resource when the integration is removed.

### Config entry

The config flow checks Home Keeper first and aborts with the reason if the check fails.
Then it asks for the currency of the prices and values, with the currency of Home
Assistant as the default. The options flow changes the currency and returns
`config_flow.merge_flow_input`, so no stored key is lost.

### Localized text

The pure core raises `models.LibraryError` with a key of `strings.json` `exceptions`. A
service turns it into a `ServiceValidationError`, which Home Assistant translates. A
websocket error and an HTTP view error show their text as is, so
`backend_i18n.resolve_exception` resolves it in the language of Home Assistant. Text that
is not an exception, such as the tab title and the loan task names, is in
`backend_strings/<lang>.json` and resolves with `backend_i18n.resolve_string`.

### Diagnostics

`diagnostics.async_get_config_entry_diagnostics` returns the options, the tab state, the
revision, the counts and the library document. It redacts the names of loan parties, the
notes and `acquired_from`.

### Design doc index

| Doc | Subject |
|---|---|
| [store-models](store-models.md) | The storage document, the records and the write path |
| [people-privilege](people-privilege.md) | The caller, the admin gate and the read projections |
| [events-api](events-api.md) | Services, websocket commands, events and the API surface model |
| [open-library-covers](open-library-covers.md) | Open Library, the lookup queue and the cover files |
| [scan-and-isbn](scan-and-isbn.md) | ISBN rules, the camera scanner and the scan service |
| [csv-import-export](csv-import-export.md) | Goodreads, StoryGraph and library CSV files |
| [loans-home-keeper](loans-home-keeper.md) | Loans and their Home Keeper tasks |
| [wishlist-todo-sync](wishlist-todo-sync.md) | The wishlist and its per-person to-do list |
| [entities](entities.md) | The coordinator, the sensors and the To read lists |
| [home-keeper-dependency](home-keeper-dependency.md) | The check, the tab, the companion and the repairs |
| [frontend-tab-card](frontend-tab-card.md) | The tab, the card, routing, i18n and the bundles |

## Trade-offs

- **A tab in the Home Keeper panel** over **a sidebar panel of its own**: 1 admin place for
  the home, and Home Keeper owns the history and the layout. The cost is the dependency.
- **Services registered at entry setup** over **services registered in `async_setup`**:
  the teardown reads the model, so registration and removal cannot disagree. A call
  during a reload gets "action not found".
- **1 document for the whole library** over **a file for each section**: 1 save is 1
  consistent state. A library of 5000 books is the design size.

## One-way doors

- The domain `home_keeper_library`, the static path `/home_keeper_library_static` and the
  tab path `/home-keeper/library`.
- The service names and fields, and the event names and payloads
  ([INTEGRATING.md](../INTEGRATING.md)).
- The storage key `home_keeper_library`, `const.STORAGE_VERSION` and the option key
  `currency`.
