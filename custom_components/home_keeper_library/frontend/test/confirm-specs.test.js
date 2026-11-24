import { describe, expect, it } from 'vitest';
import * as specs from '../src/confirm-specs.ts';
import { buildIndex } from '../src/utils.ts';

// The exact words of each confirm dialog, with counts from a small library.

const lib = {
  rooms: [{ id: 'r1', name: 'Study' }],
  bookcases: [
    { id: 'c1', room_id: 'r1', name: 'Oak case' },
    { id: 'c2', room_id: 'r1', name: 'Pine case' },
    { id: 'c3', room_id: 'r2', name: 'Other room case' },
  ],
  shelves: [
    { id: 's1', bookcase_id: 'c1', name: 'Top' },
    { id: 's2', bookcase_id: 'c1', name: 'Bottom' },
    { id: 's3', bookcase_id: 'c2', name: 'Only' },
    { id: 's4', bookcase_id: 'c3', name: 'Elsewhere' },
  ],
  books: [
    { id: 'b1', title: 'Dune', reading: { a: {}, b: {} } },
    { id: 'b2', title: 'Emma', reading: {} },
  ],
  copies: [
    { id: 'k1', book_id: 'b1', shelf_id: 's1', format: 'hardcover' },
    { id: 'k2', book_id: 'b1', shelf_id: 's1', format: 'paperback' },
    { id: 'k3', book_id: 'b2', shelf_id: 's3', format: 'ebook' },
    { id: 'k4', book_id: 'b2', shelf_id: 's4', format: 'paperback' },
  ],
  loans: [
    { id: 'l1', book_id: 'b1', party: 'Priya', returned: null },
    { id: 'l2', book_id: 'b1', party: 'Sam', returned: '2026-01-01' },
    { id: 'l3', book_id: 'b2', party: 'Jo', returned: null },
  ],
  people: [],
};
const idx = buildIndex(lib);
const book = (id) => lib.books.find((b) => b.id === id);
const U = 'You cannot undo this.';

describe('confirm specs', () => {
  it('counts the copies, the loans of any state and the reading statuses of a book', () => {
    expect(specs.deleteBook(lib, idx, book('b1'))).toEqual({
      title: 'Delete "Dune"?',
      body: `These go with it:\nCopies: 2\nLoans: 2\nReading statuses: 2\n${U}`,
      confirmLabel: 'Delete book',
    });
    expect(specs.deleteBook(lib, idx, book('b2')).body).toBe(`These go with it:\nCopies: 2\nLoans: 1\nReading statuses: 0\n${U}`);
  });

  it('names the format and the book of a copy', () => {
    expect(specs.deleteCopy(idx, lib.copies[0])).toEqual({
      title: 'Delete copy',
      body: `Delete the hardcover copy of "Dune"? The book and its reading status stay.\n${U}`,
      confirmLabel: 'Delete copy',
    });
    expect(specs.deleteCopy(idx, { id: 'x', book_id: 'none', shelf_id: null, format: 'other' }).body).toContain('copy of ""');
  });

  it('names the book and the party of a loan', () => {
    expect(specs.deleteLoan(idx, lib.loans[0])).toEqual({
      title: 'Delete loan',
      body: `Delete the loan of "Dune" with Priya? The book stays in the library.\n${U}`,
      confirmLabel: 'Delete loan',
    });
    expect(specs.deleteLoan(idx, { id: 'x', book_id: 'b2' }).body).toContain('with ?');
  });

  it('counts the bookcases, shelves and copies that lose their shelf in a room', () => {
    expect(specs.deleteRoom(lib, idx, lib.rooms[0])).toEqual({
      title: 'Delete "Study"?',
      body: `These go with it:\nBookcases: 2\nShelves: 3\n\nCopies that then have no shelf: 3\n${U}`,
      confirmLabel: 'Delete room',
    });
  });

  it('counts the shelves and the copies that lose their shelf in a bookcase', () => {
    expect(specs.deleteBookcase(lib, idx, lib.bookcases[0])).toEqual({
      title: 'Delete "Oak case"?',
      body: `These go with it:\nShelves: 2\n\nCopies that then have no shelf: 2\n${U}`,
      confirmLabel: 'Delete bookcase',
    });
  });

  it('counts the copies on a shelf', () => {
    expect(specs.deleteShelf(idx, lib.shelves[0])).toEqual({
      title: 'Delete "Top"?',
      body: `Copies that then have no shelf: 2\n${U}`,
      confirmLabel: 'Delete shelf',
    });
    expect(specs.deleteShelf(idx, lib.shelves[1]).body).toBe(`Copies that then have no shelf: 0\n${U}`);
  });

  it('names the book of a wishlist entry', () => {
    expect(specs.removeWish(book('b1'))).toEqual({
      title: 'Remove from wishlist',
      body: `Remove "Dune" from the wishlist? The book stays in the library.\n${U}`,
      confirmLabel: 'Remove from wishlist',
    });
  });

  it('says that a custom cover is deleted', () => {
    expect(specs.replaceCover(book('b1'))).toEqual({
      title: 'Replace your cover?',
      body: `Replace the cover that you added for "Dune" with the Open Library cover? The library deletes your image.\n${U}`,
      confirmLabel: 'Use Open Library cover',
    });
  });

  it('keeps the words of the disconnect and the scan', () => {
    expect(specs.disconnectCatalog()).toEqual({
      title: 'Disconnect Open Library?',
      body: 'The library removes the keys. You cannot send books until you connect again.',
      confirmLabel: 'Disconnect',
    });
    expect(specs.removeScan('9781402894626')).toEqual({
      title: 'Remove this scan?',
      body: `Delete the book with ISBN 9781402894626 and its copy.\n${U}`,
      confirmLabel: 'Remove this scan',
    });
  });

  it('gives the preview counts of an import, and the replace line only if it is on', () => {
    const state = { rowCount: 9, replaceReading: false, summary: { counts: { rows: 3, existing: 1, new: 2, title_match: 4 } } };
    expect(specs.importRows(state, 'Alex')).toEqual({
      title: 'Import 3 rows',
      body: `Already in the library: 1\nNew books: 2\nNo ISBN, match by title: 4\n${U}`,
      confirmLabel: 'Import 3 rows',
    });
    expect(specs.importRows({ ...state, replaceReading: true }, 'Alex').body).toBe(
      `Already in the library: 1\nNew books: 2\nNo ISBN, match by title: 4\n\nThe import replaces the reading status that Alex has now.\n${U}`,
    );
  });

  it('falls back to the row count and to 0 if there is no preview count', () => {
    const state = { rowCount: 1, replaceReading: false, summary: null };
    expect(specs.importRows(state, '')).toEqual({
      title: 'Import 1 row',
      body: `Already in the library: 0\nNew books: 0\nNo ISBN, match by title: 0\n${U}`,
      confirmLabel: 'Import 1 row',
    });
  });
});
