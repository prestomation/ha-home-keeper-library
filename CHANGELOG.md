# Changelog

Each change that a user can see is in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `manifest.json` `version`
is the single source of truth (see `RELEASE.md`).

## [Unreleased]

### Changed

- **Home Keeper betas.** The library works with a beta of Home Keeper. It does not
  check the Home Keeper version number now.
- **Camera on HTTP pages.** On an `http://` address, the scan says at once that the
  camera needs HTTPS, and it does not start the camera. **Enter ISBN** still works.

### Fixed

- **Black camera after scan.** The camera picture stays on after each scan, so you can
  scan the next book at once.
- **Camera after Back.** If you leave the scan step while the camera starts, the camera
  stops.
- **Changed ISBN.** When you change the ISBN of a book, its ISBN-10 changes too.
- **Custom covers.** A custom cover stays if the Open Library cover cannot be read. An
  Open Library cover does not replace a cover that you upload during its download.
- **Library CSV import.** A row with a bad copy value adds no book. A book with 2 or
  more copies counts 1 time in the reading totals.
- **ISBN with other digits.** An ISBN cell with a digit such as "²" does not stop the
  import. That row gets no ISBN.
- **Card updates after a reload.** The dashboard card shows changes again after a
  reload of the integration.
- **Wishlist privacy.** A user who is not an admin does not see the to-do list of the
  wishlist of another person.
- **Text after an error.** If a dialog or the notes editor cannot save, it keeps the
  text that you typed. A change that fails shows the stored value again.
- **Import preview.** If you change the import settings quickly, the preview shows the
  result of the last settings.
- **Home Keeper link.** A Home Keeper that refuses a field of the library no longer stops
  the setup of the library.

## [0.2.0] - 2026-10-05

### Added

- **[ISBN barcode scan](https://prestomation.github.io/ha-home-keeper-library/docs/guide/scan-books).** Scan the ISBN barcode of each book with a
  phone. The book goes on the selected shelf with its details and cover from Open
  Library. Enter the ISBN by hand for a book with no barcode.
- **[Rooms and shelves](https://prestomation.github.io/ha-home-keeper-library/docs/guide/rooms-and-shelves).** Record the rooms, bookcases and
  shelves of the home. Each copy shows its shelf.
- **[Book search and filters](https://prestomation.github.io/ha-home-keeper-library/docs/guide/books).** Find a book by its title, author, ISBN,
  series or notes. Filter the library by room, shelf, reader, subject and reading status.
- **[Reading status and notes](https://prestomation.github.io/ha-home-keeper-library/docs/guide/book-detail).** Each person keeps a reading status, a
  rating, the page, the dates and private notes for each book. Each copy keeps its
  format, condition, price and value.
- **[Lent and borrowed books](https://prestomation.github.io/ha-home-keeper-library/docs/guide/loans).** Record the books that are lent out or
  borrowed. Each due date gets a Home Keeper task, and the completed task returns the book.
- **[Per-person wishlist](https://prestomation.github.io/ha-home-keeper-library/docs/guide/wishlist).** Each person has a wishlist. The books to buy go
  to a to-do list of that person.
- **[Goodreads and StoryGraph import](https://prestomation.github.io/ha-home-keeper-library/docs/guide/import-export).** Bring a reading history in
  from a Goodreads or StoryGraph CSV file, with a preview first. Export the library to a
  CSV file that both read.
- **[Dashboard card](https://prestomation.github.io/ha-home-keeper-library/docs/guide/dashboard-card).** Each user gets a dashboard card with their
  reading and their yearly goal. The card also shows the books to read next and the
  household activity.
- **[Per-person entities](https://prestomation.github.io/ha-home-keeper-library/docs/guide/services).** Each person gets a To read list and sensors for
  the books read this year and the books in progress.
- **[Services and events](https://prestomation.github.io/ha-home-keeper-library/docs/guide/services).** Each operation of the Library tab is a service
  for automations. Each change fires an event.
- **[People and privacy](https://prestomation.github.io/ha-home-keeper-library/docs/guide/people-and-privacy).** Prices, borrower names and private
  notes stay with the admins. Each person can stop sharing their reading status.
