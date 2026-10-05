---
sidebar_position: 1
slug: /intro
title: Introduction
---

# Home Keeper Library

Home Keeper Library is a Home Assistant integration for the books of a household. It
records the rooms and shelves of the home, the books and their copies, the reading status
of each person, the loans and a wishlist.

**Home Keeper Library requires [Home Keeper](https://github.com/prestomation/ha-home-keeper).**
Install and set up Home Keeper first. The library adds a **Library** tab to the Home
Keeper panel.

<!-- screenshot: books-desktop.png -->

## Features

- **Scan.** Fill a shelf with the camera of a phone. Details and covers come from Open
  Library.
- **Shelves.** Each copy has a room, a bookcase and a shelf, so a search finds the book.
- **Reading.** Each person has a reading status, a rating, notes and a yearly goal.
- **Loans.** Lent and borrowed books get a task in Home Keeper on the due date.
- **Wishlist.** The books to buy go to a to-do list of the person.
- **Import.** Goodreads and StoryGraph CSV files bring a reading history in.
- **Card and entities.** Every user gets a dashboard card, sensors and a To read list.

## Next steps

- Read the [overview](/docs/guide/overview), then [Installation](/docs/guide/installation).
- To use the library from an automation or another integration, read the
  [Developer Guide](/developer/integrating).
