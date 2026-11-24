import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/tab-index.ts';
import { bookId, fakeHass, fixture, flush } from './fake-hass.js';

// Every delete, remove and import of the tab asks first, in 1 dialog.

let el;
let host;

async function mount(path, opts = {}) {
  const fake = fakeHass(opts);
  el = document.createElement('home-keeper-library-tab');
  host = {
    apiVersion: 1,
    navigate: vi.fn((p) => {
      el.route = { path: p };
    }),
    taskLink: vi.fn((id) => `/home-keeper/tasks/${id}`),
    applianceLink: (id) => `/home-keeper/appliances/${id}`,
    showToast: vi.fn(),
  };
  el.host = host;
  el.route = { path };
  document.body.appendChild(el);
  el.hass = fake.hass;
  await flush();
  return fake;
}

const $ = (sel) => el.shadowRoot.querySelector(sel);
const ask = () => ({
  title: $('.hkl-confirm h2')?.textContent,
  body: $('.hkl-confirm p')?.textContent,
  ok: $('[data-k="confirm-ok"]')?.textContent,
});
const press = (k) =>
  ($('.hkl-confirm-scrim') ?? el.shadowRoot.activeElement).dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));

afterEach(() => {
  el?.remove();
  el = undefined;
});

describe('delete a book', () => {
  it('names the book, counts what goes with it and focuses Cancel', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const book = state.books ? Object.values(state.books).find((b) => b.id === id) : null;
    const fake = await mount(`/books/${id}`);
    $('[data-k="delete-book"]').click();
    const a = ask();
    expect(a.title).toBe('Delete "Dune"?');
    expect(a.ok).toBe('Delete book');
    expect(a.body).toMatch(/^These go with it:\nCopies: \d+\nLoans: \d+\nReading statuses: \d+\nYou cannot undo this\.$/);
    expect(el.shadowRoot.activeElement).toBe($('[data-k="confirm-cancel"]'));
    expect($('[role="alertdialog"]')).not.toBeNull();
    expect(fake.calls('delete_book')).toEqual([]);
    expect(book).toBeDefined();
  });

  it('does nothing on Cancel or Escape', async () => {
    const state = fixture();
    const fake = await mount(`/books/${bookId(state, 'Dune')}`);
    $('[data-k="delete-book"]').focus();
    $('[data-k="delete-book"]').click();
    $('[data-k="confirm-cancel"]').click();
    expect($('.hkl-confirm-scrim')).toBeNull();
    expect(el.shadowRoot.activeElement?.dataset.k).toBe('delete-book');
    $('[data-k="delete-book"]').click();
    press('Escape');
    expect($('.hkl-confirm-scrim')).toBeNull();
    await flush();
    expect(fake.calls('delete_book')).toEqual([]);
    expect(el.shadowRoot.activeElement?.dataset.k).toBe('delete-book');
  });

  it('deletes on confirm, closes, and goes back to the list', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const fake = await mount(`/books/${id}`);
    $('[data-k="delete-book"]').click();
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_book')).toEqual([{ type: 'home_keeper_library/delete_book', book_id: id }]);
    expect($('.hkl-confirm-scrim')).toBeNull();
    expect(host.navigate).toHaveBeenLastCalledWith('/books', { replace: true });
  });

  it('shows the error of a failed delete as a toast and stays on the page', async () => {
    const state = fixture();
    const fake = await mount(`/books/${bookId(state, 'Dune')}`, { replies: { delete_book: () => Promise.reject({ code: 'x', message: 'It failed.' }) } });
    $('[data-k="delete-book"]').click();
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_book')).toHaveLength(1);
    expect(host.showToast).toHaveBeenCalled();
    expect(host.navigate).not.toHaveBeenCalled();
  });
});

describe('the other deletes', () => {
  it('asks before a copy is deleted, and names the book', async () => {
    const state = fixture();
    const fake = await mount(`/books/${bookId(state, 'Dune')}`);
    $('[data-act="delete-copy"]').click();
    expect(ask().title).toBe('Delete copy');
    expect(ask().body).toContain('"Dune"');
    expect(ask().body).toContain('You cannot undo this.');
    expect(ask().ok).toBe('Delete copy');
    expect(fake.calls('delete_copy')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_copy')).toHaveLength(1);
  });

  it('asks before a loan is deleted, and names the book', async () => {
    const fake = await mount('/loans;tab=returned');
    const del = $('[data-act="delete-loan"]');
    expect(del).not.toBeNull();
    del.click();
    expect(ask().title).toBe('Delete loan');
    expect(ask().body).toMatch(/^Delete the loan of ".+" with .+\? The book stays in the library\.\nYou cannot undo this\.$/);
    expect(fake.calls('delete_loan')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_loan')).toHaveLength(1);
  });

  it('counts the shelves of a room and the copies that lose their shelf', async () => {
    const fake = await mount('/shelves');
    $('[data-act="delete-room"]').click();
    const a = ask();
    expect(a.title).toMatch(/^Delete ".+"\?$/);
    expect(a.body).toMatch(/Bookcases: \d+\nShelves: \d+\n\nCopies that then have no shelf: \d+\nYou cannot undo this\.$/);
    expect(a.ok).toBe('Delete room');
    expect(fake.calls('delete_room')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_room')[0]).toMatchObject({ force: true });
    expect(host.navigate).toHaveBeenLastCalledWith('/shelves', { replace: true });
  });

  it('asks before a bookcase and a shelf are deleted', async () => {
    const fake = await mount('/shelves');
    $('[data-act="delete-bookcase"]').click();
    expect(ask().ok).toBe('Delete bookcase');
    expect(ask().body).toContain('Shelves: ');
    $('[data-k="confirm-cancel"]').click();
    $('[data-act="delete-shelf"]').click();
    expect(ask().ok).toBe('Delete shelf');
    expect(ask().body).toContain('You cannot undo this.');
    expect(fake.calls('delete_bookcase')).toEqual([]);
    expect(fake.calls('delete_shelf')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('delete_shelf')[0]).toMatchObject({ force: true });
  });
});

describe('remove and disconnect', () => {
  it('asks before a book leaves the wishlist', async () => {
    const fake = await mount('/wishlist');
    $('[data-act="wish-remove"]').click();
    expect(ask().title).toBe('Remove from wishlist');
    expect(ask().body).toMatch(/^Remove ".+" from the wishlist\? The book stays in the library\.\nYou cannot undo this\.$/);
    expect(ask().ok).toBe('Remove from wishlist');
    expect(fake.calls('remove_from_wishlist')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('remove_from_wishlist')).toHaveLength(1);
    expect(host.showToast).toHaveBeenCalledWith('Removed from the wishlist.');
  });

  it('asks before Open Library is disconnected', async () => {
    const state = fixture();
    state.catalog_accounts = { openlibrary: { connected: true, username: 'alex_reads' } };
    const fake = await mount('/settings', { state });
    $('[data-k="ol-disconnect"]').click();
    expect(ask().ok).toBe('Disconnect');
    expect(fake.calls('disconnect_catalog')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('disconnect_catalog')).toHaveLength(1);
  });
});

describe('import', () => {
  const summary = { dry_run: true, counts: { rows: 3, read: 2, wishlist: 1, existing: 1, new: 2, title_match: 0 }, rows: [], truncated: false };

  async function previewed(replace = false) {
    const fake = await mount('/import', { replies: { import_csv: summary } });
    const input = $('[data-k="im-file"]');
    Object.defineProperty(input, 'files', { value: [new File(['Title,Author\nA,B\n'], 'goodreads_library_export.csv', { type: 'text/csv' })] });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await flush(10);
    if (replace) {
      const box = $('[data-k="im-replace"]');
      box.checked = true;
      box.dispatchEvent(new Event('change', { bubbles: true }));
      await flush(10);
    }
    return fake;
  }

  it('asks with the counts of the preview before the import writes', async () => {
    const fake = await previewed();
    $('[data-k="import-run"]').click();
    const a = ask();
    expect(a.title).toBe('Import 3 rows');
    expect(a.body).toBe('Already in the library: 1\nNew books: 2\nNo ISBN, match by title: 0\nYou cannot undo this.');
    expect(a.ok).toBe('Import 3 rows');
    expect(fake.calls('import_csv').filter((m) => !m.dry_run)).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('import_csv').filter((m) => !m.dry_run)).toHaveLength(1);
  });

  it('says that the import replaces the reading status, if the box is checked', async () => {
    await previewed(true);
    $('[data-k="import-run"]').click();
    expect(ask().body).toContain('The import replaces the reading status that Alex has now.');
  });

  it('closes only the confirmation on Escape, and the import stays open', async () => {
    await previewed();
    $('[data-k="import-run"]').click();
    press('Escape');
    expect($('.hkl-confirm-scrim')).toBeNull();
    expect($('#hkl-import-title')).not.toBeNull();
  });
});

describe('teardown', () => {
  it('removes the dialog when the tab leaves the page', async () => {
    const state = fixture();
    await mount(`/books/${bookId(state, 'Dune')}`);
    $('[data-k="delete-book"]').click();
    expect($('.hkl-confirm-scrim')).not.toBeNull();
    el.remove();
    expect(el.shadowRoot.querySelector('.hkl-confirm-scrim')).toBeNull();
  });
});

describe('replace a custom cover', () => {
  it('asks before the Open Library cover replaces a photo that the user added', async () => {
    const state = fixture();
    const book = Object.values(state.books)[0];
    book.cover = { kind: 'custom', file: 'c.jpg' };
    book.catalogs = { openlibrary: { key: '/works/OL1W', cover_id: 7 } };
    const fake = await mount(`/books/${book.id}`, { state });
    const use = $('[data-k="use-ol"]');
    expect(use).not.toBeNull();
    use.click();
    expect(ask().title).toBe('Replace your cover?');
    expect(ask().ok).toBe('Use Open Library cover');
    expect(fake.calls('set_cover')).toEqual([]);
    $('[data-k="confirm-ok"]').click();
    await flush();
    expect(fake.calls('set_cover')[0]).toMatchObject({ kind: 'openlibrary' });
  });
});
