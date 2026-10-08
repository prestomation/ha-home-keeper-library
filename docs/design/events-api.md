---
title: Services, websocket commands, events and the API surface
summary: How each operation is 1 handler behind a service and its websocket twin, how the events are built and fired, and how api_surface.py declares the whole surface.
implements:
  - custom_components/home_keeper_library/api_surface.py
  - custom_components/home_keeper_library/services.py
  - custom_components/home_keeper_library/websocket_api.py
  - custom_components/home_keeper_library/events.py
related: [people-privilege, store-models, entities, architecture]
source_hash: ec222cebbd74
---

# Services, websocket commands, events and the API surface

Services are the contract for automations, scripts, voice and other integrations. The
tab and the card use websocket commands, and each command that changes data is the twin
of a service. Bus events observe each change. `api_surface.py` declares all of them. The
integrator view is [INTEGRATING.md](../INTEGRATING.md) and [EVENTS.md](../EVENTS.md).

## Goals

- **G1. 1 handler for each operation.** A service and its websocket twin call the same
  handler with the same fields and the same gate, so they cannot differ.
- **G2. Every change is observable.** The store fires a
  `home_keeper_library_<noun>_<verb>` event after it saves.
- **G3. 1 declared surface.** The runtime registers and removes the surfaces from
  `api_surface.py`, and a drift test reads the source against it.
- **G4. Localized errors.** A refused call gives a key and a message in the language of
  the user.

## Non-goals

- A REST API. The services and the HTTP views of the covers are the external paths.
- Device triggers, conditions or actions ([entities](entities.md)).
- Websocket twins of the read services. `get_state` gives the same data to the tab.

## Design

### Services

`services.py` has 1 handler for each service in `SERVICE_HANDLERS`, of the form
`async (ctx, data) -> reply`, and 1 voluptuous field map in `SERVICE_FIELDS`.
`services.async_register_services` registers each `ServiceSpec` with its fields and its
`SupportsResponse`. A call goes through `services.async_run`:

1. Refuse a non-admin caller of an `admin_only` spec with `Unauthorized`.
2. Find the coordinator, or raise the localized `not_loaded`.
3. Run the handler with a `Ctx` of Home Assistant, the coordinator and the caller.

A handler raises `models.LibraryError`. The service wrapper turns it into a
`ServiceValidationError` with the key and the placeholders. A reply that holds a book goes
through `projections.project_book` for the caller. A mutation returns its record when the
caller asks for a response.

### Websocket commands

`websocket_api.async_register` registers 3 commands of its own and 1 twin for each service
that is not a read service:

- `home_keeper_library/get_state` returns the projected document, the caller (`me`), the
  currency, the tab state and the revision.
- `home_keeper_library/subscribe` sends `{"type": "changed", "revision": n}` after each
  store change. The client then calls `get_state` again. The command listens to the
  dispatcher signal `const.SIGNAL_STORE_CHANGED`, so a subscription stays after a reload
  of the entry.
- `home_keeper_library/list_todo_entities` lists the `todo` entities for the wishlist
  picker, without the library's own lists. It is admin-only.
- `home_keeper_library/<service>` takes the fields of the service and calls
  `services.async_run`, which applies the gate. A `LibraryError` or a
  `ServiceValidationError` becomes `send_error` with the key as the code and the message
  resolved with its placeholders.

### Events

`events.py` has 1 pure builder for each payload shape. The book events share the spine
`{book_id, title, person_id, origin}` from `events.book_event_data`. The room, bookcase
and shelf events have their own id, their parent id and the name. `import_completed` has
the person, the source and the counts. The store fires each event after the save, in the
order of the change: a `force` delete fires each `copy_moved`, then the `*_removed` of
each child, then the `*_removed` of the parent. `book_finished` follows its
`reading_changed`.

An update fires an event only if a field changed. Each `*_updated` event names the
fields in `changed_fields`. A payload never holds a price, a value, private notes or the
value of a setting of a person:

| Event | Builder | Keys after the spine |
|---|---|---|
| `copy_updated` | `events.copy_updated_event_data` | `copy_id`, `shelf_id`, `changed_fields` |
| `reading_updated` | `events.reading_updated_event_data` | `status`, `changed_fields` |
| `loan_updated` | `events.loan_updated_event_data` | the loan keys, `changed_fields` |
| `loan_removed` | `events.loan_event_data` | the loan keys, as before the delete |
| `person_settings_updated` | `events.person_settings_event_data` | no spine: `person_id`, `changed_fields`, `origin` |
| `settings_updated` | `events.settings_event_data` | no spine: `changed_fields`, `currency`, `origin` |

`copy_updated` fires for a copy change other than the shelf, and `copy_moved` for a new
shelf. `reading_updated` fires for a change that keeps the status, and `reading_changed`
for a new status. The loan keys are `loan_id`, `direction`, `copy_id`, `party`, `started`,
`due` and `returned`. `settings_updated` is not a store change: the currency is an option
of the entry. `coordinator.async_check_settings` fires it 1 time for each new currency,
from `set_settings` and from the update listener of the options flow.

### API surface

`api_surface.py` holds `SERVICES`, `READ_SERVICES`, `EVENTS` with `PAYLOAD_SPINES`,
`ENTITY_PLATFORMS`, `WEBSOCKET_COMMANDS`, `HTTP_VIEWS`, `OPTIONS` and `SURFACE_KINDS`. It
also lists the 3 Home Keeper events that the library listens for. It imports only
`const`. `tests/unit/test_api_surface.py` reads the source of the component with `ast`,
and calls the event builders, to check each table. `ci/generate_api_docs.py` renders the
model into the API reference of the docs site.

## Trade-offs

- **Twins from 1 table** over **hand-written commands**: no command can miss its gate.
  The cost is that each command takes exactly the service fields.
- **Read the whole state after each change** over **send the change**: a client has 1
  code path, and a missed message costs nothing.
- **Events from the store** over **events from handlers**: a change from a to-do list, a
  Home Keeper task or an import fires the same event as one from the tab.

## One-way doors

- The service names, the field names and the reply shapes.
- The event names, the spine and the extra keys of each event.
- The websocket command names, because the tab and the card of an older browser session
  call them.
