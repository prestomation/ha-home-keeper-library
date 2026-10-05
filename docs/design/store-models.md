---
title: Store and models
summary: The storage document, the records of the library, the pure model functions and the 1 write path that saves and fires events.
implements:
  - custom_components/home_keeper_library/store.py
  - custom_components/home_keeper_library/models.py
related: [architecture, events-api, people-privilege, csv-import-export]
source_hash: 944bea4aca70
---

# Store and models

The library is 1 JSON document in `.storage/home_keeper_library`. `models.py` holds the
pure functions that check input and build records. `LibraryStore` in `store.py` is the
only code that changes the document.

## Goals

- **G1. One write path.** Each change goes through a `LibraryStore` method. It checks the
  input with `models`, changes the document, saves it, fires the events and tells the
  listeners, in that order.
- **G2. A book is the title, a copy is the thing.** A book with 0 copies is valid: a
  library book in the reading history, an ebook, or a wishlist entry.
- **G3. Stable ids.** Every record id is a uuid4 hex string. A person is a Home Assistant
  person by its collection id, never by its entity id.
- **G4. Safe loads.** A missing or damaged section loads as empty. A new section needs no
  migration step.

## Non-goals

- A database. The design size is 5000 books in 1 document.
- History of a record. The events tell an integrator about each change.
- Records that a caller writes directly. Every field goes through a `models` function.

## Design

### The document

| Section | Shape | Note |
|---|---|---|
| `rooms` | `{id: room}` | `name`, `area_id`, `order` |
| `bookcases` | `{id: bookcase}` | `room_id`, `name`, `note`, `order` |
| `shelves` | `{id: shelf}` | `bookcase_id`, `name`, `order` |
| `books` | `{id: book}` | `models.BOOK_FIELDS`, `cover`, `wishlist`, `lookup_tries`, time stamps |
| `copies` | `{id: copy}` | `book_id` and `models.COPY_FIELDS` |
| `reading` | `{person_id: {book_id: row}}` | `models.READING_FIELDS` and `updated_at` |
| `loans` | `{id: loan}` | `direction`, `book_id`, `copy_id`, `party`, dates, `hk_task_id` |
| `people` | `{person_id: settings}` | `models.PERSON_FIELDS` |
| `todo_orphans` | `[{entity_id, uid}]` | To-do items that the wishlist sync must remove |

`models.normalize_state` runs on every load and in the storage migration hook. It gives
each section its type, so a section that a later version adds needs no migration. It also
gives each book a whole `lookup_tries` count of 0 or more.

### Model functions

- `models.build_book`, `models.build_copy`, `models.build_loan` and the location builders
  check each field and return a new dict. They never change an argument and never read a
  clock: the store passes `now` and `today`.
- A bad value raises `models.LibraryError` with a key and placeholders. The key is in
  `strings.json` `exceptions`.
- An ISBN goes through `isbn.normalize`. The book stores both forms when 1 converts to the
  other ([scan-and-isbn](scan-and-isbn.md)).
- `models.fill_from_draft` writes only the empty `models.DRAFT_FIELDS` of a book, so an
  edit by a user stays when Open Library fills the book.
- `models.title_key` folds a title and its first author for a match with no ISBN.

### The write path

Each method ends in `_commit`: save, add 1 to `revision`, fire the events, call each
listener. A listener that fails is logged and the others still run. The listeners are the
coordinator, the `subscribe` websocket command, the wishlist sync and the loan sync.

### Rules

- **Duplicates.** `add_book` returns the stored book with `existing: true` when the
  ISBN-13 matches. A second copy is a separate call.
- **Locations.** A room with bookcases, a bookcase with shelves and a shelf with copies
  fail to delete with a localized error, unless `force: true`. With `force`, each child
  is removed and each copy moves to no shelf.
- **Book delete.** Deleting a book deletes its copies, reading rows and loans, and the
  cover file. Its wishlist to-do item goes to `todo_orphans`.
- **Reading.** `set_reading` with status `none` removes the row. A borrowed book sets the
  status of the person to `reading` if it is `want` or absent.
- **Loans.** A copy has at most 1 open loan. A lent copy keeps its shelf.
- **Overdue.** `fire_overdue` marks each loan that passed its due date with
  `overdue_fired`, so `loan_overdue` fires once for each due date.
- **Wishlist.** A new copy of a book that has a wishlist entry and no copy clears the
  entry (`models.copy_clears_wishlist`), as `got_wishlist_book` does. The to-do item
  goes to `todo_orphans`, and `copy_added` fires before `wishlist_removed`.
- **Import.** `commit_import` merges the result of a CSV import into the current
  document and fires only `import_completed` ([csv-import-export](csv-import-export.md#steps)).
- **Bookkeeping.** `set_lookup_tries` and `set_loan_task` save a field that only a queue
  or a sync reads, and fire no event.
- **Currency.** The currency is an option of the config entry, not a field of the
  document. `async_settings_updated` fires `settings_updated` and tells the listeners,
  so the clients read it again.

## Trade-offs

- **Plain dicts** over **model classes**: the document is the storage format and the
  reply format, with no conversion layer. The cost is that each shape is pinned by tests
  (`tests/unit/test_shapes.py`), not by a type.
- **Save before the events** over **events first**: an automation that reads the library
  on an event sees the change.
- **1 revision number** over **a change log**: a client reads the whole state again after
  each change. That is simple and consistent at the design size.

## One-way doors

- The storage key, the section names and the field names of each record.
- The enum values: `models.FORMATS`, `models.CONDITIONS`, `models.STATUSES`,
  `models.DIRECTIONS` and `models.COVER_KINDS`.
- Dates as `YYYY-MM-DD` and time stamps as aware ISO 8601.
