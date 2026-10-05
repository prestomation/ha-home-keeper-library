import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as u from '../src/utils.ts';

// Small builders, so each test shows the data it reads.
const book = (id, extra = {}) => ({
  id,
  title: `Title ${id}`,
  subtitle: '',
  authors: [],
  isbn13: null,
  isbn10: null,
  publisher: '',
  published: '',
  pages: null,
  language: null,
  subjects: [],
  series: null,
  description: '',
  tags: [],
  shared_notes: '',
  openlibrary: null,
  cover: { kind: 'none', file: null },
  needs_details: false,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  wishlist: null,
  reading: {},
  owned: true,
  cover_url: null,
  ...extra,
});
const row = (status, extra = {}) => ({
  status,
  rating: null,
  page: null,
  started: null,
  finished: null,
  read_count: 0,
  private_notes: '',
  updated_at: '2026-01-01T00:00:00+00:00',
  ...extra,
});
const copy = (id, bookId, shelfId, extra = {}) => ({
  id,
  book_id: bookId,
  shelf_id: shelfId,
  format: 'paperback',
  condition: null,
  acquired: null,
  signed: false,
  first_edition: false,
  note: '',
  created_at: '',
  ...extra,
});

function lib(extra = {}) {
  return u.normalizeState({
    rooms: { r1: { id: 'r1', name: 'Living', area_id: null, order: 1 }, r2: { id: 'r2', name: 'Office', area_id: null, order: 2 } },
    bookcases: {
      c1: { id: 'c1', room_id: 'r1', name: 'Case A', note: '', order: 1 },
      c2: { id: 'c2', room_id: 'r2', name: 'Case B', note: '', order: 1 },
    },
    shelves: {
      s2: { id: 's2', bookcase_id: 'c1', name: 'Shelf 2', order: 2 },
      s1: { id: 's1', bookcase_id: 'c1', name: 'Shelf 1', order: 1 },
      s3: { id: 's3', bookcase_id: 'c2', name: 'Top', order: 1 },
    },
    books: {},
    copies: {},
    loans: {},
    people: {},
    me: { person_id: 'me', is_admin: true },
    currency: 'EUR',
    ...extra,
  });
}

describe('escapeHTML', () => {
  it('escapes the 5 HTML characters', () => {
    expect(u.escapeHTML('<b>"x" & \'y\'</b>')).toBe('&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;');
  });
  it('escapes the ampersand first', () => {
    expect(u.escapeHTML('&lt;')).toBe('&amp;lt;');
  });
  it('gives an empty string for null and undefined, and coerces numbers', () => {
    expect(u.escapeHTML(null)).toBe('');
    expect(u.escapeHTML(undefined)).toBe('');
    expect(u.escapeHTML(0)).toBe('0');
  });
  it('makes a payload inert in a real DOM', () => {
    const el = document.createElement('div');
    el.innerHTML = u.escapeHTML('<img src=x onerror=alert(1)>');
    expect(el.querySelector('img')).toBeNull();
  });
});

describe('fold and initials', () => {
  it('folds case and accents', () => {
    expect(u.fold('Gödel ÉCOLE')).toBe('godel ecole');
    expect(u.fold(null)).toBe('');
  });
  it('gives the upper case first letter', () => {
    expect(u.initials('  sam ')).toBe('S');
    expect(u.initials('')).toBe('?');
  });
});

describe('asList and normalizeState', () => {
  it('reads a map or a list', () => {
    expect(u.asList({ a: 1, b: 2 })).toEqual([1, 2]);
    const list = [1];
    expect(u.asList(list)).toEqual([1]);
    expect(u.asList(list)).not.toBe(list);
    expect(u.asList(null)).toEqual([]);
    expect(u.asList(undefined)).toEqual([]);
  });

  it('sorts rooms, bookcases and shelves by order, then name', () => {
    const l = u.normalizeState({
      rooms: [
        { id: 'b', name: 'B', order: 2 },
        { id: 'z', name: 'Z', order: 1 },
        { id: 'a', name: 'A', order: 1 },
      ],
      shelves: { x: { id: 'x', name: 'X', order: 3 }, y: { id: 'y', name: 'Y', order: 1 } },
      bookcases: [{ id: 'q', name: 'Q', order: 5 }, { id: 'p', name: 'P' }],
    });
    expect(l.rooms.map((r) => r.id)).toEqual(['a', 'z', 'b']);
    expect(l.shelves.map((s) => s.id)).toEqual(['y', 'x']);
    expect(l.bookcases.map((s) => s.id)).toEqual(['p', 'q']);
  });

  it('reads the people map, sorts by name and gives each person the color of its place', () => {
    const l = u.normalizeState({
      people: {
        zoe: { person_id: 'zoe', name: 'Zoe', entity_id: 'person.zoe', share_reading: false, wishlist_todo: 'todo.x', yearly_goal: 5 },
        adam: { person_id: 'adam', name: 'Adam', entity_id: null, share_reading: true, yearly_goal: null },
        bea: { person_id: 'bea', name: 'Bea', entity_id: null, share_reading: true, wishlist_todo: null, yearly_goal: 3 },
      },
    });
    expect(l.people).toEqual([
      { id: 'adam', name: 'Adam', share_reading: true, wishlist_todo: null, yearly_goal: null, color: u.PERSON_COLORS[0] },
      { id: 'bea', name: 'Bea', share_reading: true, wishlist_todo: null, yearly_goal: 3, color: u.PERSON_COLORS[1] },
      { id: 'zoe', name: 'Zoe', share_reading: false, wishlist_todo: 'todo.x', yearly_goal: 5, color: u.PERSON_COLORS[2] },
    ]);
  });

  it('gives 2 people with the same name different colors, in id order', () => {
    const l = u.normalizePeople({ b: { person_id: 'b', name: 'Sam' }, a: { person_id: 'a', name: 'Sam' } });
    expect(l.map((p) => p.id)).toEqual(['a', 'b']);
    expect(l[0].color).not.toBe(l[1].color);
  });

  it('uses the key for a person with no id or name, and keeps share_reading when it is missing', () => {
    const l = u.normalizeState({ people: { p9: { wishlist_todo: null, yearly_goal: null } } });
    expect(l.people[0].id).toBe('p9');
    expect(l.people[0].name).toBe('p9');
    expect(l.people[0].share_reading).toBe(true);
    expect(u.normalizePeople(undefined)).toEqual([]);
    expect(u.normalizePeople(null)).toEqual([]);
  });

  it('fills missing book lists and the defaults of me and currency', () => {
    const l = u.normalizeState({ books: [{ id: 'b' }] });
    expect(l.books[0]).toMatchObject({ authors: [], tags: [], subjects: [], reading: {} });
    expect(l.me).toEqual({ person_id: null, name: null, is_admin: false });
    expect(u.normalizeState({ me: { person_id: 'p', name: 'P', is_admin: 'yes' } }).me).toEqual({ person_id: 'p', name: 'P', is_admin: false });
    expect(l.currency).toBe('USD');
    expect(l.copies).toEqual([]);
    expect(l.loans).toEqual([]);
  });

  it('keeps the lists that a book has', () => {
    const l = u.normalizeState({ books: [{ id: 'b', authors: ['A'], tags: ['t'], subjects: ['s'], reading: { p: row('read') } }], currency: 'EUR', me: { person_id: 'p', is_admin: true } });
    expect(l.books[0]).toMatchObject({ authors: ['A'], tags: ['t'], subjects: ['s'] });
    expect(l.books[0].reading.p.status).toBe('read');
    expect(l.currency).toBe('EUR');
    expect(l.me.person_id).toBe('p');
  });
});

describe('personNames', () => {
  it('reads the id and the friendly name of each person entity', () => {
    expect(
      u.personNames({
        'person.alex': { entity_id: 'person.alex', attributes: { id: 'a1', friendly_name: 'Alex' } },
        'person.no_name': { entity_id: 'person.no_name', attributes: { id: 'a2' } },
        'person.no_id': { entity_id: 'person.no_id', attributes: { friendly_name: 'X' } },
        'sensor.x': { entity_id: 'sensor.x', attributes: { id: 'a3', friendly_name: 'S' } },
        'person.empty': { entity_id: 'person.empty', attributes: { id: '', friendly_name: 'E' } },
      }),
    ).toEqual({ a1: 'Alex', a2: 'no_name' });
    expect(u.personNames(undefined)).toEqual({});
  });
});

describe('buildIndex, shelfPath and locations', () => {
  const l = lib({
    books: { b1: book('b1'), b2: book('b2') },
    copies: { k1: copy('k1', 'b1', 's1'), k2: copy('k2', 'b1', null), k3: copy('k3', 'b2', 's3') },
    loans: {
      l1: { id: 'l1', direction: 'out', book_id: 'b1', copy_id: 'k1', returned: null },
      l2: { id: 'l2', direction: 'out', book_id: 'b2', copy_id: 'k3', returned: '2026-01-01' },
      l3: { id: 'l3', direction: 'in', book_id: 'b2', copy_id: null, returned: null },
      l4: { id: 'l4', direction: 'out', book_id: 'b2', copy_id: null, returned: null },
    },
  });
  const idx = u.buildIndex(l);

  it('groups copies by book and by shelf, with "" for no shelf', () => {
    expect(idx.copiesByBook.get('b1').map((c) => c.id)).toEqual(['k1', 'k2']);
    expect(idx.copiesByShelf.get('').map((c) => c.id)).toEqual(['k2']);
    expect(idx.copiesByShelf.get('s3').map((c) => c.id)).toEqual(['k3']);
    expect(idx.copy.get('k3').book_id).toBe('b2');
    expect(idx.book.get('b2').id).toBe('b2');
  });

  it('keeps only open loans and maps an out loan to its copy', () => {
    expect(idx.activeLoans.get('b1').map((x) => x.id)).toEqual(['l1']);
    expect(idx.activeLoans.get('b2').map((x) => x.id)).toEqual(['l3', 'l4']);
    expect(idx.loanByCopy.get('k1').id).toBe('l1');
    expect(idx.loanByCopy.has('k3')).toBe(false);
    expect([...idx.loanByCopy.keys()]).toEqual(['k1']);
  });

  it('finds the room, bookcase and shelf', () => {
    const p = u.shelfPath(idx, 's1');
    expect([p.room.id, p.bookcase.id, p.shelf.id]).toEqual(['r1', 'c1', 's1']);
    expect(u.shelfPath(idx, null)).toEqual({ room: null, bookcase: null, shelf: null });
    expect(u.shelfPath(idx, 'missing')).toEqual({ room: null, bookcase: null, shelf: null });
  });

  it('labels a location in full and in short', () => {
    expect(u.locationLabel(idx, 's1')).toBe('Living › Case A › Shelf 1');
    expect(u.locationLabel(idx, null)).toBe('');
    expect(u.shortLocation(idx, 's3')).toBe('Office · Top');
    expect(u.shortLocation(idx, undefined)).toBe('');
  });

  it('orders the shelves and finds the next one', () => {
    expect(u.orderedShelves(l).map((s) => s.id)).toEqual(['s1', 's2', 's3']);
    expect(u.nextShelf(l, 's1').id).toBe('s2');
    expect(u.nextShelf(l, 's2').id).toBe('s3');
    expect(u.nextShelf(l, 's3')).toBeNull();
    expect(u.nextShelf(l, 'nope')).toBeNull();
    expect(u.nextShelf(l, null)).toBeNull();
  });

  it('adds the copy values of a room', () => {
    const l2 = lib({ copies: { a: copy('a', 'b', 's1', { value: 10 }), b: copy('b', 'b', 's2', { value: 5.5 }), c: copy('c', 'b', 's3', { value: 99 }), d: copy('d', 'b', 's1') } });
    const i2 = u.buildIndex(l2);
    expect(u.roomValue(l2, i2, 'r1')).toBe(15.5);
    expect(u.roomValue(l2, i2, 'r2')).toBe(99);
  });
});

describe('parseRoute and buildPath', () => {
  it('parses the default and the book list', () => {
    expect(u.parseRoute('')).toEqual({ view: 'books', id: null, query: {} });
    expect(u.parseRoute(undefined)).toEqual({ view: 'books', id: null, query: {} });
    expect(u.parseRoute('/books')).toEqual({ view: 'books', id: null, query: {} });
    expect(u.parseRoute('/nope/x')).toEqual({ view: 'books', id: null, query: {} });
  });

  it('parses each view', () => {
    expect(u.parseRoute('/books/abc')).toEqual({ view: 'book', id: 'abc', query: {} });
    expect(u.parseRoute('/shelves')).toEqual({ view: 'shelves', id: null, query: {} });
    expect(u.parseRoute('/shelves/r1')).toEqual({ view: 'shelves', id: 'r1', query: {} });
    for (const v of ['loans', 'wishlist', 'scan', 'import', 'settings']) {
      expect(u.parseRoute(`/${v}`).view).toBe(v);
    }
  });

  it('reads the query from the path or from search', () => {
    expect(u.parseRoute('/books?q=le%20guin&room=r1').query).toEqual({ q: 'le guin', room: 'r1' });
    expect(u.parseRoute('/books', '?q=x').query).toEqual({ q: 'x' });
    expect(u.parseRoute('/books?q=a', '?q=b').query).toEqual({ q: 'a' });
  });

  it('drops default values and keys of other views', () => {
    expect(u.parseRoute('/books?status=all&sort=author&view=grid&owned=yes&tab=in').query).toEqual({});
    expect(u.parseRoute('/loans?tab=in&q=x').query).toEqual({ tab: 'in' });
    expect(u.parseRoute('/loans?tab=out').query).toEqual({});
    expect(u.parseRoute('/scan?shelf=s1&mode=borrowed&step=camera').query).toEqual({ shelf: 's1', mode: 'borrowed', step: 'camera' });
    expect(u.parseRoute('/scan?step=setup&mode=shelf').query).toEqual({});
    expect(u.parseRoute('/books/x?q=a').query).toEqual({});
  });

  it('decodes ids and tolerates extra slashes', () => {
    expect(u.parseRoute('//books/a%2Fb//').id).toBe('a/b');
  });

  it('builds paths in a fixed key order with no defaults', () => {
    expect(u.buildPath({ view: 'books' })).toBe('/books');
    expect(u.buildPath({ view: 'books', query: { view: 'rows', q: 'x y', sort: 'author' } })).toBe('/books?q=x+y&view=rows');
    expect(u.buildPath({ view: 'book', id: 'a/b' })).toBe('/books/a%2Fb');
    expect(u.buildPath({ view: 'book', id: null })).toBe('/books');
    expect(u.buildPath({ view: 'shelves', id: 'r1' })).toBe('/shelves/r1');
    expect(u.buildPath({ view: 'shelves' })).toBe('/shelves');
    expect(u.buildPath({ view: 'loans', query: { tab: 'returned' } })).toBe('/loans?tab=returned');
    expect(u.buildPath({ view: 'settings', query: { q: 'x' } })).toBe('/settings');
  });

  it('round-trips', () => {
    for (const p of ['/books?q=a&status=read&room=r&shelf=s&reader=p&subject=x&owned=all&sort=title&view=rows', '/books/b1', '/shelves/r', '/loans?tab=in', '/wishlist', '/scan?shelf=s&mode=borrowed&step=summary', '/import', '/settings']) {
      expect(u.buildPath(u.parseRoute(p))).toBe(p);
    }
  });

  it('sets and removes a query key', () => {
    const q = { a: '1' };
    expect(u.withQuery(q, 'b', '2')).toEqual({ a: '1', b: '2' });
    expect(u.withQuery(q, 'a', '')).toEqual({});
    expect(u.withQuery(q, 'a', null)).toEqual({});
    expect(q).toEqual({ a: '1' });
  });
});

describe('readFilters and hasFilters', () => {
  it('reads the defaults', () => {
    expect(u.readFilters({})).toEqual({ q: '', status: 'all', room: '', shelf: '', reader: '', subject: '', owned: 'yes', sort: 'author', view: 'grid' });
  });
  it('reads valid values and drops unknown ones', () => {
    const f = u.readFilters({ q: 'x', status: 'read', room: 'r', shelf: 's', reader: 'p', subject: 'y', owned: 'no', sort: 'rating', view: 'rows' });
    expect(f).toEqual({ q: 'x', status: 'read', room: 'r', shelf: 's', reader: 'p', subject: 'y', owned: 'no', sort: 'rating', view: 'rows' });
    expect(u.readFilters({ status: 'bad', owned: 'bad', sort: 'bad', view: 'bad' })).toMatchObject({ status: 'all', owned: 'yes', sort: 'author', view: 'grid' });
  });
  it('says if a filter narrows the list', () => {
    const base = u.readFilters({});
    expect(u.hasFilters(base)).toBe(false);
    expect(u.hasFilters({ ...base, sort: 'title', view: 'rows' })).toBe(false);
    for (const [k, v] of [['q', 'x'], ['room', 'r'], ['shelf', 's'], ['reader', 'p'], ['subject', 'y'], ['status', 'read'], ['owned', 'all']]) {
      expect(u.hasFilters({ ...base, [k]: v }), k).toBe(true);
    }
  });
});

describe('reading helpers and search', () => {
  const b = book('b', {
    title: 'The Left Hand',
    subtitle: 'A novel',
    authors: ['Ursula K. Le Guin'],
    isbn13: '9780441478125',
    isbn10: '0441478123',
    series: { name: 'Hainish', number: 4 },
    shared_notes: 'Book club',
    tags: ['hugo'],
    reading: { me: row('read', { private_notes: 'secret word' }), other: row('reading', { private_notes: 'hidden' }) },
  });

  it('reads the row and the status of a person', () => {
    expect(u.readingOf(b, 'me').status).toBe('read');
    expect(u.readingOf(b, null)).toBeNull();
    expect(u.readingOf(b, 'nobody')).toBeNull();
    expect(u.statusOf(b, 'other')).toBe('reading');
    expect(u.statusOf(b, 'nobody')).toBeNull();
    expect(u.statusOf(book('x', { reading: { p: { status: null } } }), 'p')).toBeNull();
  });

  it('searches each field', () => {
    for (const q of ['left hand', 'NOVEL', 'guin', '9780441478125', '978-0-441-47812-5', '0441478123', 'hainish', 'club', 'hugo', 'secret']) {
      expect(u.matchesSearch(b, q, 'me'), q).toBe(true);
    }
  });

  it('needs every word, and reads only my private notes', () => {
    expect(u.matchesSearch(b, 'left zebra', 'me')).toBe(false);
    expect(u.matchesSearch(b, 'hidden', 'me')).toBe(false);
    expect(u.matchesSearch(b, 'hidden', 'other')).toBe(true);
    expect(u.matchesSearch(b, '   ', 'me')).toBe(true);
    expect(u.matchesSearch(b, '', null)).toBe(true);
  });

  it('matches a hyphenated ISBN only as digits', () => {
    expect(u.matchesSearch(b, '0-441-47812-3', 'me')).toBe(true);
    expect(u.matchesSearch(b, '978-0-441-9', 'me')).toBe(false);
    expect(u.matchesSearch(book('n', { title: 'a-b' }), 'ab', null)).toBe(false);
  });

  it('matches accents', () => {
    expect(u.matchesSearch(book('g', { title: 'Gödel' }), 'godel', null)).toBe(true);
    expect(u.matchesSearch(book('g', { title: 'Godel' }), 'Gödel', null)).toBe(true);
  });

  it('separates fields so a search does not join 2 fields', () => {
    expect(u.searchText(book('s', { title: 'ab', subtitle: 'cd' }), null)).not.toContain('abcd');
  });
});

describe('filterBooks, statusCounts and sortBooks', () => {
  const l = lib({
    books: {
      a: book('a', { title: 'Alpha', authors: ['Zed Last'], subjects: ['SF'], reading: { me: row('read', { rating: 3 }), p2: row('read') }, created_at: '2026-01-03', published: '1999' }),
      b: book('b', { title: 'Beta', authors: ['Amy Bee'], reading: { me: row('reading') }, needs_details: true, created_at: '2026-01-02', published: 'May 1970' }),
      c: book('c', { title: 'Gamma', authors: ['Amy Bee'], owned: false, reading: { me: row('want', { rating: 5 }) }, created_at: '2026-01-01' }),
      d: book('d', { title: 'Delta', authors: [], subjects: ['SF', 'Art'], created_at: '2026-01-04', published: '2001' }),
    },
    copies: { k1: copy('k1', 'a', 's1'), k2: copy('k2', 'b', 's3'), k3: copy('k3', 'd', null) },
  });
  const ctx = { idx: u.buildIndex(l), me: 'me' };
  const ids = (q) => u.filterBooks(l.books, u.readFilters(q), ctx).map((x) => x.id);

  it('shows owned books by default, sorted by author', () => {
    expect(ids({})).toEqual(['b', 'a', 'd']);
    expect(ids({ owned: 'all' })).toEqual(['b', 'c', 'a', 'd']);
    expect(ids({ owned: 'no' })).toEqual(['c']);
  });

  it('filters by status', () => {
    expect(ids({ status: 'read' })).toEqual(['a']);
    expect(ids({ status: 'reading' })).toEqual(['b']);
    expect(ids({ status: 'unread' })).toEqual(['b', 'd']);
    expect(ids({ status: 'needs' })).toEqual(['b']);
  });

  it('filters by place', () => {
    expect(ids({ room: 'r1' })).toEqual(['a']);
    expect(ids({ room: 'r2' })).toEqual(['b']);
    expect(ids({ shelf: 's3' })).toEqual(['b']);
    expect(ids({ shelf: 'none' })).toEqual(['d']);
    expect(ids({ room: 'r1', shelf: 's3' })).toEqual([]);
    expect(ids({ room: 'r2', shelf: 's3' })).toEqual(['b']);
  });

  it('filters by reader, subject and search', () => {
    expect(ids({ reader: 'p2' })).toEqual(['a']);
    expect(ids({ reader: 'me' })).toEqual(['a']);
    expect(ids({ subject: 'Art' })).toEqual(['d']);
    expect(ids({ subject: 'SF' })).toEqual(['a', 'd']);
    expect(ids({ q: 'gamma', owned: 'all' })).toEqual(['c']);
    expect(ids({ q: 'gamma' })).toEqual([]);
  });

  it('counts each status with the other filters on', () => {
    expect(u.statusCounts(l.books, u.readFilters({}), ctx)).toEqual({ all: 3, unread: 2, reading: 1, read: 1, needs: 1 });
    expect(u.statusCounts(l.books, u.readFilters({ status: 'read', owned: 'all' }), ctx)).toEqual({ all: 4, unread: 3, reading: 1, read: 1, needs: 1 });
    expect(u.statusCounts(l.books, u.readFilters({ room: 'r1' }), ctx)).toEqual({ all: 1, unread: 0, reading: 0, read: 1, needs: 0 });
  });

  it('sorts by each key with the title as the tiebreak', () => {
    const sort = (k) => u.sortBooks(l.books, k, 'me').map((x) => x.id);
    expect(sort('author')).toEqual(['b', 'c', 'a', 'd']);
    expect(sort('title')).toEqual(['a', 'b', 'd', 'c']);
    expect(sort('added')).toEqual(['d', 'a', 'b', 'c']);
    expect(sort('published')).toEqual(['b', 'a', 'd', 'c']);
    expect(sort('rating')).toEqual(['c', 'a', 'b', 'd']);
    expect(l.books.map((x) => x.id)).toEqual(['a', 'b', 'c', 'd']);
  });

  it('sorts a series by its number inside the same author', () => {
    const s = [
      book('x3', { title: 'C', authors: ['A B'], series: { name: 'S', number: 3 } }),
      book('x1', { title: 'Z', authors: ['A B'], series: { name: 'S', number: '1' } }),
      book('x2', { title: 'A', authors: ['A B'], series: { name: 'S', number: 2 } }),
      book('x0', { title: 'Y', authors: ['A B'], series: { name: 'S', number: 'x' } }),
      book('y', { title: 'B', authors: ['A B'], series: { name: 'R', number: 9 } }),
    ];
    expect(u.sortBooks(s, 'author', null).map((x) => x.id)).toEqual(['y', 'x0', 'x1', 'x2', 'x3']);
  });

  it('lists the subjects with no duplicates', () => {
    expect(u.allSubjects(l.books)).toEqual(['Art', 'SF']);
  });
});

describe('authorKey and yearOf', () => {
  it('keys an author by the last word', () => {
    expect(u.authorKey('Ursula K. Le Guin')).toBe('guin ursula k. le guin');
    expect(u.authorKey('  Weir ')).toBe('weir weir');
    expect(u.authorKey('')).toBe('￿');
    expect(u.authorKey(undefined)).toBe('￿');
    expect(u.authorKey('Amy') < u.authorKey('')).toBe(true);
  });
  it('reads a 4 digit year', () => {
    expect(u.yearOf('March 2001')).toBe(2001);
    expect(u.yearOf('1969')).toBe(1969);
    expect(u.yearOf('12345')).toBeNull();
    expect(u.yearOf('')).toBeNull();
    expect(u.yearOf(null)).toBeNull();
  });
});

describe('ISBN', () => {
  it('cleans an ISBN', () => {
    expect(u.cleanIsbn(' 0-441-47812-x ')).toBe('044147812X');
    expect(u.cleanIsbn(null)).toBe('');
  });
  it('checks ISBN-10', () => {
    expect(u.isValidIsbn10('0441478123')).toBe(true);
    expect(u.isValidIsbn10('080442957X')).toBe(true);
    expect(u.isValidIsbn10('0441478124')).toBe(false);
    expect(u.isValidIsbn10('044147812')).toBe(false);
    expect(u.isValidIsbn10('X441478123')).toBe(false);
    expect(u.isValidIsbn10('04414781234')).toBe(false);
  });
  it('checks ISBN-13', () => {
    expect(u.ean13Check('978044147812')).toBe(5);
    expect(u.ean13Check('978000000000')).toBe(2);
    expect(u.ean13Check('979100000000')).toBe(8);
    expect(u.isValidIsbn13('9780441478125')).toBe(true);
    expect(u.isValidIsbn13('9791000000008')).toBe(true);
    expect(u.isValidIsbn13('9780441478126')).toBe(false);
    expect(u.isValidIsbn13('4006381333931')).toBe(false);
    expect(u.isValidIsbn13('97804414781255')).toBe(false);
    expect(u.isValidIsbn13('978044147812')).toBe(false);
  });
  it('converts ISBN-10 to ISBN-13', () => {
    expect(u.isbn10to13('0441478123')).toBe('9780441478125');
    expect(u.isbn10to13('080442957X')).toBe('9780804429573');
  });
  it('reads a book EAN and rejects other codes', () => {
    expect(u.isbnFromEan('9780441478125')).toBe('9780441478125');
    expect(u.isbnFromEan(' 9780441478125 ')).toBe('9780441478125');
    expect(u.isbnFromEan('4006381333931')).toBeNull();
    expect(u.isbnFromEan('96385074')).toBeNull();
    expect(u.isbnFromEan(null)).toBeNull();
  });
  it('normalizes a typed ISBN to ISBN-13', () => {
    expect(u.normalizeIsbn('978-0-441-47812-5')).toBe('9780441478125');
    expect(u.normalizeIsbn('0-441-47812-3')).toBe('9780441478125');
    expect(u.normalizeIsbn('0441478124')).toBeNull();
    expect(u.normalizeIsbn('9780441478126')).toBeNull();
    expect(u.normalizeIsbn('12345')).toBeNull();
  });
});

describe('makeCodeGate and debounce', () => {
  it('lets the same code through again only after the window', () => {
    const gate = u.makeCodeGate(3000);
    expect(gate('a', 1000)).toBe(true);
    expect(gate('a', 3999)).toBe(false);
    expect(gate('b', 3999)).toBe(true);
    expect(gate('a', 4000)).toBe(true);
    expect(gate('a', 4001)).toBe(false);
    expect(gate('a', 7000)).toBe(true);
  });
  it('accepts a first code at time 0', () => {
    expect(u.makeCodeGate(10)('x', 0)).toBe(true);
  });

  describe('debounce', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());
    it('calls once with the last arguments', () => {
      const fn = vi.fn();
      const d = u.debounce(fn, 100);
      d(1);
      vi.advanceTimersByTime(60);
      d(2);
      vi.advanceTimersByTime(99);
      expect(fn).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(fn).toHaveBeenCalledTimes(1);
      expect(fn).toHaveBeenCalledWith(2);
      d(3);
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(2);
    });
    it('cancels a pending call', () => {
      const fn = vi.fn();
      const d = u.debounce(fn, 100);
      d();
      d.cancel();
      vi.advanceTimersByTime(500);
      expect(fn).not.toHaveBeenCalled();
      d.cancel();
      d();
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });
});

describe('drawing', () => {
  it('hashes with FNV-1a', () => {
    expect(u.hash('')).toBe(0x811c9dc5);
    expect(u.hash('a')).toBe(0xe40c292c);
    expect(u.hash('foobar')).toBe(0xbf9cf968);
  });
  it('gives each id the same cover colors', () => {
    const c = u.coverColors('b1');
    expect(c).toEqual(u.coverColors('b1'));
    const [bg, ink] = u.COVER_COLORS[u.hash('b1') % u.COVER_COLORS.length];
    expect(c).toEqual({ bg, ink });
  });
  it('sizes spines from the page count and the id', () => {
    const [a, b, c, d] = u.spines([
      book('s1', { pages: 400, title: 'T' }),
      book('s2', { pages: 10 }),
      book('s3', { pages: 5000 }),
      book('s4'),
    ]);
    expect(a).toMatchObject({ id: 's1', title: 'T', w: 16 });
    expect(b.w).toBe(8);
    expect(c.w).toBe(22);
    const h = u.hash('s4');
    expect(d.w).toBe(8 + (h % 10));
    expect(d.h).toBe(56 + ((h >>> 8) % 27));
    expect(d.color).toBe(u.COVER_COLORS[h % u.COVER_COLORS.length][0]);
    expect(u.spines([book('a'), book('b'), book('c')], 2)).toHaveLength(2);
    expect(u.spines(Array.from({ length: 70 }, (_, i) => book(`x${i}`)))).toHaveLength(60);
  });
  it('gives a person color by place, and wraps after the last color', () => {
    const n = u.PERSON_COLORS.length;
    expect(new Set(u.PERSON_COLORS.map((_, i) => u.personColor(i))).size).toBe(n);
    expect(u.personColor(0)).toBe(u.PERSON_COLORS[0]);
    expect(u.personColor(n - 1)).toBe(u.PERSON_COLORS[n - 1]);
    expect(u.personColor(n)).toBe(u.PERSON_COLORS[0]);
    expect(u.personColor(n + 2)).toBe(u.PERSON_COLORS[2]);
    expect(u.personColor(-1)).toBe(u.PERSON_COLORS[n - 1]);
  });
});

describe('dates and numbers', () => {
  it('formats the local date', () => {
    expect(u.todayISO(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05');
    expect(u.todayISO(new Date(2026, 10, 25))).toBe('2026-11-25');
  });
  it('counts days between 2 dates', () => {
    expect(u.daysBetween('2026-03-01', '2026-03-31')).toBe(30);
    expect(u.daysBetween('2026-03-31T10:00:00Z', '2026-03-01')).toBe(-30);
    expect(u.daysBetween('2026-03-28', '2026-03-30')).toBe(2);
  });
  it('classifies a due date', () => {
    expect(u.dueState(null, '2026-01-10')).toEqual({ kind: 'none', days: 0 });
    expect(u.dueState('2026-01-08', '2026-01-10')).toEqual({ kind: 'overdue', days: 2 });
    expect(u.dueState('2026-01-10', '2026-01-10')).toEqual({ kind: 'today', days: 0 });
    expect(u.dueState('2026-01-11', '2026-01-10')).toEqual({ kind: 'soon', days: 1 });
    expect(u.dueState('2026-01-13', '2026-01-10')).toEqual({ kind: 'soon', days: 3 });
    expect(u.dueState('2026-01-14', '2026-01-10')).toEqual({ kind: 'later', days: 4 });
  });
  it('reads form numbers', () => {
    expect(u.intOrNull(' 12 ')).toBe(12);
    expect(u.intOrNull('0')).toBe(0);
    expect(u.intOrNull('1.5')).toBeNull();
    expect(u.intOrNull('')).toBeNull();
    expect(u.intOrNull(null)).toBeNull();
    expect(u.intOrNull('x')).toBeNull();
    expect(u.numberOrNull('7,99')).toBe(7.99);
    expect(u.numberOrNull(' 3 ')).toBe(3);
    expect(u.numberOrNull('0')).toBe(0);
    expect(u.numberOrNull('')).toBeNull();
    expect(u.numberOrNull(undefined)).toBeNull();
    expect(u.numberOrNull('abc')).toBeNull();
  });
  it('splits a list', () => {
    expect(u.splitList(' a, b ;c\n\n,d ')).toEqual(['a', 'b', 'c', 'd']);
    expect(u.splitList('')).toEqual([]);
    expect(u.splitList(null)).toEqual([]);
  });
  it('computes progress', () => {
    expect(u.progress(112, 304)).toBe(37);
    expect(u.progress(0, 100)).toBe(0);
    expect(u.progress(500, 100)).toBe(100);
    expect(u.progress(-5, 100)).toBe(0);
    expect(u.progress(10, null)).toBeNull();
    expect(u.progress(10, 0)).toBeNull();
    expect(u.progress(null, 100)).toBeNull();
    expect(u.progress(undefined, 100)).toBeNull();
  });
});

describe('cardModel and pickRandom', () => {
  const now = new Date(2026, 9, 5);
  const l = lib({
    people: {
      me: { share_reading: true, wishlist_todo: null, yearly_goal: 10 },
      sam: { share_reading: true, wishlist_todo: null, yearly_goal: null },
      shy: { share_reading: false, wishlist_todo: null, yearly_goal: null },
    },
    books: {
      a: book('a', { pages: 100, reading: { me: row('read', { finished: '2026-02-01' }), sam: row('read', { updated_at: '2026-10-01' }) } }),
      b: book('b', { pages: 200, reading: { me: row('read', { finished: '2025-12-31' }), shy: row('reading') } }),
      c: book('c', { reading: { me: row('read', { finished: '2026-05-01' }), sam: row('want') } }),
      d: book('d', { reading: { me: row('reading', { updated_at: '2026-01-01' }), sam: row('reading', { updated_at: '2026-10-03' }) } }),
      e: book('e', { reading: { me: row('reading', { updated_at: '2026-03-01' }) } }),
      f: book('f', { reading: { me: row('want') } }),
    },
  });

  it('collects reading, want, the goal and household activity', () => {
    const m = u.cardModel(l, 'me', now);
    expect(m.reading.map((r) => r.book.id)).toEqual(['e', 'd']);
    expect(m.want.map((b) => b.id)).toEqual(['f']);
    expect(m.goal).toEqual({ done: 2, goal: 10, pages: 100, year: 2026 });
    expect(m.household.map((a) => `${a.person.id}:${a.book.id}`)).toEqual(['sam:d', 'sam:a']);
  });

  it('limits the activity and has no goal with no person', () => {
    expect(u.cardModel(l, 'me', now, 1).household).toHaveLength(1);
    const m = u.cardModel(l, null, now);
    expect(m.goal.goal).toBeNull();
    expect(m.reading).toEqual([]);
    expect(m.household.map((a) => a.book.id).slice(0, 3)).toEqual(['d', 'a', 'e']);
    expect(m.household).toHaveLength(5);
    expect(u.cardModel(l, 'sam', now).goal.goal).toBeNull();
  });

  it('picks with a number from 0 to 1', () => {
    expect(u.pickRandom([], 0.5)).toBeNull();
    expect(u.pickRandom(['a', 'b', 'c'], 0)).toBe('a');
    expect(u.pickRandom(['a', 'b', 'c'], 0.5)).toBe('b');
    expect(u.pickRandom(['a', 'b', 'c'], 0.99)).toBe('c');
    expect(u.pickRandom(['a', 'b', 'c'], 1)).toBe('c');
  });
});

describe('scanTally, loansFor and csvRowCount', () => {
  it('counts scan results', () => {
    expect(
      u.scanTally([
        { result: 'added', book: { needs_details: false } },
        { result: 'added', book: { needs_details: true } },
        { result: 'moved', book: null },
        { result: 'duplicate', book: null },
        { result: 'skipped', book: null },
        { result: 'not_found', book: null },
      ]),
    ).toEqual({ added: 2, moved: 1, needs: 2, duplicate: 1, skipped: 1 });
    expect(u.scanTally([])).toEqual({ added: 0, moved: 0, needs: 0, duplicate: 0, skipped: 0 });
  });

  it('sorts loans for each tab', () => {
    const loans = [
      { id: 'a', direction: 'out', due: '2026-02-01', started: '2026-01-01', returned: null },
      { id: 'b', direction: 'out', due: null, started: '2026-01-01', returned: null },
      { id: 'c', direction: 'out', due: '2026-01-15', started: '2026-01-01', returned: null },
      { id: 'd', direction: 'in', due: null, started: '2026-01-02', returned: null },
      { id: 'e', direction: 'in', due: null, started: '2026-01-01', returned: null },
      { id: 'f', direction: 'out', due: null, started: '2026-01-01', returned: '2026-01-05' },
      { id: 'g', direction: 'in', due: null, started: '2026-01-01', returned: '2026-01-09' },
    ];
    expect(u.loansFor(loans, 'out').map((l) => l.id)).toEqual(['c', 'a', 'b']);
    expect(u.loansFor(loans, 'in').map((l) => l.id)).toEqual(['e', 'd']);
    expect(u.loansFor(loans, 'returned').map((l) => l.id)).toEqual(['g', 'f']);
  });

  it('counts CSV records after the header', () => {
    expect(u.csvRowCount('a,b\n1,2\n3,4\n')).toBe(2);
    expect(u.csvRowCount('a,b\r\n1,2\r\n3,4')).toBe(2);
    expect(u.csvRowCount('a,b\n"x\ny",2\n\n4,5\n')).toBe(2);
    expect(u.csvRowCount('a\n""\n')).toBe(1);
    expect(u.csvRowCount('a,b')).toBe(0);
    expect(u.csvRowCount('')).toBe(0);
    expect(u.csvRowCount('\r\n')).toBe(0);
  });
});

describe('CoverUrls', () => {
  const T0 = 1_000_000;
  const signer = () => {
    let n = 0;
    return vi.fn(async (path) => `${path}&authSig=${++n}`);
  };

  it('signs each path 1 time and gives the signed URL', async () => {
    const urls = new u.CoverUrls();
    const sign = signer();
    expect(urls.get('/c/a?v=1', T0)).toBeUndefined();
    expect(await urls.ensure(['/c/a?v=1', '/c/b?v=1', '/c/a?v=1'], sign, T0)).toBe(true);
    expect(sign).toHaveBeenCalledTimes(2);
    expect(urls.get('/c/a?v=1', T0)).toBe('/c/a?v=1&authSig=1');
    expect(urls.get('/c/b?v=1', T0)).toBe('/c/b?v=1&authSig=2');
    expect(await urls.ensure(['/c/a?v=1'], sign, T0 + 1000)).toBe(false);
    expect(sign).toHaveBeenCalledTimes(2);
  });

  it('signs again after the resign time and stops using a URL in its last minute', async () => {
    const urls = new u.CoverUrls();
    const sign = signer();
    await urls.ensure(['/c/a'], sign, T0);
    expect(await urls.ensure(['/c/a'], sign, T0 + u.COVER_RESIGN_MS - 1)).toBe(false);
    const life = u.COVER_SIGN_SECONDS * 1000;
    expect(urls.get('/c/a', T0 + life - 60_001)).toBe('/c/a&authSig=1');
    expect(urls.get('/c/a', T0 + life - 60_000)).toBeUndefined();
    expect(await urls.ensure(['/c/a'], sign, T0 + u.COVER_RESIGN_MS)).toBe(true);
    expect(urls.get('/c/a', T0 + u.COVER_RESIGN_MS)).toBe('/c/a&authSig=2');
    expect(u.COVER_RESIGN_MS).toBeLessThan(life - 60_000);
  });

  it('shares 1 sign between calls that overlap', async () => {
    const urls = new u.CoverUrls();
    let release;
    const sign = vi.fn(() => new Promise((r) => (release = r)));
    const first = urls.ensure(['/c/a'], sign, T0);
    const second = urls.ensure(['/c/a'], sign, T0);
    expect(sign).toHaveBeenCalledTimes(1);
    release('/c/a?authSig=x');
    expect(await first).toBe(true);
    expect(await second).toBe(true);
    expect(urls.get('/c/a', T0)).toBe('/c/a?authSig=x');
  });

  it('keeps no URL for a failed sign and tries again on the next call', async () => {
    const urls = new u.CoverUrls();
    const sign = vi.fn().mockRejectedValueOnce(new Error('no')).mockResolvedValueOnce('/c/a?ok');
    expect(await urls.ensure(['/c/a'], sign, T0)).toBe(false);
    expect(urls.get('/c/a', T0)).toBeUndefined();
    expect(await urls.ensure(['/c/a'], sign, T0)).toBe(true);
    expect(urls.get('/c/a', T0)).toBe('/c/a?ok');
  });

  it('keeps the old URL when a new sign fails', async () => {
    const urls = new u.CoverUrls();
    const sign = vi.fn().mockResolvedValueOnce('/c/a?one').mockRejectedValueOnce(new Error('no'));
    await urls.ensure(['/c/a'], sign, T0);
    expect(await urls.ensure(['/c/a'], sign, T0 + u.COVER_RESIGN_MS)).toBe(false);
    expect(urls.get('/c/a', T0 + u.COVER_RESIGN_MS)).toBe('/c/a?one');
  });

  it('forgets every URL on clear', async () => {
    const urls = new u.CoverUrls();
    await urls.ensure(['/c/a'], signer(), T0);
    urls.clear();
    expect(urls.get('/c/a', T0)).toBeUndefined();
  });

  it('gives false for no paths', async () => {
    const sign = vi.fn();
    expect(await new u.CoverUrls().ensure([], sign, T0)).toBe(false);
    expect(sign).not.toHaveBeenCalled();
  });
});
