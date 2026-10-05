---
title: CSV import and export
summary: How the library reads Goodreads, StoryGraph and library CSV files with a dry run first, how it matches rows to books, and how it writes an export.
implements:
  - custom_components/home_keeper_library/csv_io.py
  - custom_components/home_keeper_library/frontend/src/tab-import.ts
related: [store-models, open-library-covers, events-api]
source_hash: 308acf3d56d6
---

# CSV import and export

An admin moves a reading history into the library from a Goodreads or StoryGraph export,
or moves a library from 1 Home Assistant to another with the library format. The import
runs as a dry run first, so the admin sees the counts before a write.

## Goals

- **G1. Preview before write.** A dry run is the same pure call as the import, with the
  result thrown away. The preview and the import cannot disagree.
- **G2. No second book.** A row matches a stored book by ISBN-13, then ISBN-10, then
  title and first author.
- **G3. Keep what is there.** A reading row that the person has now stays, unless the
  admin asks to replace it. A book with a copy gets no second copy from a Goodreads or
  StoryGraph row.
- **G4. Round trips.** `parse(write(rows))` gives the rows back, for each format.

## Non-goals

- A sync with Goodreads or StoryGraph. The import reads a file once.
- Open Library calls inside the import. New books that need details go to the lookup
  queue after the write.
- A JSON export of the whole document ([IDEAS.md](../../IDEAS.md#json-backup)).

## Design

### Steps

1. `csv_io.parse` reads the text into import rows, with the same keys for each source.
   `goodreads` needs the `Title` column, and so does `storygraph`. A file of more than
   5 MB is refused with `csv_too_large`.
2. `csv_io.apply_import` plans the import on a snapshot of the document in an executor
   job. It returns the planned document, the counts, 1 result for each row and the ids of
   the new books that need details.
3. With `dry_run: true` the service returns the counts and the first 200 row results.
   Else `LibraryStore.commit_import` writes the plan and fires `import_completed`, and
   the new books go to the lookup queue.

**An import never replaces the document.** Other changes can come in while the plan
runs. `models.merge_changes` compares the snapshot with the plan, and writes into the
current document only the records and the fields that the plan changed. The merge and
the save have no `await` between them, so no other change comes in the middle.

- A change to another field of the same record stays.
- A record that a user deleted while the plan ran stays deleted.
- A planned copy or reading row of a deleted book is dropped. A planned copy on a
  deleted shelf goes to no shelf.
- A new book starts with `lookup_tries` 0
  ([open-library-covers](open-library-covers.md#lookup-queue)).

### Goodreads mapping

- An ISBN cell such as `="0441478123"` loses the `=` and the quotes.
- `Exclusive Shelf` gives the status: `read`, `currently-reading` gives `reading`,
  `to-read` gives `want`, `did-not-finish` gives `dnf`.
- A `to-read` row with `Owned Copies` 0 goes on the wishlist of the person, with
  `buy: false`, and gets no reading row.
- `Owned Copies` above 0 adds 1 copy on the chosen shelf, if the book has none. The
  format comes from `Binding`: hardcover, paperback, ebook, audiobook, else other.
- `My Rating` above 0 gives the rating. `Date Read` gives `finished`. `Read Count` gives
  `read_count`.
- `Bookshelves` other than the exclusive shelf become tags.
- With `import_notes`, `My Review` and `Private Notes` become the private notes.

### StoryGraph mapping

`Read Status` maps the same way, with `did-not-finish` as `dnf`. `Star Rating` can be a
decimal and rounds to the nearest whole star from 1 to 5. `Owned?` adds a copy, and
`Format` gives its format. `Tags` become tags, and `Review` becomes the private notes.

### Library format

The library format has every book field, the copy fields, the location as a path of room,
bookcase and shelf names, and the reading row of the chosen person. A row puts its copy
on the shelf of its path when that shelf exists, else on the chosen shelf. A copy id that
is already stored is not added again.

### Export

`csv_io.export` writes the Goodreads header, which Goodreads and StoryGraph read, or the
library format. With a person, the file has the reading status of that person. With no
person, it has all books and no reading status. `csv_io.export_filename` names the file
with the format and the date.

### Tab

`tab-import.ts` is the Import dialog at `/import`: source, person, shelf for new books,
file, preview table and counts, then **Import**. It reads the file in the browser and
sends the text to `import_csv`.

## Trade-offs

- **1 merge of the plan** over **1 store call for each row**: 1 save and 1 event for
  an import of thousands of rows. The cost is the merge, which compares 3 documents.
- **Text in a service field** over **a file upload**: an automation can call the import.
  The limit is 5 MB.
- **Match by title and first author** over **ISBN only**: many Goodreads rows have no
  ISBN. A wrong match is possible for 2 books with the same title by 1 author.

## One-way doors

- The source names `goodreads`, `storygraph` and `library`, and the export formats
  `goodreads` and `library`.
- The column names of the library format.
- The count keys of the import reply (`csv_io.COUNT_KEYS`).
