# People and privacy

The library uses the people of Home Assistant. Each reading status, rating and private
note belongs to 1 Home Assistant `person`. A user of Home Assistant is linked to a person
in **Settings → People**. The library acts for the person of the user who signs in.

## What each user can do

| Operation | Admin | Other user |
|---|---|---|
| Manage rooms, shelves, books, copies, covers, loans and the wishlist | Yes | No |
| Scan, import and export | Yes | No |
| Set the reading status, rating, page and notes of their own person | Yes | Yes |
| Set the reading status of another person | Yes | No |
| Turn **Share reading** on or off, and set the yearly goal, for their own person | Yes | Yes |
| Select the wishlist to-do list of a person | Yes | No |
| Read the books, the shelves and the covers | Yes | Yes |

The Library tab is in the Home Keeper panel, which only admins can open. Other users use
the [dashboard card](../views/dashboard-card.md), the entities and the services. A user
with no linked person can read the library, and cannot set a reading status.

## What other users read

Admins read the whole library. Other users do not read:

- the price, the value and the source of a copy;
- the name of the person who borrowed or lent a book;
- the private notes of another person;
- the reading status of a person who turned **Share reading** off.

Shared notes are for the whole household. Private notes are for 1 person and the admins.

## People settings

An admin sets these in the **Settings** page of the Library tab, for each person:

- **Share reading**: other users see the reading status of the person, with no private
  notes. It is on by default.
- **Yearly goal**: the number of books to read this year. The card and a sensor show it.
- **Wishlist to-do list**: the to-do list that gets the wishlist books with **Buy** set
  ([Wishlist](../library/wishlist.md)).

<!-- screenshot: settings-desktop.png -->

The **Settings** page also shows the currency, and has the
[export](../library/import-export.md) of the library.

## Entities

Each person gets a **To read** to-do list and 2 sensors: **books read this year** and
**reading now**. Home Assistant shows entities to every user, so these entities show the
reading of a person also when **Share reading** is off. Every user can add an item to the
**To read** list of each person.
