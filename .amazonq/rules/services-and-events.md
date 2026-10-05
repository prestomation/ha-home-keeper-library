---
title: Services and events rules
summary: How to add a service, a websocket command, an event or another surface that integrators use.
---

# Services and events rules

How the surfaces work is in [events-api](../../docs/design/events-api.md). Integrators read
[INTEGRATING.md](../../docs/INTEGRATING.md) and [EVENTS.md](../../docs/EVENTS.md).

## Services are the contract

- **Every action that changes or exports data is a `home_keeper_library.*` service.**
  Automations, scripts, voice assistants and other integrations build on services. A
  websocket command is only a UI speed-up and never replaces a service.
- **A new action is a service first.** Add 1 handler to `SERVICE_HANDLERS` and 1 field
  schema to `SERVICE_FIELDS` in `services.py`, a `ServiceSpec` to `api_surface.SERVICES`,
  a `services.yaml` entry, and `strings.json` text with parity in every
  `translations/<lang>.json`. hassfest and the parity test enforce the text.
- **The runtime reads the model.** `services.async_register_services` registers each
  `ServiceSpec`. `websocket_api.async_register` registers the twin of each service that
  is not in `api_surface.READ_SERVICES`, with the same fields. The twin calls the same
  handler, so the 2 surfaces cannot do different things.
- **Record the privilege of each new surface.** Set `admin_only` or `caller_scoped` in
  `api_surface.py`, and give the reason in the PR's Security section
  ([architecture.md](architecture.md#how-to-decide)).
- `async_unload_entry` removes the services that `api_surface.SERVICE_NAMES` lists, so a
  service in the model is torn down with no second edit.
- A read service uses `SupportsResponse.ONLY` and goes through a projection. A mutation
  returns its record with `SupportsResponse.OPTIONAL`.
- A handler finds the coordinator for each call and raises the localized `not_loaded`
  error while no entry is loaded.
- A service that takes a book takes `book_id`. Titles are not unique. `borrow_book` and
  `add_to_wishlist` also take `isbn` or `title`, and add the book when none matches.

## Events

- **Every state change fires a `home_keeper_library_<noun>_<verb>` event.** Build the
  payload with a pure function in `events.py`, so tests and integrators check the payload
  that ships.
- **Fire at the `store.py` chokepoint**, after the save, not in a handler. Then a change
  from the tab, a service, a to-do list or a Home Keeper task fires the same event.
- The book events share the spine `{book_id, title, person_id, origin}`
  (`events.book_event_data`). A specific event extends it, for example `copy_moved` adds
  `previous_shelf_id`. Copy a list into a payload. Never alias the caller's list.
- An update that changes no field fires no event. A CSV import fires only
  `import_completed`.
- An event needs no new service. It observes a change that a service already makes.
- **A new event is not done until `docs/EVENTS.md` describes it**: when it fires, its
  payload, and an example automation.
- Some changes fire no event yet ([IDEAS.md](../../IDEAS.md#events-for-every-change)).
  A new change does not add to that list.

## The declared surface

- **`api_surface.py` declares every surface an integrator can touch**: services, events
  and payloads, entity platforms and attributes, options, websocket commands, HTTP
  views, and the events of Home Keeper that the library listens for. A new one is not
  done until it has a spec there. `tests/unit/test_api_surface.py` parses the source and
  fails on drift.
- **Never write a second literal list beside a modelled one.**
- **The model holds names and structure only.** Labels and descriptions come from
  `services.yaml` and `strings.json`. Never put a user-facing sentence in
  `api_surface.py`. `EventSpec.summary` is the 1 exception, because a bus event has no
  Home Assistant string source.
- `api_surface.py` imports `const` and nothing else from the integration, and nothing
  from Home Assistant.
- **The API reference is generated, never written.** `ci/generate_api_docs.py` renders it
  into the gitignored `website/developer/`. A canonical doc links to it by its site URL.
- `SURFACE_KINDS` also lists the surfaces that the integration does not offer, each with
  a reason. A new kind of surface gets a row there first.

## Errors and escaping

- Error rules are in [architecture.md](architecture.md#localized-text). Escaping rules
  are in [frontend.md](frontend.md#markup-and-text).
