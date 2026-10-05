---
title: Ideas and open work
summary: The single backlog of Home Keeper Library work that is not built, for maintainers and agents.
---

# Ideas and open work

This file is the only list of work that is not built: bugs, gaps, refactors and ideas.
Nothing here is committed scope. When an item ships, remove it. The design docs in
`docs/design/` describe what is built.

## Known gaps

- **Query of a tab path.** Home Keeper's host drops a `?query` from a tab path. Ask Home
  Keeper to keep it, then the `;key=value` form of the tab filters can go
  (see `docs/design/frontend-tab-card.md`).

## Product ideas

- **QR shelf labels.** Print a QR label for each shelf, built on the QR label work of
  Home Keeper. A scan of the label opens `/home-keeper/library/scan;shelf=<id>`.
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

A JSON export and import of the whole library, as an `export_json` and `import_json`
service pair for the document and the covers. The CSV library format keeps the books,
the copies and the reading of 1 person. A JSON backup keeps every section, every person
and the loans. A new persisted field round-trips through it, or is excluded with a
reason.

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
