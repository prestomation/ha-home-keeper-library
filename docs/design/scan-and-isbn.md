---
title: Scan and ISBN
summary: The ISBN rules, the camera scanner with its lazy decoder chunk, the scan flow of the tab, and the scan_isbn service with its duplicate choices.
implements:
  - custom_components/home_keeper_library/isbn.py
  - custom_components/home_keeper_library/frontend/src/scanner.ts
  - custom_components/home_keeper_library/frontend/src/zxing-decoder.ts
  - custom_components/home_keeper_library/frontend/src/tab-scan.ts
related: [open-library-covers, store-models, frontend-tab-card, loans-home-keeper]
source_hash: 0465cac972ed
---

# Scan and ISBN

An admin fills a shelf with a phone: open the scan flow for the shelf, point the camera at
the barcode of each book, and read the result of each scan. A book with no barcode gets
its ISBN by hand. Each scan calls the `scan_isbn` service.

## Goals

- **G1. One ISBN for one book.** Every ISBN is cleaned, checked and stored as ISBN-13,
  with the ISBN-10 when 1 converts, so 2 forms of 1 ISBN find the same book.
- **G2. A shelf in 1 pass.** A scan adds the copy to the chosen shelf at once, and the
  next shelf is 1 step away.
- **G3. Duplicates are a choice.** A book that is already in the library asks for Move
  here, Add 2nd copy or Skip.
- **G4. A small bundle.** The barcode decoder loads only on a browser that needs it.

## Non-goals

- Barcodes that are not ISBNs, such as the price add-on of a book or a store label.
- A photo of a whole shelf. That is in [IDEAS.md](../../IDEAS.md#shelf-photo).
- Scans from the card. Scanning changes the catalog, so it is in the admin tab.

## Design

### ISBN rules

`isbn.normalize` cleans the input to digits (and `X` for the check character of an
ISBN-10), checks the check digit, and returns the ISBN-13 and the ISBN-10. An ISBN-10
converts to the ISBN-13 with the `978` prefix. Only a `978` ISBN-13 converts back. A bad
value raises `IsbnError`, which a service turns into `invalid_isbn`.
`isbn.is_isbn_barcode` accepts an EAN-13 with the `978` or `979` prefix. `utils.ts` has
the same rules for the tab, so the tab can refuse a bad code before a call.

### Scanner

`scanner.ts` opens the rear camera with `getUserMedia`. It uses the native
`BarcodeDetector` when the browser supports EAN-13, EAN-8 or UPC-A. Else it imports
`zxing-decoder.ts` with a dynamic import, so Rollup puts `@zxing/library` in a separate
chunk. The decoder imports only the UPC and EAN readers.

- On a page that is not a secure context (`cameraNeedsHttps`), the setup step shows the
  HTTPS message under the camera method and turns off **Start**. **Enter ISBN** still
  starts. If the camera step opens from its URL, it shows the same message and offers
  **Enter ISBN**.
- If the browser refuses the camera, the tab shows the reason and offers **Enter ISBN**.
- The torch button shows when the camera track has a torch.
- The same code is ignored for 3 seconds (`makeCodeGate`), so 1 book is 1 scan.
- The camera runs only on the camera step. Home Keeper redraws its panel when the data
  changes, and that moves the tab out of the page and back in. So the tab stops the
  camera only when it is still out of the page after the redraw, and it starts the
  camera again when it comes back.

### Scan flow

The route is `/scan`, with `;shelf=<id>` to preselect the shelf and `;mode=borrowed` for
borrowed books ([frontend-tab-card](frontend-tab-card.md#the-tab)). The steps are setup
(room, shelf, method), camera or manual entry, and the summary. Each result row shows
Added, Already in a place, Moved here, Skipped or No match in Open Library. A row also
shows From wishlist when the reply has `from_wishlist: true`. **Next shelf** goes to the
next shelf in display order. The summary can set the status Read for the caller on each
book that the session added or moved.

In borrowed mode each scan calls `borrow_book` with the ISBN, the lender and the due date
of the session, and adds no copy ([loans-home-keeper](loans-home-keeper.md)).

### The `scan_isbn` service

1. Check the shelf. A missing `shelf_id` means no shelf.
2. Normalize the ISBN.
3. If no book has the ISBN-13, add the book through the Open Library lookup and add a copy.
   The result is `added`, or `not_found` if Open Library has no book. A network error
   saves the book with `needs_details: true` and queues it
   ([open-library-covers](open-library-covers.md)).
4. If the book has no copy, add a copy: `added`.
5. If the book has copies, `on_duplicate` decides: `ask` returns `duplicate` with the
   copies and their locations, `skip` returns `skipped`, `move` moves a copy from
   another shelf and returns `moved`, and `add_copy` adds a copy.

The reply has `from_wishlist: true` when the new copy took its book off the wishlist
([store-models](store-models.md#rules)). The service then runs the wishlist sync, so the
to-do item goes at once.

## Trade-offs

- **A service call for each scan** over **a batch at the end**: each result shows at once,
  and an automation can use the same service. The cost is 1 round trip for each book.
- **The native detector first** over **zxing always**: the native path is faster and
  costs no download. The cost is 2 code paths to test.
- **Ask on a duplicate** over **add a copy by default**: a scan of a shelf that is already
  in the library is the most common duplicate, and it means a move.

## One-way doors

- The `scan_isbn` fields (`isbn`, `shelf_id`, `format`, `on_duplicate`), the result
  values `added`, `duplicate`, `moved`, `skipped` and `not_found`, and the reply key
  `from_wishlist`.
- The scan URL and its parameters `shelf`, `mode` and `step`.
- ISBN-13 as the key of the duplicate check.
