---
title: Architecture rules
summary: The admin and usage split, the per-person privilege gate, the read projections, the pure core, the store chokepoint, entities, options and localized text.
---

# Architecture rules

How the integration is built is in [docs/design/architecture.md](../../docs/design/architecture.md).
This file gives the rules for code that changes it.

## Home Keeper

- **Home Keeper is an `after_dependencies` entry, never a `dependencies` entry.** The
  config flow must load and say why it stops. It aborts with `home_keeper_missing`,
  `home_keeper_not_set_up` or `home_keeper_too_old`.
- **Never raise `ConfigEntryNotReady` for Home Keeper.** A retry cannot install or update
  it. `home_keeper.HomeKeeperLink` shows a repair issue with the same reason, and turns
  the tab and the loan tasks off. The store, the services, the card and the entities
  still work ([home-keeper-dependency](../../docs/design/home-keeper-dependency.md)).
- Each call to a Home Keeper service is guarded with `has_service` and sends
  `origin: "home_keeper_library"`. A listener ignores an event with that origin.

## Administration and usage

- **Administration is the Library tab of the Home Keeper panel** at
  `/home-keeper/library/...`. The library has no sidebar panel of its own. The Home
  Keeper panel is admin-only, so the tab is admin-only.
- **Usage goes through the card, the per-person `sensor` and `todo` entities, and the
  open services**, which act for the person of the caller. Never put management UI in
  the card.
- All writes go through `LibraryStore` (`store.py`). Entities, the tab and the card read
  the document and never write it.
- Records are plain JSON-serializable dicts in storage, never model objects.
- **A bulk write never replaces the document.** Plan it on a snapshot, then write only
  what the plan changed with `models.merge_changes`, with no `await` between the merge and
  the save. A change made while the plan runs stays
  ([csv-import-export](../../docs/design/csv-import-export.md#steps)).
- A field that only a queue or a sync reads, such as `lookup_tries` or `hk_task_id`, is
  bookkeeping. It fires no event and is not in the CSV export. A new book gets the start
  value from `models.build_book`, and `models.normalize_state` gives it to an old book.
- The store tells its listeners after each save. The coordinator sends the document to
  the entities with `async_set_updated_data`, so an entity never waits for a poll.

## Privilege model

The admin and usage split is also the security boundary ([SECURITY.md](../../docs/SECURITY.md)).

- **One gate for both paths.** `services.async_run` refuses a non-admin caller of an
  `admin_only` service with `Unauthorized`. The service handler and the websocket twin
  both call it, so a gate cannot be on 1 path only. The twin also checks the flag before
  it reads the input.
- A websocket command with no service twin carries `@websocket_api.require_admin` when
  it is admin-only.
- **A `caller_scoped` service is open**, and its handler lets a non-admin user change
  only their own person (`services._self_or_admin`). `set_person_settings` also refuses
  `wishlist_todo` from a non-admin user.
- The caller is a Home Assistant user. Its person is the `person` whose `user_id` is that
  user (`people.actor_for_user`). A person-scoped call with no person raises `no_person`.
- A call with no `context.user_id` comes from an automation or the core and is trusted.
- Raise the bare `Unauthorized`. It is the 1 exception to localized exceptions, and the
  websocket and REST layers map it to `unauthorized` and 401.
- Serve only built assets as a static path. Home Assistant serves static paths before
  authentication.

### Read projections

- **A reply never leaks.** Every read goes through `projections.project_state` or
  `projections.project_book`. A non-admin reads no `price`, `value` or `acquired_from`
  of a copy, and no `party` of a loan.
- A non-admin reads the reading row of another person only if that person has
  `share_reading: true`, and never with `private_notes`.
- A new field that a non-admin must not read goes in a `PRIVATE_*_FIELDS` tuple of
  `projections.py`. Test each new field with an admin and with a non-admin user.

### How to decide

Use this list for each new service, websocket command, HTTP method and event. Write the
result in the plan's Security section ([pr-workflow.md](pr-workflow.md)).

- **Open, for the caller's own person: reading status, rating, notes and settings.** A
  non-admin user changes only their own rows.
- **Open: a read that the card or a native entity needs**, through a projection.
- **Admin-only: the catalog.** Rooms, bookcases, shelves, books, copies, covers, loans
  and the wishlist.
- **Admin-only: settings and configuration**, and each operation that can send text to a
  place the caller cannot reach, such as a to-do list or a Home Keeper task.
- **Admin-only: bulk and whole-store operations**, such as import and export.
- **Admin-only: each operation that shows what Home Assistant hides from a user**, such
  as the list of to-do entities.
- **An upload always needs a real admin user.** A signed URL never writes.
- **If no rule fits, ask the maintainer.** Write the answer in the plan, then add the rule
  here.

## Pure core

- The pure modules (the module map in the
  [architecture design doc](../../docs/design/architecture.md#module-map)) never import
  `homeassistant`. `tests/unit/test_pure_core.py` checks each one, and checks the module
  map against `_PURE_MODULES` in `tests/unit/conftest.py`.
- A pure function never reads a clock. The caller passes `now` (an aware ISO 8601
  timestamp) and `today` (`YYYY-MM-DD`).
- All datetimes are timezone-aware. Use `homeassistant.util.dt` at the HA boundary
  (`store.now` and `store.today`).
- The pure core raises `models.LibraryError(key, **placeholders)`. The key is in
  `strings.json` `exceptions`.
- `models.normalize_state` runs on each load, so a new section of the document needs no
  migration step.

## Entities and devices

How the entities work is in [entities](../../docs/design/entities.md).

- 1 service device groups every entity of the config entry (`DeviceInfo` with
  `entry_type=SERVICE`).
- A per-person entity has the person id in its `unique_id`. The person id is the
  collection id of the Home Assistant person, never the entity id, so a rename keeps it.
- Use `has_entity_name` and a `translation_key`. A per-person name has the `{person}`
  placeholder.
- **An entity applies the privacy rules itself**, because Home Assistant shows each
  entity to every user and has no projection. A per-person entity is unavailable while
  its person has `share_reading: false`. A write method of a per-person entity refuses a
  user who is not the person and not an admin, with a localized error
  ([people-privilege](../../docs/design/people-privilege.md#entities)).

## Options

- The only option is `currency`. The config flow and the options flow ask for it, and
  `set_settings` writes it.
- **An options flow merges. It never replaces.** Return `config_flow.merge_flow_input`
  from `async_create_entry`, never `user_input`. Home Assistant stores the result as the
  whole options object, so a raw return deletes every key that the form does not show.
- Add an `OptionSpec` to `api_surface.OPTIONS` for each key.

## Localized text

- **Every user-facing exception is localized.** The service layer turns a
  `LibraryError` into a `ServiceValidationError` with `translation_domain=DOMAIN`, the
  key and the placeholders. Never raise with an f-string.
  `tests/unit/test_exception_translations.py` fails on a bare raise and on a key that
  `strings.json` does not have.
- A websocket error and an HTTP view error show their message as is. Resolve it with
  `backend_i18n.resolve_exception` in the language of Home Assistant.
- Text that is not an exception and has no place in `strings.json` goes in
  `backend_strings/<lang>.json`: the tab title, the loan task names and the to-do item
  summary.
