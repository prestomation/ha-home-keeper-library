# Changelog

Each change that a user can see is in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `manifest.json` `version`
is the single source of truth (see `RELEASE.md`).

## [Unreleased]

### Changed

- **Home Keeper betas.** The library works with a beta of Home Keeper. It does not
  check the Home Keeper version number now.

### Fixed

- **Black camera after scan.** The camera picture stays on after each scan, so you can
  scan the next book at once.

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
