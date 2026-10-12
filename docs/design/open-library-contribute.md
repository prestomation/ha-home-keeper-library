---
title: Send books to Open Library
summary: How an admin connects an Open Library account, how the library adds a book that Open Library does not have, and how the "Not on Open Library" list is kept.
implements:
  - custom_components/home_keeper_library/openlibrary_contribute.py
  - custom_components/home_keeper_library/openlibrary_account.py
related: [open-library-covers, people-privilege, events-api, frontend-tab-card]
source_hash: c8d5067a3fbe
---

# Send books to Open Library

An admin can send a book that Open Library does not have. The library signs in with the
Archive.org S3 keys of the household account, posts the "Add a book" form of Open
Library, and links the book to the new edition. The `openlibrary` entry of the book
field `catalog_status` keeps the "Not on Open Library" list.

## Goals

- **G1. A write only on a select.** A write to Open Library happens only when an admin
  selects **Send** for 1 book. There is no batch and no automatic write, as the bot rules
  of Open Library ask.
- **G2. Keys stay in the entry.** The S3 keys come in through the options flow and stay
  in the config entry data. No service field, reply, event or diagnostics file holds
  them.
- **G3. Only the selected details leave.** A send has the title, the first author and
  the fields that the admin selects. Private data never leaves.
- **G4. No duplicate on purpose.** The library reads the ISBN again before a send, and an
  edition that Open Library finds stays for the admin to check and link.

## Non-goals

- The JSON import API and the JSON write API of Open Library. Both need a user group
  that Open Library staff give, so a normal account cannot use them.
- The full edit form. It replaces the whole record and can ask for a captcha. The admin
  adds the other details on the website.
- A choice between many works. Open Library shows a page to pick 1, and the send stops.

## Design

### Catalog names

The services, the book fields and the `get_state` key use the word "catalog", so that a
second catalog of books can come later with no rename. Open Library is the only catalog
(`models.CATALOGS`). A book keeps its record in `catalogs.openlibrary` and its status in
`catalog_status.openlibrary`. The services have no `catalog` field yet. A later catalog
adds an optional field with the default `openlibrary`, so a call that works now keeps
working.

### Status of a book

`catalog_status.openlibrary` is absent, `missing` or `skipped`.

- The lookup queue and `add_book` set `missing` through `BookLookup.async_mark_missing`
  when Open Library has no book. A network error sets nothing.
- `skip_catalog` sets `skipped`, or `missing` again with `skip: false`.
- `fill_from_draft` clears it when it writes a record to `catalogs.openlibrary`.
  `LibraryStore.set_catalog_status` keeps it clear on a linked book.
- `models.normalize_catalogs` gives an old book `missing` at load if its lookups used
  all tries and it has no Open Library data.

Each change fires `book_updated` with `catalog_status` in `changed_fields`. The field is
not a CSV column. The tab lists a book with `missing` and no Open Library record in the
**Not on Open Library** filter, for admins only.

### Account

The options flow is a menu: `currency` and `openlibrary`. The `openlibrary` step takes
`access_key` and `secret_key`, logs in once with `OpenLibraryWriter.async_login`, and
writes the 2 keys and the user name to the entry data. A refused login gives
`invalid_auth`, a network error `cannot_connect`. The tab drives the same flow over
the REST flow API, so the keys never go over a service.

`LibraryCoordinator.catalog_accounts` gives `{openlibrary: {connected, username}}`, with
no keys. `project_state` adds it for an admin. `async_check_settings` fires
`settings_updated` with `catalog_accounts` in `changed_fields` when it changes.
`disconnect_catalog` removes the keys.

### Send

`send_to_catalog` runs these steps:

1. Refuse a book with no account (`openlibrary_not_connected`), a linked book
   (`openlibrary_already_linked`) or no author (`openlibrary_needs_author`).
2. If the ISBN goes, forget its miss and read it again. A found edition gives
   `result: existing`.
3. Log in. The `session` cookie is kept only for this send, as an explicit `Cookie`
   header.
4. Read `/search/authors.json`. 1 exact name match gives its key, else `__new__`.
5. Post `/books/add` with no redirect. `parse_add_reply` reads the `Location`:
   `mode=add-work` or `add-book` is `added`, another edition path is `existing`, and
   no edition path is `ambiguous` (`openlibrary_ambiguous`).
6. On `added`, upload the custom cover if the admin selected it. Then read the edition
   and fill the book. If the edition cannot be read yet, the book keeps the key.

A refused login or a 401 or 403 on the form gives `openlibrary_login_failed`. A
network error or a 5xx gives `lookup_unavailable`. A failed cover upload gives
`cover: failed`, not an error, because Open Library replies with a page in both cases:
the writer reads the edition again and checks `covers`.

`link_catalog` takes an edition key or an openlibrary.org URL in `record`, reads the
edition and fills the book. It is also the second step of `existing`. The reply of a
send gives the edition key in `record`.

### HTTP

`OpenLibraryClient.async_post` uses the shared session, the User-Agent, the timeout and
the per-host limit of the reads. It returns the status, the `Location` and the cookies
as the server sent them. The fixture server of the browser tests has the same 3 POST
paths.

## Trade-offs

- **The website form** over **the JSON API**: it works for every account. The cost is a
  contract that Open Library does not document, so a change there can break a send.
- **S3 keys in the entry** over **a password**: the keys can be revoked on Archive.org
  and the JSON login takes them. The cost is 2 fields to paste.
- **A login for each send** over **a stored session**: no cookie to expire or to leak.
  The cost is 1 more request for each send.
- **5 details and a link to the edit page** over **the edit form**: no risk to erase
  data on Open Library. The cost is a second step on the website.
- **Catalog names** over **Open Library names**: a second catalog needs no rename of a
  service, a field or a stored key. The cost is 1 more level in the book fields.

## One-way doors

- The book field `catalog_status`, keyed by catalog name, and its values `missing` and
  `skipped`.
- The entry data keys `openlibrary_access`, `openlibrary_secret` and
  `openlibrary_username`, and the options flow steps `currency` and `openlibrary`.
- The services `send_to_catalog`, `link_catalog`, `skip_catalog` and
  `disconnect_catalog`, with their fields and the reply keys `result`, `record` and
  `cover`.
- The `get_state` key `catalog_accounts`, keyed by catalog name.
