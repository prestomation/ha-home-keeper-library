# Home Keeper Library events

Home Keeper Library fires a Home Assistant bus event for each change to the
library. Automations and other integrations use these events. Each event
observes a change that a service already makes, so an event needs no service of
its own.

A pure function in `events.py` builds each payload. The store fires the event
after it saves the change. So a change from the tab, the card, a service, the
to-do list or a Home Keeper task fires the same event.

`api_surface.py` has the same catalog in `EVENTS` and `PAYLOAD_SPINES`.
`tests/unit/test_api_surface.py` calls the real builders and compares the keys.

## Event catalog

Names follow `home_keeper_library_<noun>_<verb>`.

| Event | Fires when |
|---|---|
| `home_keeper_library_room_added` | A room is added. |
| `home_keeper_library_room_updated` | A room changes. The payload has `changed_fields`. |
| `home_keeper_library_room_removed` | A room is deleted. |
| `home_keeper_library_bookcase_added` | A bookcase is added. |
| `home_keeper_library_bookcase_updated` | A bookcase changes or moves to another room. |
| `home_keeper_library_bookcase_removed` | A bookcase is deleted. |
| `home_keeper_library_shelf_added` | A shelf is added. |
| `home_keeper_library_shelf_updated` | A shelf changes or moves to another bookcase. |
| `home_keeper_library_shelf_removed` | A shelf is deleted. |
| `home_keeper_library_book_added` | A book is added. |
| `home_keeper_library_book_updated` | The fields, the cover or the wishlist entry of a book change. |
| `home_keeper_library_book_removed` | A book is deleted with its copies, reading rows and loans. |
| `home_keeper_library_copy_added` | A copy is added. |
| `home_keeper_library_copy_moved` | A copy moves to another shelf, or to no shelf. |
| `home_keeper_library_copy_removed` | A copy is deleted. |
| `home_keeper_library_reading_changed` | The reading status of a person changes. |
| `home_keeper_library_book_finished` | The reading status of a person becomes `read`. |
| `home_keeper_library_loan_started` | A book is lent or borrowed. |
| `home_keeper_library_loan_returned` | A loan is returned. |
| `home_keeper_library_loan_overdue` | An open loan passes its due date. |
| `home_keeper_library_wishlist_added` | A book goes on the wishlist of a person. |
| `home_keeper_library_wishlist_removed` | A book leaves the wishlist. |
| `home_keeper_library_import_completed` | A CSV import is written. |

## Payloads

The book, copy, reading, loan and wishlist events share 1 spine:

```json
{
  "book_id": "5f0c1b2a9d8e4f7a8b6c5d4e3f2a1b0c",
  "title": "The Left Hand of Darkness",
  "person_id": "alice",
  "origin": null
}
```

`person_id` is the id of the Home Assistant person, or `null`. `origin` is the
marker of the caller, or `null` for a user. A change that comes from a Home
Keeper task has the origin `home_keeper_library`.

The other keys of each event are in the generated API reference and in
`api_surface.EVENTS`:

- `book_updated` and the location `*_updated` events add `changed_fields`.
- The copy events add `copy_id` and `shelf_id`. `copy_moved` adds
  `previous_shelf_id`.
- `reading_changed` adds `status` and `previous_status`. A removed reading row
  has `status: null`.
- `book_finished` adds `finished`, `rating` and `read_count`.
- The loan events add `loan_id`, `direction`, `copy_id`, `party`, `started`,
  `due` and `returned`. `direction` is `out` for a lent copy and `in` for a
  borrowed book.
- The wishlist events add `buy` and `bought`.
- The room, bookcase and shelf events have their own ids and `name` in place of
  the book spine.
- `import_completed` has `person_id`, `source` and the counts of the import.

## Rules

- `loan_overdue` fires once for each due date. The library checks at setup and
  each hour. A new due date can fire it again.
- A CSV import fires only `import_completed`. It fires no event for each row.
- `book_finished` fires with `reading_changed`, in that order.
- Deleting a room, a bookcase or a shelf with `force: true` fires a `*_removed`
  event for each child and a `copy_moved` event for each copy that moves to no
  shelf.

## Example automation

```yaml
automation:
  - alias: Notify when a loan is overdue
    trigger:
      - platform: event
        event_type: home_keeper_library_loan_overdue
    action:
      - service: persistent_notification.create
        data:
          title: "Loan overdue"
          message: "{{ trigger.event.data.title }} was due on {{ trigger.event.data.due }}."
```
