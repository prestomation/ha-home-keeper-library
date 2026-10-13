---
title: Open Library and covers
summary: How the library reads book details from Open Library, retries a failed lookup in the background, and stores, uploads and serves cover files.
implements:
  - custom_components/home_keeper_library/openlibrary.py
  - custom_components/home_keeper_library/openlibrary_client.py
  - custom_components/home_keeper_library/book_lookup.py
  - custom_components/home_keeper_library/covers.py
related: [scan-and-isbn, csv-import-export, store-models, people-privilege]
source_hash: 8e0672d2f71b
---

# Open Library and covers

Open Library is the only source of book details. A pure parser turns its JSON into a
book draft, a small client reads it politely, and a queue fills the books that a scan or
an import saved with no details. Covers are JPEG files next to the storage document.

## Goals

- **G1. A lookup never fails a scan.** A network error saves the book with its ISBN and
  `needs_details: true`, and the queue tries again later.
- **G2. Polite reads.** 1 request a second to each host, a timeout, a descriptive
  User-Agent, and a memory of misses.
- **G3. User edits win.** A lookup fills only the empty fields of a book.
- **G4. Clean files only.** Every stored cover is a JPEG that Pillow wrote, at most
  1200 px, whatever the source.

## Non-goals

- Other catalogs, such as Google Books or a local ISBN database.
- A cover gallery with more than 1 cover for each book.
- Private covers. The cover view serves each signed-in user.

## Design

### Parser and client

`openlibrary.parse_edition` turns the edition document of `/isbn/{isbn}.json`, its work
and its authors into a draft: the fields of `models.DRAFT_FIELDS` and a `catalogs` block
with the `openlibrary` record: the edition key, the work key and the cover id.
`openlibrary.parse_search` and `openlibrary.best_match` read `/search.json` for a book with
no ISBN. `openlibrary.parse_work` turns a work and its authors into a draft with only the
fields that are the same in each edition: no ISBN, publisher, date, pages or language, and
no edition key. A value of the wrong type is ignored.

`OpenLibraryClient` uses the shared aiohttp session of Home Assistant, a timeout of 10
seconds and the User-Agent `const.USER_AGENT` with the repository URL. An async limiter
spaces the requests to each host by 1 second. An ISBN or a search that finds no book is a
miss for 24 hours, in memory. A network error raises `OpenLibraryError`. It is not a miss.
`async_lookup_edition` reads an edition by its key, `async_lookup_work` reads a work by its
key, and `forget_miss` clears the miss of an ISBN. `async_post` is the write path of a send
([open-library-contribute](open-library-contribute.md)).

The base URLs are `const.OPENLIBRARY_URL` and `const.OPENLIBRARY_COVERS_URL`. The
environment variables `HOME_KEEPER_LIBRARY_OPENLIBRARY_URL` and
`HOME_KEEPER_LIBRARY_OPENLIBRARY_COVERS_URL` replace them (`openlibrary_client.openlibrary_urls`).
They are for tests only: `tests/e2e/docker-compose.e2e.yml` sets them to point the
container at a fixture server.

### Title search

`search_catalog` finds the best work for a title and its first author with `best_match`.
It changes nothing. The reply is `status` (`found`, `not_found` or `unavailable`) and
`match` (`openlibrary.search_match`: `title`, `authors`, `first_published` and
`work_key`), with no edition field, because the match is often a different edition. The
title sheet of a scan uses it, and a person confirms the match
([scan-and-isbn](scan-and-isbn.md#title-sheet)). The lookup queue never uses a title
search for a book with an ISBN, because no person checks the match.

### Lookup queue

`BookLookup` holds a queue of book ids and runs 1 worker while the queue has ids. For each
book that still has `needs_details: true`, it reads Open Library by ISBN, else by title
and first author. A draft fills the book with `LibraryStore.fill_book` and the origin
`home_keeper_library`, and then the cover downloads. After a network error the queue
tries again after 1 minute, then after 5 minutes: `const.LOOKUP_MAX_TRIES` (3) tries in
all. A book that Open Library does not have keeps `needs_details: true` for the user to
fill, and `async_mark_missing` gives it the `catalog_status` `openlibrary: missing`.

The book field `lookup_tries` counts the lookups that gave no details, so the limit holds
across a restart. A network error adds 1. A book that Open Library does not have gets the
full count at once, from the queue and from `add_book`. The queue is in memory, so setup
queues again each book that `models.books_to_look_up` names: a book that needs details,
has an ISBN, has no Open Library record and has fewer tries than the limit, oldest first.
`lookup_tries` is bookkeeping of the queue. It fires no event, is not a column of the CSV
export, and is 0 for a new or imported book.

`refresh_book` runs the same find and fill at once, and raises `lookup_unavailable` on a
network error.

### Cover files

A cover file is `<book_id>-<token>.jpg` in `.storage/home_keeper_library_covers/`. The
directory is not below `.storage/home_keeper_library`, because that path is the store
file. The token changes with each new cover. `cover_url` is
`/api/home_keeper_library/cover/<id>?v=<token>`, so a browser never shows an old cover
from its cache.

- **Open Library.** `covers.async_store_openlibrary_cover` downloads the large image of
  the cover id once. A book with a custom cover keeps it, also if the user sets the
  custom cover during the download. `set_cover` with `kind: openlibrary` keeps the custom
  cover until the new file is stored.
- **Upload.** `CoverUploadView` takes a multipart POST with 1 file from an admin user. It
  reads at most 10 MB, reads the type from the first bytes, and accepts JPEG, PNG and
  WebP. `covers.reencode` writes a new JPEG in an executor job, with a limit on the pixel
  count. The reply is a `file_id` in a pending folder. `set_cover` with `kind: custom`
  moves the file onto the book. A pending file that no book takes is deleted after 24
  hours, at setup.
- **Serve.** `CoverView` returns the file of a book to each signed-in user, with a long
  private cache time. An `<img>` element cannot send a token, so the client signs the
  path.
- **Delete.** A new cover or a deleted book releases the old file, and the store deletes
  it in an executor job.
- **Bundle.** A Home Keeper export copies the cover files into its bundle, and an import
  writes each file again with `covers.reencode` ([import-export](import-export.md#files)).

## Trade-offs

- **An in-memory queue that setup fills again** over **a stored queue**: no new section
  in the document, only 1 count on each book. The cost is a scan of the books at setup.
- **Re-encode every image** over **store the upload as is**: a stored file is never an
  unknown format, and the size is small. The cost is a little CPU time in an executor.
- **A miss cache for 24 hours** over **ask each time**: a scan of the same unknown book
  does not repeat the request.

## One-way doors

- The cover URL path `/api/home_keeper_library/cover/{book_id}` and the upload path
  `/api/home_keeper_library/upload`.
- The `catalogs` block of a book, keyed by catalog name. The `openlibrary` record has
  `edition_key`, `work_key` and `cover_id`. The `lookup_isbn` draft has the same block.
- The `search_catalog` fields `title` and `authors`, the reply keys `status` and `match`,
  and the `match` keys.
- The book field `lookup_tries` and the covers directory `home_keeper_library_covers`.
- The cover `kind` values and the file name format.
