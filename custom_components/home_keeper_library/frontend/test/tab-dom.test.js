import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/tab-index.ts';
import { coverUrls } from '../src/markup.ts';
import { ALEX, bookId, fakeHass, fixture, flush, SAM } from './fake-hass.js';

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

  it('ends a subscription that starts after the tab leaves the page', async () => {
    const fake = fakeHass();
    const unsub = vi.fn();
    let resolve;
    fake.hass.connection.subscribeMessage = vi.fn(() => new Promise((r) => (resolve = r)));
    el = document.createElement('home-keeper-library-tab');
    el.route = { path: '/books' };
    document.body.appendChild(el);
    el.hass = fake.hass;
    await flush();
    el.remove();
    resolve(unsub);
    await flush();
    expect(unsub).toHaveBeenCalledTimes(1);
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
    expect($$('.hkl-tile')).toHaveLength(38);
    expect($('[data-k="st-all"]').textContent).toContain('38');
    expect($('[data-k="st-read"]').textContent).toContain('9');
    expect($('[data-k="nav-books"]').getAttribute('aria-current')).toBe('page');
  });

  it('reads the filters from the route', async () => {
    await mount('/books;status=reading;view=rows');
    expect($$('.hkl-row').map((r) => r.querySelector('.hkl-row-title').textContent)).toEqual([
      'Every Grain of Rice',
      'Integrated Chinese 1',
      'The Ministry for the Future',
      'Project Hail Mary',
    ]);
    expect($('[data-k="st-reading"]').getAttribute('aria-pressed')).toBe('true');
  });

  it('includes books with no copy when owned is all', async () => {
    await mount('/books;owned=all');
    expect($$('.hkl-tile')).toHaveLength(44);
  });

  it('navigates with replace when a chip or a menu changes', async () => {
    await mount();
    $('[data-k="st-read"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith('/books;status=read', { replace: true });
    change($('[data-k="f-sort"]'), 'title');
    expect(host.navigate).toHaveBeenLastCalledWith('/books;status=read;sort=title', { replace: true });
    $('[data-k="clear"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith('/books;sort=title', { replace: true });
  });

  it('clears a shelf that is not in the new room', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves).find((s) => s.name === 'Top').id;
    const office = Object.values(state.rooms).find((r) => r.name === 'Office').id;
    await mount(`/books;shelf=${shelf}`);
    change($('[data-k="f-room"]'), office);
    expect(host.navigate).toHaveBeenLastCalledWith(`/books;room=${office}`, { replace: true });
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
    expect(host.navigate).toHaveBeenCalledWith('/books;q=le%20guin', { replace: true });
    expect(el.shadowRoot.activeElement?.dataset.k).toBe('q');
    expect($$('.hkl-tile').length).toBe(12);
  });

  it('opens a book with a push', async () => {
    await mount();
    $('.hkl-tile').click();
    expect(host.navigate.mock.calls[0][0]).toMatch(/^\/books\/[0-9a-f]{32}$/);
    expect(host.navigate.mock.calls[0][1]).toEqual({ replace: false });
  });

  it('escapes user text', async () => {
    const state = fixture();
    state.books.find((b) => b.title === 'Dune').title = '<img src=x onerror="alert(1)">';
    await mount('/books', { state });
    expect(el.shadowRoot.querySelector('img[src="x"]')).toBeNull();
    expect(text()).toContain('<img src=x onerror="alert(1)">');
  });

  it('shows a banner for a non-admin user', async () => {
    const state = fixture();
    state.me.is_admin = false;
    await mount('/books', { state });
    expect(text()).toContain('Only an admin can change the library.');
  });
});

describe('covers', () => {
  beforeEach(() => coverUrls.clear());

  it('signs each cover path, then shows the image with the signed URL', async () => {
    const state = fixture();
    const book = state.books.find((b) => b.title === 'The Left Hand of Darkness');
    expect(book.cover_url).toMatch(/^\/api\/home_keeper_library\/cover\/[0-9a-f]{32}\?v=[0-9a-f]{8}$/);
    const fake = await mount('/books');
    const signs = fake.send.mock.calls.map((c) => c[0]).filter((m) => m.type === 'auth/sign_path');
    expect(signs.length).toBe(state.books.filter((b) => b.owned && b.cover_url).length);
    expect(signs[0].expires).toBe(3600);
    const tile = $(`[data-k="b-${book.id}"]`);
    expect(tile.querySelector('img').getAttribute('src')).toBe(`${book.cover_url}&authSig=t3600`);
    expect(tile.querySelector('.hkl-cover-badge').textContent).toBe('Custom cover');
    const plain = $$('.hkl-tile .hkl-cover:not([data-cover])');
    expect(plain.length).toBeGreaterThan(0);
    expect(plain[0].querySelector('img')).toBeNull();
  });

  it('shows the title block when the sign fails', async () => {
    const state = fixture();
    const book = state.books.find((b) => b.title === 'Piranesi');
    await mount(`/books/${book.id}`, { replies: { 'auth/sign_path': () => Promise.reject(new Error('no')) } });
    const block = $('.hkl-cover-large');
    expect(block.dataset.cover).toBe(book.cover_url);
    expect(block.querySelector('img')).toBeNull();
    expect(block.querySelector('.hkl-cover-title').textContent).toBe('Piranesi');
  });

  it('puts the reader marks in their own row and shows the ring colors in the legend', async () => {
    const state = fixture();
    const book = state.books.find((b) => b.title === 'The Left Hand of Darkness');
    await mount('/books');
    const tile = $(`[data-k="b-${book.id}"]`);
    const dots = tile.querySelectorAll('.hkl-tile-readers .hkl-dot');
    expect([...dots].map((d) => d.getAttribute('aria-label'))).toEqual(['Alex: Read', 'Sam: Reading']);
    expect(tile.querySelector('.hkl-tile-meta .hkl-dot')).toBeNull();
    expect(dots[0].style.getPropertyValue('--p')).not.toBe(dots[1].style.getPropertyValue('--p'));
    expect($$('.hkl-legend .hkl-ring').map((r) => r.className)).toEqual(['hkl-ring ring-read', 'hkl-ring ring-reading']);
  });
});

describe('book detail', () => {
  it('shows the location, the loan and the task link', async () => {
    const state = fixture();
    await mount(`/books/${bookId(state, 'The Left Hand of Darkness')}`);
    expect($('h1').textContent).toBe('The Left Hand of Darkness');
    expect(text()).toContain('Living room › Bookcase A › Shelf 2');
    expect(text()).toContain('Priya · since Sep 12, 2026');
    const task = state.loans.find((l) => l.party === 'Priya' && l.book_id === bookId(state, 'The Left Hand of Darkness')).hk_task_id;
    expect(task).toMatch(/^[0-9a-f]{32}$/);
    expect($('.hkl-task').getAttribute('href')).toBe(`/home-keeper/tasks/${task}`);
    expect(host.taskLink).toHaveBeenCalledWith(task);
    expect(text()).toContain('Read on Mar 2, 2025 · Read 2 times');
    expect(text()).toContain('Page 112 of 304');
    expect($('[data-k="rs-read"]').getAttribute('aria-pressed')).toBe('true');
    expect($$('.hkl-star.on')).toHaveLength(4);
  });

  it('opens the task with host.openTask, or leaves the link to the browser', async () => {
    const state = fixture();
    await mount(`/books/${bookId(state, 'The Left Hand of Darkness')}`);
    const link = $('.hkl-task');
    const plain = new MouseEvent('click', { bubbles: true, cancelable: true, composed: true });
    link.dispatchEvent(plain);
    expect(plain.defaultPrevented).toBe(false);
    host.openTask = vi.fn();
    const click = new MouseEvent('click', { bubbles: true, cancelable: true, composed: true });
    $('.hkl-task').dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    expect(host.openTask).toHaveBeenCalledWith(link.dataset.id);
    expect(host.navigate).not.toHaveBeenCalled();
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
    change($('[data-k="rp"]'), SAM);
    $('[data-k="rs-read"]').click();
    await flush();
    expect(fake.calls('set_reading')[0]).toMatchObject({ person_id: SAM, status: 'read', read_count: 1 });
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

  it('shows the error of a failed dialog inline and keeps what the user typed', async () => {
    const state = fixture();
    let n = 0;
    await mount(`/books/${bookId(state, 'Dune')}`, { replies: { update_book: () => Promise.reject({ message: `Not allowed ${++n}` }) } });
    $('[data-k="edit-book"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="subtitle"]').value = 'Typed text';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(dlg.querySelectorAll('.hkl-error')).toHaveLength(1);
    expect(dlg.querySelector('.hkl-error').textContent).toBe('Not allowed 1');
    expect(dlg.querySelector('[name="subtitle"]').value).toBe('Typed text');
    expect(dlg.querySelector('[data-k="d-submit"]').disabled).toBe(false);
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect([...dlg.querySelectorAll('.hkl-error')].map((e) => e.textContent)).toEqual(['Not allowed 2']);
  });

  it('disables the submit button while the call runs, and a late reply leaves a new dialog open', async () => {
    const state = fixture();
    let finish;
    await mount(`/books/${bookId(state, 'Dune')}`, { replies: { update_book: () => new Promise((r) => (finish = r)) } });
    $('[data-k="edit-book"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(dlg.querySelector('[data-k="d-submit"]').disabled).toBe(true);
    dlg.querySelector('[data-k="d-x"]').click();
    expect(dlg.innerHTML).toBe('');
    $('[data-k="edit-book"]').click();
    finish({});
    await flush();
    expect(dlg.querySelector('[data-k="d-submit"]').disabled).toBe(false);
  });

  it('keeps the notes editor open with the text when the save fails', async () => {
    const state = fixture();
    const id = bookId(state, 'Dune');
    await mount(`/books/${id}`, { replies: { update_book: () => Promise.reject({ message: 'No' }) } });
    $('[data-k="notes-edit"]').click();
    $('[data-k="notes-text"]').value = 'Kept';
    $('[data-k="notes-save"]').click();
    await flush();
    expect($('[data-k="notes-text"]').value).toBe('Kept');
    expect(host.showToast).toHaveBeenCalledWith('No');
  });

  it('shows the stored status again when a change fails', async () => {
    const state = fixture();
    const id = bookId(state, 'The Lathe of Heaven');
    await mount(`/books/${id}`, { replies: { set_reading: () => Promise.reject({ message: 'No' }) } });
    const page = $('[data-k="r-page"]');
    const before = page.value;
    change(page, '42');
    await flush();
    expect($('[data-k="r-page"]').value).toBe(before);
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
    await mount('/loans;tab=in');
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

describe('settings currency', () => {
  it('saves a new currency code with set_settings', async () => {
    const fake = await mount('/settings');
    const input = $('[data-k="currency"]');
    expect(input.value).toBe('EUR');
    input.value = 'usd';
    $('[data-k="currency-save"]').click();
    await flush();
    expect(fake.calls('set_settings')).toEqual([{ type: 'home_keeper_library/set_settings', currency: 'USD' }]);
    expect(host.showToast).toHaveBeenCalledWith('Settings saved.');
  });

  it('refuses a code that is not 3 letters and sends nothing for the same code', async () => {
    const fake = await mount('/settings');
    $('[data-k="currency"]').value = 'EU';
    $('[data-k="currency-save"]').click();
    await flush();
    expect(host.showToast).toHaveBeenCalledWith('Type a currency code of 3 letters.');
    $('[data-k="currency"]').value = ' eur ';
    $('[data-k="currency-save"]').click();
    await flush();
    expect(fake.calls('set_settings')).toEqual([]);
  });
});

describe('scan', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
  });

  it('blocks the camera on a page that is not HTTPS, and Enter ISBN still starts', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    await mount(`/scan;shelf=${shelf}`);
    expect(text()).toContain('Scan into Shelf 1');
    expect($('[data-k="m-https"]').textContent).toContain('The camera needs HTTPS.');
    expect($('[data-k="scan-start"]').disabled).toBe(true);
    expect($('[data-k="scan-start"]').getAttribute('aria-describedby')).toBe('scan-https');
    expect($('#scan-https')).toBe($('[data-k="m-https"]'));
    $('[data-k="scan-start"]').click();
    expect(host.navigate).not.toHaveBeenCalled();

    change($('[data-k="m-manual"]'), 'manual');
    await flush();
    expect($('[data-k="m-https"]')).toBeNull();
    expect($('[data-k="scan-start"]').disabled).toBe(false);
    $('[data-k="scan-start"]').click();
    expect(host.navigate).toHaveBeenLastCalledWith(`/scan;shelf=${shelf};step=camera`, { replace: false });
    await flush();
    expect($('[data-k="isbn-input"]')).not.toBeNull();
  });

  it('shows the HTTPS message on the camera step of a page that is not HTTPS', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${Object.values(state.shelves)[0].id};step=camera`);
    await flush();
    expect(text()).toContain('The camera needs HTTPS.');
    expect($('[data-k="isbn-input"]')).not.toBeNull();
  });

  it('lets the camera start on an HTTPS page', async () => {
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    const state = fixture();
    await mount(`/scan;shelf=${Object.values(state.shelves)[0].id}`);
    expect($('[data-k="m-https"]')).toBeNull();
    expect($('[data-k="scan-start"]').disabled).toBe(false);
  });

  it('scans an ISBN and resolves a duplicate', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    const dune = Object.values(state.books).find((b) => b.title === 'Dune');
    const copies = Object.values(state.copies).filter((c) => c.book_id === dune.id);
    const fake = await mount(`/scan;shelf=${shelf};step=camera`, {
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
    expect(text()).toContain('Already in Living room › Bookcase A › Shelf 1');
    $('[data-value="move"]').click();
    await flush();
    expect(fake.calls('scan_isbn')[1]).toMatchObject({ on_duplicate: 'move' });
    expect(text()).toContain('Moved here');
    expect(text()).toContain('Added to this shelf: 1');
    $('[data-k="scan-done"]').click();
    expect(text()).toContain('Scan summary');
    expect($$('.hkl-stat b').map((b) => b.textContent)).toEqual(['0', '1', '0']);
  });

  it('keeps a typed ISBN when a store change renders the view', async () => {
    const state = fixture();
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    const input = $('[data-k="isbn-input"]');
    input.focus();
    input.value = '978044';
    fake.push();
    await flush();
    const now = $('[data-k="isbn-input"]');
    expect(now).not.toBe(input);
    expect(now.value).toBe('978044');
    expect(el.shadowRoot.activeElement).toBe(now);
  });

  it('marks a scanned book that comes from the wishlist', async () => {
    const state = fixture();
    const shelf = state.shelves[0].id;
    const wished = state.books.find((b) => b.title === 'The Other Wind');
    const dune = state.books.find((b) => b.title === 'Dune');
    const fake = await mount(`/scan;shelf=${shelf};step=camera`, {
      replies: {
        scan_isbn: (m) =>
          m.isbn === wished.isbn13
            ? { result: 'added', book: wished, copy: null, existing_copies: [], from_wishlist: true }
            : { result: 'added', book: dune, copy: null, existing_copies: [] },
      },
    });
    void fake;
    for (const isbn of [wished.isbn13, dune.isbn13]) {
      $('[data-k="isbn-input"]').value = isbn;
      $('[data-k="isbn-add"]').click();
      await flush();
    }
    const rows = $$('.hkl-result');
    const wishRow = rows.find((r) => r.textContent.includes('The Other Wind'));
    const duneRow = rows.find((r) => r.textContent.includes('Dune'));
    expect(wishRow.querySelector('[data-k^="from-wish-"]').textContent).toBe('From wishlist');
    expect(wishRow.querySelector('.hkl-pill.ok').textContent).toBe('Added');
    expect(duneRow.querySelector('[data-k^="from-wish-"]')).toBeNull();
  });

  it('sets Read for me on the scanned books when the box is set', async () => {
    const state = fixture();
    const shelf = Object.values(state.shelves)[0].id;
    const dune = Object.values(state.books).find((b) => b.title === 'Dune');
    const fake = await mount(`/scan;shelf=${shelf};step=camera`, {
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

describe('scan with no match', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
  });

  /** A book that a scan saved with no match: its ISBN is its title. */
  function missing(state, isbn, id) {
    const shelf = state.shelves[0].id;
    const book = { ...state.books[0], id, title: isbn, subtitle: '', authors: [], isbn13: isbn, isbn10: null, publisher: '', published: '', pages: null, needs_details: true, cover: null };
    const copy = { ...state.copies[0], id: `c-${id}`, book_id: id, shelf_id: shelf, format: 'paperback' };
    state.books.push(book);
    state.copies.push(copy);
    return { book, copy, reply: { result: 'not_found', book, copy, existing_copies: [] } };
  }

  async function scan(isbn) {
    $('[data-k="isbn-input"]').value = isbn;
    $('[data-k="isbn-add"]').click();
  }

  const sheet = () => $('.hkl-dialog.sheet');

  function typeTitle(value) {
    const input = sheet().querySelector('[name="title"]');
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  it('asks for the title before the next scan, and saves only the title', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: {
        scan_isbn: miss.reply,
        update_book: (m) => {
          miss.book.title = m.title;
          return { book: miss.book };
        },
      },
    });
    await scan(miss.book.isbn13);
    await flush();
    expect(sheet()).not.toBeNull();
    expect(sheet().querySelector('h2').textContent).toBe('No match in Open Library');
    expect(sheet().querySelector('[data-k="d-isbn"]').textContent).toBe('ISBN 9781402894626');
    expect(sheet().querySelector('[data-k="d-x"]')).toBeNull();
    expect(sheet().querySelector('[data-k="d-cancel"]')).toBeNull();
    expect(sheet().querySelector('[data-k="d-more"]').open).toBe(false);
    const submit = sheet().querySelector('[data-k="d-submit"]');
    expect(submit.textContent).toBe('Save and scan next');
    expect(submit.disabled).toBe(true);
    expect(el.shadowRoot.activeElement).toBe(sheet().querySelector('[name="title"]'));

    // Escape, a click on the scrim and a new scan do not close the sheet.
    sheet().dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true }));
    $('.hkl-scrim').click();
    await scan('9780441478125');
    await flush();
    expect(sheet()).not.toBeNull();
    expect(fake.calls('scan_isbn')).toHaveLength(1);

    typeTitle('  ');
    expect(submit.disabled).toBe(true);
    typeTitle('Field Notes on Moss');
    expect(submit.disabled).toBe(false);
    submit.click();
    await flush();
    const calls = fake.calls('update_book');
    expect(calls).toHaveLength(1);
    expect(calls[0]).toEqual({ type: 'home_keeper_library/update_book', book_id: 'new', title: 'Field Notes on Moss' });
    expect(fake.calls('update_copy')).toHaveLength(0);
    expect(fake.calls('set_cover')).toHaveLength(0);
    expect(sheet()).toBeNull();
    expect(el.shadowRoot.activeElement).toBe($('[data-k="isbn-input"]'));
    const row = $$('.hkl-result').find((r) => r.textContent.includes('Field Notes on Moss'));
    expect(row.textContent).toContain('No match in Open Library');

    // The scan goes on.
    await scan('9780441478125');
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(2);
  });

  it('shows the error of an empty title and keeps the sheet open', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, { state, replies: { scan_isbn: miss.reply } });
    await scan(miss.book.isbn13);
    await flush();
    sheet().dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await flush();
    expect(sheet().querySelector('.hkl-error').textContent).toBe('Type the title.');
    expect(fake.calls('update_book')).toHaveLength(0);
  });

  it('keeps the sheet open with the error when a save call fails', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: {
        scan_isbn: miss.reply,
        update_copy: () => {
          throw { code: 'home_assistant_error', message: 'Copy save failed' };
        },
      },
    });
    await scan(miss.book.isbn13);
    await flush();
    typeTitle('Field Notes on Moss');
    sheet().querySelector('[name="format"]').value = 'hardcover';
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('update_book')).toHaveLength(1);
    expect(sheet()).not.toBeNull();
    expect(sheet().querySelector('.hkl-error').textContent).toContain('Copy save failed');
    expect(sheet().querySelector('[name="title"]').value).toBe('Field Notes on Moss');
    // The scan stays paused.
    await scan('9780441478125');
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(1);
  });

  it('saves the details that the user adds', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, { state, replies: { scan_isbn: miss.reply } });
    await scan(miss.book.isbn13);
    await flush();
    sheet().querySelector('[data-k="d-more-toggle"]').click();
    expect(sheet().querySelector('[data-k="d-more"]').open).toBe(true);
    expect(sheet().querySelector('[data-k="d-cover"]').getAttribute('capture')).toBe('environment');
    typeTitle('Field Notes on Moss');
    const set = (name, value) => (sheet().querySelector(`[name="${name}"]`).value = value);
    set('authors', 'A. Hollins, B. Reed');
    set('published', '2004');
    set('pages', '120');
    set('format', 'hardcover');
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('update_book')[0]).toEqual({
      type: 'home_keeper_library/update_book',
      book_id: 'new',
      title: 'Field Notes on Moss',
      authors: ['A. Hollins', 'B. Reed'],
      published: '2004',
      pages: 120,
    });
    expect(fake.calls('update_copy')[0]).toEqual({ type: 'home_keeper_library/update_copy', copy_id: 'c-new', format: 'hardcover' });
    expect(sheet()).toBeNull();
  });

  it('removes a scan, then asks for the next book with no match', async () => {
    const state = fixture();
    const first = missing(state, '9781402894626', 'one');
    const second = missing(state, '9780306406157', 'two');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: { scan_isbn: (m) => (m.isbn === first.book.isbn13 ? first.reply : second.reply) },
    });
    // The 2nd scan starts while the lookup of the 1st one runs.
    void scan(first.book.isbn13);
    void scan(second.book.isbn13);
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(2);
    expect(sheet().querySelector('[data-k="d-isbn"]').textContent).toBe('ISBN 9781402894626');
    const remove = sheet().querySelector('[data-k="d-remove"]');
    expect(remove.textContent).toBe('Remove this scan');
    remove.click();
    await flush();
    expect(fake.calls('delete_book')).toEqual([{ type: 'home_keeper_library/delete_book', book_id: 'one' }]);
    expect(sheet().querySelector('[data-k="d-isbn"]').textContent).toBe('ISBN 9780306406157');
    expect($$('[data-k^="removed-"]').map((p) => p.textContent)).toEqual(['Removed']);

    typeTitle('Second book');
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(sheet()).toBeNull();
    $('[data-k="scan-done"]').click();
    expect($$('.hkl-stat b').map((b) => b.textContent)).toEqual(['0', '0', '1']);
  });

  const MATCH = { title: 'Field Notes on Moss', authors: ['A. Hollins'], first_published: '1999', work_key: 'OL45W' };

  it('shows the Open Library work for the title, and links it on a confirm', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: { scan_isbn: miss.reply, search_catalog: { status: 'found', match: MATCH } },
    });
    await scan(miss.book.isbn13);
    await flush();
    typeTitle('Field notes on moss');
    sheet().querySelector('[data-k="d-more-toggle"]').click();
    sheet().querySelector('[name="authors"]').value = 'Hollins';
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('search_catalog')).toEqual([
      { type: 'home_keeper_library/search_catalog', title: 'Field notes on moss', authors: ['Hollins'] },
    ]);
    // The title sheet becomes the match dialog. It is not a sheet.
    expect(sheet()).toBeNull();
    const dlg = $('.hkl-dialog');
    expect(dlg.querySelector('h2').textContent).toBe('Found on Open Library');
    expect(dlg.querySelector('[data-k="d-match-title"]').textContent).toBe('Field Notes on Moss');
    expect(dlg.querySelector('[data-k="d-match-by"]').textContent).toBe('A. Hollins · first published 1999');
    expect(dlg.querySelector('[data-k="d-match-hint"]').textContent).toContain('The ISBN stays the same.');
    expect(dlg.querySelector('[data-k="d-match-view"]').getAttribute('href')).toBe('https://openlibrary.org/works/OL45W');
    expect(dlg.querySelector('[data-k="d-cancel"]').textContent).toBe('Not this book');
    expect(dlg.querySelector('[data-k="d-submit"]').textContent).toBe('Use these details');
    expect(dlg.querySelector('[data-k="d-submit"]').disabled).toBe(false);
    // The scan stays paused while the match shows.
    await scan('9780441478125');
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(1);

    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('link_catalog')).toEqual([{ type: 'home_keeper_library/link_catalog', book_id: 'new', record: 'OL45W' }]);
    expect($('.hkl-dialog')).toBeNull();
    expect(host.showToast).toHaveBeenCalledWith('Details added from Open Library.');
    await scan('9780441478125');
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(2);
  });

  it('closes the match with no link on Not this book', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: { scan_isbn: miss.reply, search_catalog: { status: 'found', match: MATCH } },
    });
    await scan(miss.book.isbn13);
    await flush();
    typeTitle('Field Notes on Moss');
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('search_catalog')[0].authors).toEqual([]);
    $('.hkl-dialog [data-k="d-cancel"]').click();
    await flush();
    expect($('.hkl-dialog')).toBeNull();
    expect(fake.calls('link_catalog')).toHaveLength(0);
    await scan('9780441478125');
    await flush();
    expect(fake.calls('scan_isbn')).toHaveLength(2);
  });

  it.each([
    ['no match', { status: 'not_found', match: null }],
    ['Open Library is down', { status: 'unavailable', match: null }],
    ['a match with no work key', { status: 'found', match: { ...MATCH, work_key: '' } }],
    ['a failed call', () => {
      throw { code: 'home_assistant_error', message: 'Search failed' };
    }],
  ])('goes on with the scan after %s', async (_name, reply) => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      state,
      replies: { scan_isbn: miss.reply, search_catalog: reply },
    });
    await scan(miss.book.isbn13);
    await flush();
    typeTitle('Field Notes on Moss');
    sheet().querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('search_catalog')).toHaveLength(1);
    expect($('.hkl-dialog')).toBeNull();
    expect(el.shadowRoot.activeElement).toBe($('[data-k="isbn-input"]'));
  });

  it('closes the sheet when the user leaves the scan', async () => {
    const state = fixture();
    const miss = missing(state, '9781402894626', 'new');
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, { state, replies: { scan_isbn: miss.reply } });
    await scan(miss.book.isbn13);
    await flush();
    expect(sheet()).not.toBeNull();
    el.route = { path: '/books' };
    await flush();
    expect(sheet()).toBeNull();
  });
});

describe('scan camera', () => {
  let cam;

  /** A fake camera, a fake `BarcodeDetector` and a video `play()` that the test controls. */
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    cam = { gum: 0, refuse: false, frozen: false, paused: new WeakMap(), tracks: [] };
    const track = () => {
      const t = new EventTarget();
      Object.assign(t, { readyState: 'live', muted: false, enabled: true, stop: () => (t.readyState = 'ended'), getCapabilities: () => ({}) });
      cam.tracks.push(t);
      return t;
    };
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          cam.gum++;
          const t = track();
          return { getVideoTracks: () => [t], getTracks: () => [t] };
        },
      },
    });
    window.BarcodeDetector = class {
      static async getSupportedFormats() {
        return ['ean_13'];
      }
      async detect() {
        return [];
      }
    };
    vi.spyOn(HTMLMediaElement.prototype, 'paused', 'get').mockImplementation(function () {
      return cam.paused.get(this) ?? true;
    });
    // The video has a frame, and its time moves, unless the test freezes the picture.
    vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(4);
    vi.spyOn(HTMLMediaElement.prototype, 'currentTime', 'get').mockImplementation(() => (cam.frozen ? 1 : performance.now() / 1000));
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(function () {
      if (cam.refuse) return Promise.reject(new DOMException('no gesture', 'NotAllowedError'));
      cam.paused.set(this, false);
      this.dispatchEvent(new Event('playing'));
      return Promise.resolve();
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete window.BarcodeDetector;
  });

  const video = () => $('[data-slot="video"] video');
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  /** The browser pauses the video, as Home Keeper or the system can do. */
  function pause(v) {
    cam.paused.set(v, true);
    v.dispatchEvent(new Event('pause'));
  }

  it('keeps the video in the page when a scan renders the view', async () => {
    const state = fixture();
    const dune = state.books.find((b) => b.title === 'Dune');
    const fake = await mount(`/scan;shelf=${state.shelves[0].id};step=camera`, {
      replies: { scan_isbn: { result: 'added', book: dune, copy: null, existing_copies: [] } },
    });
    const v = video();
    const slot = v.parentNode;
    expect(v.paused).toBe(false);
    $('[data-k="scan-manual"]').click();
    $('[data-k="isbn-input"]').value = dune.isbn13;
    $('[data-k="isbn-add"]').click();
    fake.push();
    await flush();
    expect(text()).toContain('Added to this shelf: 1');
    // The slot and its video never left the page, so the browser did not pause the video.
    expect($('[data-slot="video"]')).toBe(slot);
    expect(video()).toBe(v);
    expect(cam.gum).toBe(1);
  });

  it('shows the restart button when the browser refuses play(), and a tap plays again', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    const v = video();
    cam.refuse = true;
    pause(v);
    await wait(900);
    expect($('[data-k="cam-restart"]').textContent).toBe('The camera stopped. Tap to start it again.');
    cam.refuse = false;
    $('[data-k="cam-restart"]').click();
    await wait(900);
    expect($('[data-k="cam-restart"]')).toBeNull();
    expect(video()).toBe(v);
    expect(v.paused).toBe(false);
    expect(cam.gum).toBe(1);
  });

  it('does not show the restart button for a short pause', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    const v = video();
    pause(v);
    await v.play();
    await wait(900);
    expect($('[data-k="cam-restart"]')).toBeNull();
  });

  it('starts a new camera on a tap when the camera track ended', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    const first = video();
    cam.tracks[0].readyState = 'ended';
    cam.tracks[0].dispatchEvent(new Event('ended'));
    await wait(900);
    $('[data-k="cam-restart"]').click();
    await flush();
    expect(cam.gum).toBe(2);
    expect(video()).not.toBe(first);
    expect($('[data-k="cam-restart"]')).toBeNull();
  });

  it('starts a new camera on a tap when the picture is frozen', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    const first = video();
    cam.frozen = true;
    await wait(1400);
    expect($('[data-k="cam-restart"]')).toBeNull();
    await wait(1400);
    expect($('[data-k="cam-restart"]')).not.toBeNull();
    expect(first.paused).toBe(false);
    cam.frozen = false;
    $('[data-k="cam-restart"]').click();
    await flush();
    expect(cam.gum).toBe(2);
    expect(video()).not.toBe(first);
    expect($('[data-k="cam-restart"]')).toBeNull();
  });

  it('shows the camera state and log in the debug view only with ;debug=1', async () => {
    const state = fixture();
    await mount(`/scan;shelf=${state.shelves[0].id};step=camera`);
    expect($('[data-k="cam-debug"]')).toBeNull();
    el.route = { path: `/scan;shelf=${state.shelves[0].id};step=camera;debug=1` };
    await flush();
    const dbg = $('[data-k="cam-debug"]').textContent;
    expect(dbg).toMatch(/^tab \d+ of \d+: in page=true/);
    expect(dbg).toContain('video: paused=false frozen=false');
    expect(dbg).toContain('track: live muted=false');
    expect(dbg).toContain('detector: native');
    expect(dbg).toContain('getUserMedia ok');
  });
});

describe('import', () => {
  function pick(name, content) {
    const input = $('[data-k="im-file"]');
    const file = new File([content], name, { type: 'text/csv' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  it('shows the result of each row and says when the list is cut', async () => {
    const summary = {
      dry_run: true,
      counts: { rows: 900, read: 3, existing: 1, new: 1, title_match: 1, errors: 1 },
      rows: [
        { line: 2, title: 'Piranesi', authors: ['Susanna Clarke'], isbn: '9781635575637', book_id: 'b1', action: 'existing', message: '' },
        { line: 3, title: 'Dune', authors: ['Frank Herbert'], isbn: null, book_id: 'b2', action: 'title_match', message: '' },
        { line: 4, title: '', authors: [], isbn: null, book_id: null, action: 'error', message: 'The row has no title.' },
      ],
      truncated: true,
    };
    await mount('/import', { replies: { import_csv: summary } });
    pick('goodreads_library_export.csv', 'Title\nA\n');
    await flush(10);
    const cells = $$('.hkl-details tr').map((r) => r.lastElementChild.textContent);
    expect(cells).toEqual(['In the library', 'Title match', 'The row has no title.']);
    expect($('[data-k="import-truncated"]').textContent).toBe('The list shows only part of the file. The import reads all rows.');
    expect($('[data-k="import-run"]').textContent).toBe('Import 900 rows');
  });

  it('sends a file above 3 MB to the service over REST', async () => {
    const summary = { dry_run: true, counts: { rows: 1 }, rows: [], truncated: false };
    const callApi = vi.fn(async () => ({ changed_states: [], service_response: summary }));
    const fake = await mount('/import', { callApi });
    const big = `Title\n${'x'.repeat(3 * 1024 * 1024)}\n`;
    pick('library.csv', big);
    await flush(10);
    expect(fake.calls('import_csv')).toEqual([]);
    expect(callApi).toHaveBeenCalledWith('POST', 'services/home_keeper_library/import_csv?return_response', expect.objectContaining({ dry_run: true, source: 'goodreads', person_id: ALEX }));
    expect(callApi.mock.calls[0][2].content).toBe(big);
    expect(text()).toContain('Import 1 row');
  });

  it('runs a dry run, then the import', async () => {
    const summary = { dry_run: true, counts: { rows: 3, read: 2, wishlist: 1, existing: 1, new: 2, title_match: 0 }, rows: [], truncated: false };
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

describe('Open Library', () => {
  const RICE = 'Every Grain of Rice';

  function olState({ connected = true, title = RICE, status = 'missing', extra = {} } = {}) {
    const state = fixture();
    const book = Object.values(state.books).find((b) => b.title === title);
    Object.assign(book, { catalogs: {}, catalog_status: status ? { openlibrary: status } : {}, ...extra });
    state.catalog_accounts = { openlibrary: { connected, username: connected ? 'alex_reads' : null } };
    return { state, id: book.id };
  }

  it('shows the banner on a book that Open Library does not have, and Not now skips it', async () => {
    const { state, id } = olState();
    const fake = await mount(`/books/${id}`, { state });
    expect($('[data-k="ol-banner"]').textContent).toContain('Open Library does not have this book');
    $('[data-k="ol-not-now"]').click();
    await flush();
    expect(fake.calls('skip_catalog')).toEqual([{ type: 'home_keeper_library/skip_catalog', book_id: id }]);
    expect(host.showToast).toHaveBeenCalledWith('The book is no longer in the Not on Open Library list.');
  });

  it('shows no banner to a non-admin user, on a linked book or on a skipped book', async () => {
    const user = olState();
    user.state.me.is_admin = false;
    delete user.state.catalog_accounts;
    await mount(`/books/${user.id}`, { state: user.state });
    expect($('[data-k="ol-banner"]')).toBeNull();
    el.remove();
    const skipped = olState({ status: 'skipped' });
    await mount(`/books/${skipped.id}`, { state: skipped.state });
    expect($('[data-k="ol-banner"]')).toBeNull();
    expect($('[data-k="ol-send-later"]').textContent).toBe('Send to Open Library');
    el.remove();
    const dune = fixture();
    await mount(`/books/${bookId(dune, 'Dune')}`, { state: dune });
    expect($('[data-k="ol-banner"]')).toBeNull();
    expect($('[data-k="ol-send-later"]')).toBeNull();
  });

  it('links to Settings when no account is connected', async () => {
    const { state, id } = olState({ connected: false });
    await mount(`/books/${id}`, { state });
    const go = $('[data-k="ol-banner-send"]');
    expect(go.textContent).toBe('Connect Open Library');
    go.click();
    expect(host.navigate).toHaveBeenCalledWith('/settings', expect.anything());
  });

  it('sends the selected fields and shows the new edition', async () => {
    const { state, id } = olState({ extra: { publisher: 'Bloomsbury', published: '2013', isbn13: '9781408802526', cover: { kind: 'custom', file: 'x.jpg' } } });
    const reply = { result: 'added', record: 'OL5M', cover: 'failed', book: {} };
    const fake = await mount(`/books/${id}`, { state, replies: { send_to_catalog: reply } });
    $('[data-k="ol-banner-send"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    expect(dlg.textContent).toContain('You send as alex_reads.');
    expect(dlg.querySelector('[data-k="d-send-publisher"]').checked).toBe(true);
    expect(dlg.querySelector('[data-k="d-send-cover"]').checked).toBe(false);
    dlg.querySelector('[data-k="d-send-published"]').checked = false;
    dlg.querySelector('[data-k="d-send-cover"]').checked = true;
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('send_to_catalog')).toEqual([
      { type: 'home_keeper_library/send_to_catalog', book_id: id, fields: ['publisher', 'isbn'], include_cover: true },
    ]);
    expect(dlg.querySelector('[data-k="d-ol-added"]').textContent).toContain('OL5M');
    expect(dlg.querySelector('[data-k="d-ol-cover-failed"]')).not.toBeNull();
    expect(dlg.querySelector('[data-k="d-ol-edit"]').getAttribute('href')).toBe('https://openlibrary.org/books/OL5M/edit');
    expect(dlg.querySelector('[data-k="d-cancel"]')).toBeNull();
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(dlg.innerHTML).toBe('');
  });

  it('disables an empty field and hides the cover choice without a custom cover', async () => {
    const { state, id } = olState({ extra: { publisher: '', isbn13: null, isbn10: null } });
    await mount(`/books/${id}`, { state });
    $('[data-k="ol-banner-send"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    expect(dlg.querySelector('[data-k="d-send-publisher"]').disabled).toBe(true);
    expect(dlg.querySelector('[data-k="d-send-isbn"]').disabled).toBe(true);
    expect(dlg.querySelector('[data-k="d-send-cover"]')).toBeNull();
  });

  it('offers to link an edition that Open Library already has', async () => {
    const { state, id } = olState();
    const reply = { result: 'existing', record: 'OL9M', cover: 'skipped', book: {} };
    const fake = await mount(`/books/${id}`, { state, replies: { send_to_catalog: reply } });
    $('[data-k="ol-banner-send"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(dlg.querySelector('[data-k="d-ol-existing"]').textContent).toContain('OL9M');
    expect(dlg.querySelector('[data-k="d-submit"]').textContent).toBe('Link to OL9M');
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('link_catalog')).toEqual([{ type: 'home_keeper_library/link_catalog', book_id: id, record: 'OL9M' }]);
    expect(host.showToast).toHaveBeenCalledWith('Book linked to Open Library.');
    expect(dlg.innerHTML).toBe('');
  });

  it('shows a send error in the dialog and hides the busy line', async () => {
    const { state, id } = olState();
    await mount(`/books/${id}`, { state, replies: { send_to_catalog: () => Promise.reject({ message: 'Refused' }) } });
    $('[data-k="ol-banner-send"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(dlg.querySelector('.hkl-error').textContent).toBe('Refused');
    expect(dlg.querySelector('[data-k="d-sending"]').hidden).toBe(true);
    expect(dlg.querySelector('[data-k="d-submit"]').disabled).toBe(false);
  });

  it('lists the books that are not on Open Library with an action on each row', async () => {
    const { state, id } = olState();
    const fake = await mount('/books?status=not_on_ol', { state });
    expect($('[data-k="st-not_on_ol"]').textContent).toContain('Not on Open Library');
    expect($('[data-k="ol-list-hint"]').textContent).toContain('(4)');
    expect($$('.hkl-olrow').map((r) => r.querySelector('.hkl-row-title').textContent)).toEqual(['Every Grain of Rice', 'Steering the Craft', '9780980123468', 'Untitled paperback']);
    // A book with no author asks for one and has no Send button.
    const untitled = $$('.hkl-olrow')[3];
    expect(untitled.querySelector('.hkl-row-hint').textContent).toBe('Add an author before you send');
    expect(untitled.querySelector('[data-act="send-ol"]')).toBeNull();
    $(`[data-k="ol-skip-${id}"]`).click();
    await flush();
    expect(fake.calls('skip_catalog')[0]).toMatchObject({ book_id: id });
    $(`[data-k="ol-send-${id}"]`).click();
    expect(el.shadowRoot.getElementById('dlg').textContent).toContain('Send to Open Library');
  });

  it('hides the chip with no book in it, and from a non-admin user', async () => {
    const none = fixture();
    for (const b of Object.values(none.books)) b.catalog_status = {};
    await mount('/books', { state: none });
    expect($('[data-k="st-not_on_ol"]')).toBeNull();
    el.remove();
    const { state } = olState();
    state.me.is_admin = false;
    await mount('/books?status=not_on_ol', { state });
    expect($('[data-k="st-not_on_ol"]')).toBeNull();
    expect($$('.hkl-olrow')).toHaveLength(0);
  });

  it('tells the user after a manual add that Open Library does not have the book', async () => {
    const reply = { book: { id: 'new' }, existing: false, lookup: 'not_found' };
    await mount('/books', { replies: { add_book: reply } });
    $('[data-k="add-book"]').click();
    const dlg = el.shadowRoot.getElementById('dlg');
    dlg.querySelector('[name="query"]').value = '9780000000002';
    dlg.querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(host.showToast).toHaveBeenCalledWith('Book added. Open Library does not have it.');
  });
});

describe('settings Open Library', () => {
  function flowApi(result) {
    return vi.fn(async (method, path, body) => {
      if (method === 'DELETE') return {};
      if (path === 'config/config_entries/options/flow') return { flow_id: 'f1', type: 'menu' };
      if (body?.next_step_id) return { flow_id: 'f1', type: 'form' };
      return result;
    });
  }

  it('connects an account through the options flow, never through a service', async () => {
    const callApi = flowApi({ flow_id: 'f1', type: 'create_entry' });
    const fake = await mount('/settings', { callApi, replies: { 'config_entries/get': [{ entry_id: 'e1' }] } });
    $('[data-k="ol-access"]').value = ' ACC ';
    $('[data-k="ol-secret"]').value = 'SEC';
    $('[data-k="ol-connect-save"]').click();
    await flush();
    expect(callApi.mock.calls).toEqual([
      ['POST', 'config/config_entries/options/flow', { handler: 'e1' }],
      ['POST', 'config/config_entries/options/flow/f1', { next_step_id: 'openlibrary' }],
      ['POST', 'config/config_entries/options/flow/f1', { access_key: 'ACC', secret_key: 'SEC' }],
    ]);
    expect(host.showToast).toHaveBeenCalledWith('Open Library account connected.');
    const sent = JSON.stringify(fake.send.mock.calls);
    expect(sent).not.toContain('SEC');
  });

  it('shows the flow error, keeps the access key and closes the flow', async () => {
    const callApi = flowApi({ flow_id: 'f1', type: 'form', errors: { base: 'invalid_auth' } });
    await mount('/settings', { callApi, replies: { 'config_entries/get': [{ entry_id: 'e1' }] } });
    $('[data-k="ol-access"]').value = 'ACC';
    $('[data-k="ol-secret"]').value = 'BAD';
    $('[data-k="ol-connect-save"]').click();
    await flush();
    expect($('[data-k="ol-error"]').textContent).toBe('Open Library did not accept these keys.');
    expect($('[data-k="ol-access"]').value).toBe('ACC');
    expect($('[data-k="ol-secret"]').value).toBe('');
    expect(callApi.mock.calls.at(-1)).toEqual(['DELETE', 'config/config_entries/options/flow/f1']);
  });

  it('asks for both keys before it starts the flow', async () => {
    const callApi = flowApi({});
    await mount('/settings', { callApi });
    $('[data-k="ol-access"]').value = 'ACC';
    $('[data-k="ol-connect-save"]').click();
    await flush();
    expect($('[data-k="ol-error"]').textContent).toBe('Enter the access key and the secret key.');
    expect(callApi).not.toHaveBeenCalled();
  });

  it('shows the account and disconnects it after a confirm', async () => {
    const state = fixture();
    state.catalog_accounts = { openlibrary: { connected: true, username: 'alex_reads' } };
    const fake = await mount('/settings', { state });
    expect($('[data-k="ol-connected"]').textContent).toBe('Connected as alex_reads');
    expect($('[data-k="ol-access"]')).toBeNull();
    $('[data-k="ol-disconnect"]').click();
    el.shadowRoot.getElementById('dlg').querySelector('[data-k="d-submit"]').click();
    await flush();
    expect(fake.calls('disconnect_catalog')).toHaveLength(1);
  });
});
