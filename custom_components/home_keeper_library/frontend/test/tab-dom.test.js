import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/tab-index.ts';
import { ALEX, bookId, fakeHass, fixture, flush } from './fake-hass.js';

let el;
let host;

async function mount(path = '/books', opts = {}) {
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
const $$ = (sel) => [...el.shadowRoot.querySelectorAll(sel)];
const text = () => el.shadowRoot.getElementById('main').textContent.replace(/\s+/g, ' ');

function change(node, value) {
  if (node.type === 'checkbox') node.checked = value;
  else node.value = value;
  node.dispatchEvent(new Event('change', { bubbles: true }));
}

afterEach(() => {
  el?.remove();
  el = undefined;
  vi.useRealTimers();
});

describe('data', () => {
  it('fetches get_state, then subscribes, and fetches again on changed', async () => {
    const fake = await mount();
    expect(fake.send.mock.calls[0][0]).toEqual({ type: 'home_keeper_library/get_state' });
    expect(fake.hass.connection.subscribeMessage).toHaveBeenCalledTimes(1);
    expect(fake.subs[0].msg).toEqual({ type: 'home_keeper_library/subscribe' });
    fake.push();
    await flush();
    expect(fake.calls('get_state')).toHaveLength(2);
  });

  it('shows the error of a failed fetch', async () => {
    const fake = fakeHass();
    fake.send.mockRejectedValueOnce({ message: 'boom' });
    el = document.createElement('home-keeper-library-tab');
    el.route = { path: '/books' };
    document.body.appendChild(el);
    el.hass = fake.hass;
    await flush();
    expect(text()).toContain('boom');
  });
});

describe('books view', () => {
  it('shows the owned books with the status counts', async () => {
    await mount();
    expect($$('.hkl-tile')).toHaveLength(36);
    expect($('[data-k="st-all"]').textContent).toContain('36');
    expect($('[data-k="st-read"]').textContent).toContain('9');
    expect($('[data-k="nav-books"]').getAttribute('aria-current')).toBe('page');
  });

  it('reads the filters from the route', async () => {
    await mount('/books?status=reading&view=rows');
    expect($$('.hkl-row').map((r) => r.querySelector('.hkl-row-title').textContent)).toEqual([
      'Every Grain of Rice',
      'Integrated Chinese 1',
      'Project Hail Mary',
    ]);
    expect($('[data-k="st-reading"]').getAttribute('aria-pressed')).toBe('true');
  });

  it('includes books with no copy when owned is all', async () => {
    await mount('/books?owned=all');
    expect($$('.hkl-tile')).toHaveLength(42);
  });

  it('navigates with replace when a chip or a menu changes', async () => {
    await mount();
    $('[data-k="st-read"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith('/books?status=read', { replace: true });
    change($('[data-k="f-sort"]'), 'title');
    expect(host.navigate).toHaveBeenLastCalledWith('/books?status=read&sort=title', { replace: true });
    $('[data-k="clear"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith('/books?sort=title', { replace: true });
  });

  it('clears a shelf that is not in the new room', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves).find((s) => s.name === 'Top').id;
    const office = Object.values(state.rooms).find((r) => r.name === 'Office').id;
    await mount(`/books?shelf=${shelf}`);
    change($('[data-k="f-room"]'), office);
    expect(host.navigate).toHaveBeenLastCalledWith(`/books?room=${office}`, { replace: true });
  });

  it('debounces the search into the URL and keeps the focus', async () => {
    await mount();
    vi.useFakeTimers();
    const input = $('[data-k="q"]');
    input.focus();
    input.value = 'le guin';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(host.navigate).not.toHaveBeenCalled();
    vi.advanceTimersByTime(260);
    expect(host.navigate).toHaveBeenCalledWith('/books?q=le+guin', { replace: true });
    expect(el.shadowRoot.activeElement?.dataset.k).toBe('q');
    expect($$('.hkl-tile').length).toBe(12);
  });

  it('opens a book with a push', async () => {
    await mount();
    $('.hkl-tile').click();
    expect(host.navigate.mock.calls[0][0]).toMatch(/^\/books\/b0/);
    expect(host.navigate.mock.calls[0][1]).toEqual({ replace: false });
  });

  it('escapes user text', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    state.books[id].title = '<img src=x onerror="alert(1)">';
    await mount('/books', { state });
    expect($('img')).toBeNull();
    expect(text()).toContain('<img src=x onerror="alert(1)">');
  });

  it('shows a banner for a non-admin user', async () => {
    const state = fixture();
    state.me.is_admin = false;
    await mount('/books', { state });
    expect(text()).toContain('Only an admin can change the library.');
  });
});

describe('book detail', () => {
  it('shows the location, the loan and the task link', async () => {
    const state = fixture();
    await mount(`/books/${bookId(state, 'The Left Hand of Darkness')}`);
    expect($('h1').textContent).toBe('The Left Hand of Darkness');
    expect(text()).toContain('Living room › Bookcase A › Shelf 2');
    expect(text()).toContain('Priya · since Sep 12, 2026');
    expect($('.hkl-task').getAttribute('href')).toBe('/home-keeper/tasks/task0002');
    expect(host.taskLink).toHaveBeenCalledWith('task0002');
    expect(text()).toContain('Read on Mar 2, 2025 · Read 2 times');
    expect(text()).toContain('Page 112 of 304');
    expect($('[data-k="rs-read"]').getAttribute('aria-pressed')).toBe('true');
    expect($$('.hkl-star.on')).toHaveLength(4);
  });

  it('sets the status, the rating and the page for the person', async () => {
    const state = fixture();
    const id = bookId(state, 'The Lathe of Heaven');
    const fake = await mount(`/books/${id}`);
    $('[data-k="rs-reading"]').click();
    await flush();
    const [msg] = fake.calls('set_reading');
    expect(msg).toMatchObject({ book_id: id, person_id: ALEX, status: 'reading' });
    expect(msg.started).toMatch(/^\d{4}-\d\d-\d\d$/);
    $('[data-k="star-3"]').click();
    await flush();
    expect(fake.calls('set_reading')[1]).toMatchObject({ book_id: id, rating: 3 });
    change($('[data-k="r-page"]'), '42');
    await flush();
    expect(fake.calls('set_reading')[2]).toMatchObject({ page: 42 });
  });

  it('sets the status of another person', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const fake = await mount(`/books/${id}`);
    change($('[data-k="rp"]'), '5a0000000000000000000000000005a0');
    $('[data-k="rs-read"]').click();
    await flush();
    expect(fake.calls('set_reading')[0]).toMatchObject({ person_id: '5a0000000000000000000000000005a0', status: 'read', read_count: 1 });
  });

  it('returns a loan', async () => {
    const state = fixture();
    const fake = await mount(`/books/${bookId(state, 'The Left Hand of Darkness')}`);
    $('[data-act="return-loan"]').click();
    await flush();
    expect(fake.calls('return_loan')).toEqual([{ type: 'home_keeper_library/return_loan', loan_id: expect.any(String) }]);
    expect(host.showToast).toHaveBeenCalledWith('Book returned.');
  });

  it('deletes after the confirmation and goes back to the list', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const fake = await mount(`/books/${id}`);
    $('[data-k="delete-book"]').click();
    expect(el.shadowRoot.getElementById('dlg').textContent).toContain('Delete "Dune"');
    $('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('delete_book')[0]).toMatchObject({ book_id: id });
    expect(host.navigate).toHaveBeenLastCalledWith('/books', { replace: true });
  });

  it('shows the gone notice for a deleted book', async () => {
    await mount('/books/nope');
    expect(text()).toContain('This book is not in the library.');
  });

  it('saves the shared notes', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const fake = await mount(`/books/${id}`);
    $('[data-k="notes-edit"]').click();
    $('[data-k="notes-text"]').value = '**Good**';
    $('[data-k="notes-save"]').click();
    await flush();
    expect(fake.calls('update_book')[0]).toMatchObject({ book_id: id, shared_notes: '**Good**' });
  });

  it('edits the book from the dialog', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    const fake = await mount(`/books/${id}`);
    $('[data-k="edit-book"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="authors"]').value = 'Frank Herbert, Someone Else';
    dlg.querySelector('[name="isbn"]').value = '0-441-47812-3';
    dlg.querySelector('[name="series_name"]').value = 'Dune';
    dlg.querySelector('[name="series_number"]').value = '1';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('update_book')[0]).toMatchObject({
      book_id: id,
      title: 'Dune',
      authors: ['Frank Herbert', 'Someone Else'],
      isbn13: '9780441478125',
      series: { name: 'Dune', number: 1 },
      pages: 688,
    });
    expect(dlg.innerHTML).toBe('');
  });

  it('shows the error of a failed dialog inline', async () => {
    const state = fixture();
    const fake = await mount(`/books/${bookId(state, 'Dune')}`, { replies: { update_book: () => Promise.reject({ message: 'Not allowed' }) } });
    void fake;
    $('[data-k="edit-book"]').click();
    $('[data-k="d-submit"]').click();
    await flush();
    expect(el.shadowRoot.getElementById('dlg').textContent).toContain('Not allowed');
  });
});

describe('shelves, loans, wishlist and settings', () => {
  it('draws a spine for each book on a shelf', async () => {
    await mount('/shelves');
    const shelf = $$('.hkl-shelf')[1];
    expect(shelf.querySelector('.hkl-shelf-name').textContent).toBe('Shelf 2');
    expect(shelf.querySelectorAll('.hkl-spine')).toHaveLength(7);
    expect(text()).toContain('No shelf: 2 copies');
  });

  it('adds a bookcase with shelves', async () => {
    const fake = await mount('/shelves', { replies: { add_bookcase: { id: 'newcase' } } });
    $('[data-act="add-bookcase"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="name"]').value = 'Case C';
    dlg.querySelector('[name="shelves"]').value = '2';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush(10);
    expect(fake.calls('add_bookcase')[0]).toMatchObject({ name: 'Case C', room_id: expect.any(String) });
    expect(fake.calls('add_shelf').map((m) => [m.bookcase_id, m.name])).toEqual([
      ['newcase', 'Shelf 1'],
      ['newcase', 'Shelf 2'],
    ]);
  });

  it('lists the loans of each tab', async () => {
    await mount('/loans');
    expect($$('.hkl-listrow')).toHaveLength(3);
    expect($('[data-k="lt-in"]').textContent).toContain('2');
    await mount('/loans?tab=in');
    expect(text()).toContain('Seattle Public Library · Alex · Paperback · Reading');
  });

  it('lends a copy with a task', async () => {
    const fake = await mount('/loans');
    $('[data-k="lend-book"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="party"]').value = 'Priya';
    dlg.querySelector('[name="due"]').value = '2026-11-04';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('lend_book')[0]).toMatchObject({ party: 'Priya', due: '2026-11-04', add_task: true, copy_id: expect.any(String) });
  });

  it('adds a borrowed book by ISBN', async () => {
    const fake = await mount('/loans');
    $('[data-k="add-borrowed"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="query"]').value = '978-0-441-47812-5';
    dlg.querySelector('[name="party"]').value = 'Library';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('borrow_book')[0]).toMatchObject({ isbn: '9780441478125', party: 'Library', person_id: ALEX });
    expect(fake.calls('borrow_book')[0].title).toBeUndefined();
  });

  it('sets Buy on a wishlist book', async () => {
    const fake = await mount('/wishlist');
    expect($$('.hkl-listrow')).toHaveLength(4);
    const box = $('[data-chg="wish-buy"]:not(:checked)');
    change(box, true);
    await flush();
    expect(fake.calls('update_wishlist')[0]).toMatchObject({ book_id: box.dataset.id, buy: true });
  });

  it('saves the person settings', async () => {
    const fake = await mount('/settings', { replies: { list_todo_entities: { entities: [{ entity_id: 'todo.books', name: 'Books list' }] } } });
    await flush();
    expect(fake.calls('list_todo_entities')).toHaveLength(1);
    expect($$('[data-key="wishlist_todo"] option').map((o) => o.textContent)).toContain('Books list');
    change($(`[data-k="pg-${ALEX}"]`), '30');
    await flush();
    expect(fake.calls('set_person_settings')[0]).toEqual({ type: 'home_keeper_library/set_person_settings', person_id: ALEX, yearly_goal: 30 });
  });
});

describe('scan', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
  });

  it('starts the camera step and shows the HTTPS message with no camera API', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    await mount(`/scan?shelf=${shelf}`);
    expect(text()).toContain('Scan into Shelf 1');
    $('[data-k="scan-start"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith(`/scan?shelf=${shelf}&step=camera`, { replace: false });
    await flush();
    expect(text()).toContain('The camera needs HTTPS.');
    expect($('[data-k="isbn-input"]')).not.toBeNull();
  });

  it('scans an ISBN and resolves a duplicate', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    const dune = Object.values(state.books).find((b) => b.title === 'Dune');
    const copies = Object.values(state.copies).filter((c) => c.book_id === dune.id);
    const fake = await mount(`/scan?shelf=${shelf}&step=camera`, {
      replies: {
        scan_isbn: (m) =>
          m.on_duplicate === 'ask'
            ? { result: 'duplicate', book: dune, copy: null, existing_copies: copies }
            : { result: 'moved', book: dune, copy: copies[0], existing_copies: copies },
      },
    });
    const input = $('[data-k="isbn-input"]');
    input.value = 'bad';
    $('[data-k="isbn-add"]').click();
    expect(host.showToast).toHaveBeenCalledWith('This is not a valid ISBN.');
    $('[data-k="isbn-input"]').value = dune.isbn13;
    $('[data-k="isbn-add"]').click();
    await flush();
    expect(fake.calls('scan_isbn')[0]).toMatchObject({ isbn: dune.isbn13, shelf_id: shelf, on_duplicate: 'ask' });
    expect(text()).toContain('Already in Office › Tall bookcase › Shelf 1');
    $('[data-value="move"]').click();
    await flush();
    expect(fake.calls('scan_isbn')[1]).toMatchObject({ on_duplicate: 'move' });
    expect(text()).toContain('Moved here');
    expect(text()).toContain('Added to this shelf: 1');
    $('[data-k="scan-done"]').click();
    expect(text()).toContain('Scan summary');
    expect($$('.hkl-stat b').map((b) => b.textContent)).toEqual(['0', '1', '0']);
  });

  it('sets Read for me on the scanned books when the box is set', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    const dune = Object.values(state.books).find((b) => b.title === 'Dune');
    const fake = await mount(`/scan?shelf=${shelf}&step=camera`, {
      replies: { scan_isbn: { result: 'added', book: dune, copy: null, existing_copies: [] } },
    });
    $('[data-k="isbn-input"]').value = dune.isbn13;
    $('[data-k="isbn-add"]').click();
    await flush();
    $('[data-k="scan-done"]').click();
    change($('[data-k="markread"]'), true);
    $('[data-k="scan-finish"]').click();
    await flush();
    expect(fake.calls('set_reading')[0]).toMatchObject({ book_id: dune.id, person_id: ALEX, status: 'read' });
  });
});

describe('import', () => {
  it('runs a dry run, then the import', async () => {
    const summary = { counts: { rows: 3, read: 2, wishlist: 1, existing: 1, new: 2, title_match: 0 }, rows: [] };
    const fake = await mount('/import', { replies: { import_csv: summary } });
    expect($('#hkl-import-title').textContent).toBe('Import books');
    const input = $('[data-k="im-file"]');
    const file = new File(['Title,Author\nA,B\nC,D\nE,F\n'], 'goodreads_library_export.csv', { type: 'text/csv' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await flush(10);
    expect(fake.calls('import_csv')[0]).toMatchObject({ content: 'Title,Author\nA,B\nC,D\nE,F\n', source: 'goodreads', person_id: ALEX, dry_run: true, import_notes: true, replace_reading: false, shelf_id: null });
    expect(text()).toContain('goodreads_library_export.csv · 3 rows');
    expect(text()).toContain('Already in the library: 1');
    $('[data-k="import-run"]').click();
    await flush();
    expect(fake.calls('import_csv')[1]).toMatchObject({ dry_run: false });
    expect(host.showToast).toHaveBeenCalledWith('Import complete.');
  });
});
