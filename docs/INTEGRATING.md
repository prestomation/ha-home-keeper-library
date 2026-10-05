---
title: Integrating with the library
summary: How automations, scripts, voice assistants and other integrations use the services, events and entities of Home Keeper Library, for integrators.
---

# Integrate with Home Keeper Library

Automations, scripts, voice assistants and other integrations use 3 stable surfaces:

- **Services** change the library.
- **Events** fire after each change.
- **Entities** show the current state.

Do not read the storage file or call the websocket commands. The tab and the card use
those, and they can change.

The [API reference](https://prestomation.github.io/ha-home-keeper-library/developer/api)
lists every service field, event payload and entity attribute. The site generates it
from the integration. Which service an admin or a user can call is in
[SECURITY.md](SECURITY.md).

## Services

Each operation of the tab is a `home_keeper_library.*` service. The groups are:

| Group | Services |
|---|---|
| Locations | `add_room`, `update_room`, `delete_room`, the same 3 for `bookcase` and `shelf` |
| Books | `lookup_isbn`, `add_book`, `update_book`, `delete_book`, `refresh_book`, `scan_isbn` |
| Copies and covers | `add_copy`, `update_copy`, `move_copy`, `delete_copy`, `set_cover` |
| Reading | `set_reading` |
| Loans | `lend_book`, `borrow_book`, `return_loan`, `update_loan`, `delete_loan` |
| Wishlist | `add_to_wishlist`, `update_wishlist`, `remove_from_wishlist`, `got_wishlist_book` |
| People and settings | `set_person_settings`, `set_settings` |
| Files | `import_csv`, `export_csv` |
| Reads | `list_books`, `get_book`, `list_locations`, `list_loans`, `list_people` |

A service that changes data returns its record when the call asks for a response. A read
service always returns a response. Use `book_id` to name a book, because 2 books can have
the same title.

### Add a book by ISBN

```yaml
action:
  - action: home_keeper_library.add_book
    data:
      isbn: "9780441478125"
    response_variable: result
  # result.book.id is the book id. result.existing is true if the ISBN was stored.
```

### Mark a book as read

```yaml
action:
  - action: home_keeper_library.set_reading
    data:
      book_id: "5f0c1b2a9d8e4f7a8b6c5d4e3f2a1b0c"
      person_id: "alice"
      status: read
      rating: 5
```

`person_id` is the id of a Home Assistant `person`, from its `id` attribute. A call from a
user with no `person_id` acts for the person of that user. A call from an automation has
no user, so it names the person.

### Find a book

```yaml
action:
  - action: home_keeper_library.list_books
    data:
      query: dune
      owned: true
    response_variable: found
```

Each book in the reply has `owned`, `copy_count`, `cover_url` and the reading rows that
the caller can read.

Guard each call from another integration with
`hass.services.has_service("home_keeper_library", "<service>")`, so that integration
still works when the library is not installed.

## Events

[EVENTS.md](EVENTS.md) has the catalog, the payloads and an example automation. Use an
`event` trigger on a `home_keeper_library_<noun>_<verb>` event, such as
`home_keeper_library_book_finished` or `home_keeper_library_loan_overdue`.

## Entities

| Entity | State |
|---|---|
| `sensor` Books | The books with 1 copy or more |
| `sensor` Loans out | The open loans of lent copies |
| `sensor` Loans overdue | The open loans past their due date |
| `sensor` *person* books read this year | The books that the person finished this year, with `goal`, `pages` and `year` |
| `sensor` *person* reading now | The books with status Reading, with `books` |
| `todo` *person* to read | The books with status Want to read |

The entities are on 1 service device, Home Keeper Library. The unique id of a
per-person entity holds the person id, so a new name of the person keeps the entity.

## Home Keeper

The library calls the Home Keeper services `register_companion`, `add_task`,
`update_task`, `complete_task`, `delete_task` and `list_tasks`, and listens for
`home_keeper_task_completed`, `home_keeper_task_deleted` and
`home_keeper_register_companions`. A loan task in Home Keeper has the source
`{"home_keeper_library": {"loan_id": "<id>"}}`. Do not change that source from another
integration.

## Contract

- A record id is opaque and stays the same when the record changes. Use the id, not the
  name or the title.
- A service raises `ServiceValidationError` with a translation key for bad input, such as
  an unknown id, an invalid ISBN or a shelf that is not empty.
- A non-admin caller of an admin-only service gets `Unauthorized`.
- The services, the tab and the card use the same code for each operation. A change from
  any of them fires the same event.
