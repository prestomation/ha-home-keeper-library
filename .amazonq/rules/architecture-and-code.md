# Architecture & code conventions

These rules are the conventions for code in Home Keeper Library
(`home_keeper_library`), a companion integration of Home Keeper. Follow them when
you write or review code.

## Administration and usage
- **Administration is the Library tab of the Home Keeper panel**
  (`/home-keeper/library/...`). The library has no sidebar panel of its own. The
  Home Keeper panel is admin-only, so the tab is admin-only. `home_keeper.py`
  registers the tab through `custom_components.home_keeper.panel_tabs`.
- **Usage** is the card, the per-person `sensor` and `todo` entities, and the
  open services and websocket commands, which are scoped to the person of the
  caller.
- **Home Keeper is an `after_dependency`, not a dependency.** The config flow
  aborts with `home_keeper_missing`, `home_keeper_not_set_up` or
  `home_keeper_too_old`. At run time `HomeKeeperLink` shows a repair issue with
  the same reason and turns the tab and the loan tasks off, and the store, the
  services, the card and the entities still work. Never raise
  `ConfigEntryNotReady` for Home Keeper.

## Pure, HA-free core
- These modules import nothing from `homeassistant`: `const`, `isbn`, `models`,
  `events`, `projections`, `openlibrary`, `csv_io`, `wishlist`, `loan_tasks`,
  `backend_i18n` and `api_surface`. `tests/unit/conftest.py` loads them in this
  order, and the mutation allowlist holds the ones with logic.
- They never read a clock. The caller passes `now` (aware ISO 8601) and `today`
  (`YYYY-MM-DD`).
- A pure module raises `models.LibraryError(key, **placeholders)`. The key is in
  `strings.json` `exceptions`. The service layer turns it into a localized
  `ServiceValidationError`, and the websocket layer resolves the message with
  `backend_i18n`.

## One mutation chokepoint
- Every write goes through `LibraryStore` (`store.py`). It checks the input with
  `models`, saves, fires the events and tells its listeners (the coordinator,
  the `subscribe` command, the to-do and loan syncs). `revision` goes up by 1 on
  each change.
- Records are plain JSON dicts. `models.normalize_state` is the migration hook:
  the store runs it on every load, so a new section needs no migration step.
- **An import never replaces the document.** `csv_io.apply_import` plans on a
  snapshot in an executor job, and `commit_import` writes the plan with
  `models.merge_changes`: only the records and fields that the plan changed,
  with no `await` in the middle. A change made while the plan runs stays.
- A book has `lookup_tries`: the Open Library lookups that gave no details.
  Setup queues again each book that `models.books_to_look_up` names, and the
  queue stops at `LOOKUP_MAX_TRIES` across restarts. It is bookkeeping of the
  queue: it fires no event and is not in the CSV export, and an imported book
  starts at 0.

## Read projections
- **A reply never leaks.** Every read goes through `projections.py`. A non-admin
  reads no `price`, `value`, `acquired_from` or loan `party`, and reads the
  reading row of another person only if that person shares it, never with
  `private_notes`. Test each new field with an admin and with a non-admin user.

## Entities
- 1 service device holds every entity. The per-person entities have the person id
  (the collection id of the Home Assistant person) in their `unique_id`, so a new
  name keeps the entity. A new person gets entities on the next store change.
- Use `has_entity_name` and a `translation_key`. A per-person name has the
  `{person}` placeholder.
- The `To read` list of a person is a `todo` entity. Its uid is the book id.
- **An entity is visible to each user, so it applies the privacy rules.** The
  `To read` list takes a change only from the user of its person, an admin user
  or no user (it reads `self._context.user_id`), else `todo_not_allowed`. While
  a person has `share_reading: false`, each per-person entity is unavailable
  and the list has no items. See [DESIGN.md](../../docs/DESIGN.md).

## Services are the interoperability surface
- **Every action that changes or exports data is a `home_keeper_library.*`
  service.** A service is 1 handler in `SERVICE_HANDLERS` and 1 field schema in
  `SERVICE_FIELDS` (`services.py`), a `services.yaml` entry and `strings.json`
  text in every language.
- **The runtime reads the model.** `services.async_register_services` registers
  each `api_surface.SERVICES` entry and applies its `admin_only` gate.
  `websocket_api.async_register` registers the websocket twin of each service
  from `api_surface.WEBSOCKET_COMMANDS` with the same fields. A twin calls the
  same handler, so the 2 surfaces cannot differ.
- A `caller_scoped` service is open, and its handler lets a non-admin user
  change only their own person. A call with no user is trusted.

## Events are the observation surface
- Each state change fires a `home_keeper_library_<noun>_<verb>` bus event. A
  pure function in `events.py` builds the payload, and the store fires it after
  the save, so every surface is observed the same way.
- The book events share the spine `{book_id, title, person_id, origin}`
  (`events.book_event_data`). Copy a list of the caller into the payload. Never
  alias it.
- A new event goes in `api_surface.EVENTS` and in
  [`docs/EVENTS.md`](../../docs/EVENTS.md) in the same change.
- A change that keeps the shelf of a copy or the status of a reading row still
  fires an event (`copy_updated`, `reading_updated`). A payload names the
  changed fields in `changed_fields` and never carries private values: no
  price, value or private notes, and no setting values of a person.
- A bulk import fires only `import_completed`. `loan_overdue` fires once for each
  due date, with the flag `overdue_fired` on the loan.

## Syncs with other integrations
- The wishlist sync (`wishlist.py` pure, `wishlist_sync.py` HA side) and the loan
  task sync (`loan_tasks.py` pure, `loan_sync.py` HA side) follow the shopping
  sync of Home Keeper: an unreadable list or task list plans nothing, a
  completed item is never touched, and each call to another integration is best
  effort.
- Each call to Home Keeper sends `origin: "home_keeper_library"`, and the
  listeners ignore events with that origin.

## Frontend bundles
- `frontend_assets.py` serves `frontend/dist/` at `/home_keeper_library_static`
  and adds the card bundle as a frontend module. The tab module URL and the card
  URL carry a content hash in `?v=`.
- Covers are served by an authenticated view. An `<img>` element cannot send a
  token, so the client signs the path with `auth/sign_path` or reads the image
  with `fetchWithAuth`.

## Errors, validation & security
- Service handlers raise `ServiceValidationError` for user-facing errors. The pure
  core raises `LibraryError`, which the boundary translates. Websocket commands
  return `connection.send_error` with the key as the code and the resolved text.
  `tests/unit/test_exception_translations.py` checks that each `LibraryError` key
  has a message.
- **Exceptions are localized (exception-translations rule).** Every user-facing
  `ServiceValidationError` / `HomeAssistantError` is built with
  `translation_domain=DOMAIN` + a `translation_key` (and `translation_placeholders`),
  never a bare string; the key is defined under `exceptions` in `strings.json` (and
  every locale). A pure-AST drift-guard (`tests/unit/test_exception_translations.py`)
  fails the build on a bare-string raise or a key missing from `strings.json`.
- Escape all user-provided content before injecting into `innerHTML` in the panel
  (`escapeHTML`).
- An upload needs a real admin user. The view reads the type from the first bytes
  and Pillow writes a new JPEG in an executor job.

## Version single-source-of-truth
- `manifest.json` `version` is canonical. `const.py` `PANEL_VERSION` mirrors it and
  `release.yml` asserts they match; `rollup.config.mjs` reads `PANEL_VERSION` from
  `const.py` so the bundles are stamped consistently. Bump both in one PR.
