---
title: Open Library and covers
summary: How the library reads book details from Open Library, retries a failed lookup in the background, and stores, uploads and serves cover files.
implements:
  - custom_components/home_keeper_library/openlibrary.py
  - custom_components/home_keeper_library/openlibrary_client.py
  - custom_components/home_keeper_library/book_lookup.py
  - custom_components/home_keeper_library/covers.py
related: [scan-and-isbn, csv-import-export, store-models, people-privilege]
source_hash: 73fcb977177f
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
and its authors into a draft: the fields of `models.DRAFT_FIELDS` and an `openlibrary`
block with the edition key, the work key and the cover id. `openlibrary.parse_search`
and `openlibrary.best_match` read `/search.json` for a book with no ISBN. A value of the
wrong type is ignored.

`OpenLibraryClient` uses the shared aiohttp session of Home Assistant, a timeout of 10
seconds and the User-Agent `const.USER_AGENT` with the repository URL. An async limiter
spaces the requests to each host by 1 second. An ISBN or a search that finds no book is a
miss for 24 hours, in memory. A network error raises `OpenLibraryError`. It is not a miss.

### Lookup queue

`BookLookup` holds a queue of book ids and runs 1 worker while the queue has ids. For each
book that still has `needs_details: true`, it reads Open Library by ISBN, else by title
and first author. A draft fills the book with `LibraryStore.fill_book` and the origin
`home_keeper_library`, and then the cover downloads. After a network error the queue
tries again after 1 minute, then after 5 minutes: 3 tries in all. A book that Open
Library does not have keeps `needs_details: true` for the user to fill.

`refresh_book` runs the same find and fill at once, and raises `lookup_unavailable` on a
network error.

### Cover files

A cover file is `<book_id>-<token>.jpg` in `.storage/home_keeper_library/covers/`. The
token changes with each new cover. `cover_url` is
`/api/home_keeper_library/cover/<id>?v=<token>`, so a browser never shows an old cover
from its cache.

- **Open Library.** `covers.async_store_openlibrary_cover` downloads the large image of
  the cover id once. A book with a custom cover keeps it.
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

## Trade-offs

- **An in-memory queue** over **a stored queue**: no new section in the document. A
  restart drops the queue ([IDEAS.md](../../IDEAS.md#lookup-queue-after-a-restart)).
- **Re-encode every image** over **store the upload as is**: a stored file is never an
  unknown format, and the size is small. The cost is a little CPU time in an executor.
- **A miss cache for 24 hours** over **ask each time**: a scan of the same unknown book
  does not repeat the request.

## One-way doors

- The cover URL path `/api/home_keeper_library/cover/{book_id}` and the upload path
  `/api/home_keeper_library/upload`.
- The `openlibrary` block of a book: `edition_key`, `work_key`, `cover_id`.
- The cover `kind` values and the file name format.
