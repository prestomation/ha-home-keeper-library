---
title: Ideas and open work
summary: The single backlog of Home Keeper Library work that is not built, for maintainers and agents.
---

# Ideas and open work

This file is the only list of work that is not built: bugs, gaps, refactors and ideas.
Nothing here is committed scope. When an item ships, remove it. The design docs in
`docs/design/` describe what is built.

## Known gaps

- **Cover images in the tab and the card.** The cover view requires a token, and the
  frontend puts `cover_url` in an `<img>` as is. Sign the path with `auth/sign_path`, or
  read the image with `fetchWithAuth` (see `docs/design/frontend-tab-card.md`).
- **Scan of a wishlist book.** `scan_isbn` adds a copy to a book on the wishlist, and the
  wishlist entry stays. The wishlist view says that a scanned book leaves the wishlist.
  Clear the entry in the scan, as `got_wishlist_book` does, or change the hint.
- **Open per-person entities.** The To read list and the per-person sensors are
  ordinary entities, which every user can read and use.

### Private per-person entities

The To read list of a person lets any user add a book or change the `want` status of
that person, and the sensors show the reading of a person who turned `share_reading`
off. Options: an option to turn the per-person entities off, entities only for the
people who share, or a check of the caller in the to-do write methods
(see `docs/design/entities.md`).

### Events for every change

These changes fire no event: an edit of a copy that keeps its shelf, `update_loan`,
`delete_loan`, a rating, page or notes change that keeps the status,
`set_person_settings` and `set_settings`. Add `copy_updated`, `loan_updated`,
`loan_removed` and `reading_updated` events, or extend the existing payloads
(see `docs/design/events-api.md`).

### Lookup queue after a restart

The lookup queue is in memory. A book that waits for a retry when Home Assistant stops
keeps `needs_details: true`, and no lookup starts at the next setup. Queue each book with
`needs_details: true` and an ISBN at setup, or store the queue
(see `docs/design/open-library-covers.md`).

### Import and concurrent changes

`import_csv` works on a copy of the document in an executor job, and then replaces the
document. A change from another session while the import runs is lost. Apply the import
result as a merge, or hold a store lock for the whole import
(see `docs/design/csv-import-export.md`).

## Product ideas

- **QR shelf labels.** Print a QR label for each shelf, with the Home Keeper QR label
  work. A scan of the label opens `/home-keeper/library/scan?shelf=<id>`.
- **Series gaps.** List the numbers that are missing from each series that the library
  holds, and put them on the wishlist in 1 step.
- **Reading log for children.** Minutes or pages for each day, a streak, and a goal for a
  person who is a child.
- **Insurance value report.** The total value and price of the copies for each room,
  with a CSV or PDF download for an insurance claim. Admin-only.
- **Phone walkthrough tour.** A second walkthrough capture at phone width: scan a shelf
  with **Enter ISBN**, read the summary, set a status in the card.

### Shelf photo

Take a photo of a shelf, and let the AI task service of Home Assistant read the spines.
Show each title as a scan result row with the same duplicate choices. The photo is never
stored.

### JSON backup

A `export_json` and `import_json` service pair for the whole document, with the covers.
The CSV library format keeps the books, the copies and 1 person's reading. A JSON backup
keeps every section, every person and the loans. A new persisted field round-trips
through it, or is excluded with a reason.

## Testing and CI

### Upgrade test tier

Boot a frozen older Home Assistant and Home Keeper on a seeded config dir, then the
current ones on the same dir, and check that the library, the tab and the loan tasks
load. Add a job in `ha-beta.yml` for it.

- **Browser test of the scan with a camera.** The e2e tier uses **Enter ISBN**. A fake
  video stream with a barcode would cover the decoder chunk.

## Docs and quality

### Quality scale ledger

The integration uses the practices of the Platinum quality scale, and `manifest.json`
declares no tier. Add `quality_scale` and a `quality_scale.yaml` ledger with each rule
and its state.
