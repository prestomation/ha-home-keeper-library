---
title: Security model
summary: The access of admins and of non-admin users to each surface of Home Keeper Library. The fields that each reply hides from a non-admin user.
---

# Security model

In Home Keeper Library, an admin manages the library. Each signed-in user keeps the
reading of their own person. Admins manage the locations, the books and their copies, the
loans and the wishlist. A non-admin user sets the reading status, the rating and the
notes of their own person, and reads what the projections allow.

## The rule

A Home Assistant instance usually has 1 or 2 admins and a few users, such as a partner,
children, a housemate or a guest account on a wall tablet. The library follows the rule
of Home Assistant itself: a user who is not an admin cannot change the setup of the home.
For the library, a guest account must not:

- delete books or move copies;
- read the price and the value of a copy, or the names of the people who borrowed a book;
- read the private notes of another person;
- read the reading status of a person who does not share it.

The admin UI is the Library tab of the Home Keeper panel, and that panel is admin-only.
Every user can use the card and the entities. Every user can also call the services that
this page lists as open.

## The caller

The library finds the person of a caller from the Home Assistant user: the `person`
whose user is the caller. A user with no person can read the library. An operation that
acts for a person gives that user the error `no_person`. The library trusts a call with
no user, as Home Assistant does. An automation makes that kind of call.

## Services

| Service | Access |
|---|---|
| `add_room`, `update_room`, `delete_room` | Admin |
| `add_bookcase`, `update_bookcase`, `delete_bookcase` | Admin |
| `add_shelf`, `update_shelf`, `delete_shelf` | Admin |
| `lookup_isbn`, `add_book`, `update_book`, `delete_book`, `refresh_book` | Admin |
| `scan_isbn`, `add_copy`, `update_copy`, `move_copy`, `delete_copy`, `set_cover` | Admin |
| `lend_book`, `borrow_book`, `return_loan`, `update_loan`, `delete_loan` | Admin |
| `add_to_wishlist`, `update_wishlist`, `remove_from_wishlist`, `got_wishlist_book` | Admin |
| `set_settings`, `import_csv`, `export_csv` | Admin |
| `set_reading` | Open, for the caller's own person. An admin can name any person. |
| `set_person_settings` | Open, for the caller's own person, with no `wishlist_todo`. An admin can set each field of any person. |
| `list_books`, `get_book`, `list_locations`, `list_loans`, `list_people` | Open, projected |

`wishlist_todo` is admin-only because it sends book titles to a to-do list. Import and
export are admin-only because they read or write the whole library.

## Websocket commands

| Command | Access |
|---|---|
| `home_keeper_library/get_state` | Open, projected |
| `home_keeper_library/subscribe` | Open. It sends only a revision number. |
| `home_keeper_library/list_todo_entities` | Admin |
| `home_keeper_library/<service>` | The same access as the service of the same name |

Each command with the name of a service runs the same code and the same check as the
service. A gate on the command alone would be no gate, because a user can call the
service directly.

## HTTP views

| Method and path | Access |
|---|---|
| `GET /home_keeper_library_static/...` | Public. It holds only the built bundles. |
| `GET /api/home_keeper_library/cover/{book_id}` | Each signed-in user. Covers are not private. |
| `POST /api/home_keeper_library/upload` | Admin, as a real user. At most 10 MB. JPEG, PNG or WebP. |

Home Assistant serves a static path before authentication, so the static path holds only
`frontend/dist/`. The upload view reads the image type from the first bytes of the file,
and stores only a JPEG that it writes again. A signed URL is accepted only for `GET` and
`HEAD`, so a signed URL cannot upload.

## Projections

An admin reads the full library. For a non-admin user, every reply goes through the
projection:

| Record | Hidden from a non-admin user |
|---|---|
| Copy | `price`, `value`, `acquired_from` |
| Loan | `party` |
| Reading row of another person | The whole row if that person has `share_reading: false`, else `private_notes` |
| Settings of another person | `wishlist_todo` |
| Wishlist entry of another person | `todo_entity`, `todo_uid` |

The book records, the shared notes and the covers are open to every user. Only an admin
can download the diagnostics. The download redacts the loan
parties, the notes and `acquired_from`.

## Entities

Home Assistant shows each entity to each user, and lets each user call the `todo`
services on each to-do list. So the per-person entities apply the privacy rules of the
library:

- The To read list of a person takes a change only from the user of that person or
  from an admin user. A call with no user, such as an automation, is trusted. A change
  from another user fails with the error `todo_not_allowed`.
- If a person has `share_reading: false`, the 3 entities of that person are unavailable:
  the To read list and the sensors that show the books read this year and the books that
  the person reads now. The list gives
  no items, also over the `todo/item/list` websocket command. They come back when the
  person shares the reading again.

The library sensors show only counts, with no title and no person.

## Events

The payload of a bus event holds the book title, the person id and, for a loan, the party. Home
Assistant lets only an admin subscribe to these events over the websocket API. An
automation that copies an event to a notification sends that data to the place that the
automation names.

## Add a surface

Each PR lists the surfaces that it adds or changes in its **Security** section. The
rules that decide if an operation is admin-only or open are in
[the architecture rules](../.amazonq/rules/architecture.md#how-to-decide).
