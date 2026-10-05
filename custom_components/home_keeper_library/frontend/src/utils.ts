// Pure logic for the Home Keeper Library tab and card.
//
// Nothing here touches the DOM, the clock or Home Assistant. A caller gives the
// current time and the data. The mutation gate runs on this file, so each
// function has direct tests in `test/utils.test.js`.

import type {
  Book,
  Bookcase,
  Copy,
  Lib,
  Loan,
  Person,
  RawPerson,
  RawState,
  ReadingRow,
  ReadingStatus,
  Room,
  ScanResult,
  Shelf,
} from './types';

// ── Text ─────────────────────────────────────────────────────────────────────

/** Escape user text before it goes into innerHTML. */
export function escapeHTML(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Lower case with no accents, for search and sort keys. */
export function fold(value: unknown): string {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/** The initial letter of a name, upper case, or "?" for an empty name. */
export function initials(name: string): string {
  const first = name.trim().charAt(0);
  return first ? first.toUpperCase() : '?';
}

// ── State ────────────────────────────────────────────────────────────────────

/** A collection from the backend as a list. The backend can send a map or a list. */
export function asList<T>(value: Record<string, T> | T[] | null | undefined): T[] {
  if (!value) return [];
  return Array.isArray(value) ? [...value] : Object.values(value);
}

function byOrder<T extends { order: number; name: string }>(a: T, b: T): number {
  return (a.order ?? 0) - (b.order ?? 0) || a.name.localeCompare(b.name);
}

/** The avatar colors. A person gets the color of its place in the person order. */
export const PERSON_COLORS = ['#00695c', '#6a1b9a', '#c62828', '#1565c0', '#ef6c00', '#2e7d32', '#4527a0', '#ad1457'];

/**
 * The avatar color of the person at *index* in the person order. 2 people get
 * different colors while the palette has colors left.
 */
export function personColor(index: number): string {
  const n = PERSON_COLORS.length;
  return PERSON_COLORS[((index % n) + n) % n];
}

/** The people of a `get_state` reply, sorted by name, with their avatar colors. */
export function normalizePeople(raw: Record<string, RawPerson> | null | undefined): Person[] {
  return Object.entries(raw ?? {})
    .map(([id, row]) => ({
      id: row.person_id || id,
      name: row.name || id,
      share_reading: row.share_reading !== false,
      wishlist_todo: row.wishlist_todo ?? null,
      yearly_goal: row.yearly_goal ?? null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id))
    .map((p, i): Person => ({ ...p, color: personColor(i) }));
}

/** Turn the raw `get_state` reply into the `Lib` that the views read. */
export function normalizeState(raw: Partial<RawState>): Lib {
  const books = asList(raw.books).map((b) => ({
    ...b,
    authors: b.authors ?? [],
    tags: b.tags ?? [],
    subjects: b.subjects ?? [],
    reading: b.reading ?? {},
  }));
  return {
    rooms: asList(raw.rooms).sort(byOrder),
    bookcases: asList(raw.bookcases).sort(byOrder),
    shelves: asList(raw.shelves).sort(byOrder),
    books,
    copies: asList(raw.copies),
    loans: asList(raw.loans),
    people: normalizePeople(raw.people),
    me: { person_id: raw.me?.person_id ?? null, name: raw.me?.name ?? null, is_admin: raw.me?.is_admin === true },
    currency: raw.currency || 'USD',
  };
}

/** Person id to display name, read from the `person.*` entity attributes. */
export function personNames(
  states: Record<string, { entity_id: string; attributes: Record<string, unknown> }> | undefined,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const st of Object.values(states ?? {})) {
    if (!st.entity_id.startsWith('person.')) continue;
    const id = st.attributes.id;
    if (typeof id !== 'string' || !id) continue;
    const name = st.attributes.friendly_name;
    out[id] = typeof name === 'string' && name ? name : st.entity_id.slice(7);
  }
  return out;
}

// ── Index ────────────────────────────────────────────────────────────────────

export interface Index {
  room: Map<string, Room>;
  bookcase: Map<string, Bookcase>;
  shelf: Map<string, Shelf>;
  book: Map<string, Book>;
  copy: Map<string, Copy>;
  person: Map<string, Person>;
  copiesByBook: Map<string, Copy[]>;
  copiesByShelf: Map<string, Copy[]>;
  /** Loans that are not returned, by book id. */
  activeLoans: Map<string, Loan[]>;
  /** The open "out" loan of each copy. */
  loanByCopy: Map<string, Loan>;
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V): void {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

/** Build the lookup maps that the views use. */
export function buildIndex(lib: Lib): Index {
  const idx: Index = {
    room: new Map(lib.rooms.map((r) => [r.id, r])),
    bookcase: new Map(lib.bookcases.map((c) => [c.id, c])),
    shelf: new Map(lib.shelves.map((s) => [s.id, s])),
    book: new Map(lib.books.map((b) => [b.id, b])),
    copy: new Map(lib.copies.map((c) => [c.id, c])),
    person: new Map(lib.people.map((p) => [p.id, p])),
    copiesByBook: new Map(),
    copiesByShelf: new Map(),
    activeLoans: new Map(),
    loanByCopy: new Map(),
  };
  for (const copy of lib.copies) {
    push(idx.copiesByBook, copy.book_id, copy);
    push(idx.copiesByShelf, copy.shelf_id ?? '', copy);
  }
  for (const loan of lib.loans) {
    if (loan.returned) continue;
    push(idx.activeLoans, loan.book_id, loan);
    if (loan.direction === 'out' && loan.copy_id) idx.loanByCopy.set(loan.copy_id, loan);
  }
  return idx;
}

/** The room, bookcase and shelf of a shelf id. Missing parts are null. */
export function shelfPath(
  idx: Index,
  shelfId: string | null | undefined,
): { room: Room | null; bookcase: Bookcase | null; shelf: Shelf | null } {
  const shelf = shelfId ? (idx.shelf.get(shelfId) ?? null) : null;
  const bookcase = shelf ? (idx.bookcase.get(shelf.bookcase_id) ?? null) : null;
  const room = bookcase ? (idx.room.get(bookcase.room_id) ?? null) : null;
  return { room, bookcase, shelf };
}

/** "Room › Bookcase › Shelf" for a shelf id, or '' for no shelf. */
export function locationLabel(idx: Index, shelfId: string | null | undefined): string {
  const { room, bookcase, shelf } = shelfPath(idx, shelfId);
  return [room?.name, bookcase?.name, shelf?.name].filter(Boolean).join(' › ');
}

/** "Room · Shelf", the short form for a book tile. */
export function shortLocation(idx: Index, shelfId: string | null | undefined): string {
  const { room, shelf } = shelfPath(idx, shelfId);
  return [room?.name, shelf?.name].filter(Boolean).join(' · ');
}

/** The shelves in display order: room, then bookcase, then shelf. */
export function orderedShelves(lib: Lib): Shelf[] {
  const out: Shelf[] = [];
  for (const room of lib.rooms) {
    for (const bc of lib.bookcases) {
      if (bc.room_id !== room.id) continue;
      for (const sh of lib.shelves) if (sh.bookcase_id === bc.id) out.push(sh);
    }
  }
  return out;
}

/** The shelf after *shelfId* in display order, or null at the end. */
export function nextShelf(lib: Lib, shelfId: string | null): Shelf | null {
  const list = orderedShelves(lib);
  const at = list.findIndex((s) => s.id === shelfId);
  return at >= 0 && at + 1 < list.length ? list[at + 1] : null;
}

// ── Routes ───────────────────────────────────────────────────────────────────

export type View =
  | 'books'
  | 'book'
  | 'shelves'
  | 'loans'
  | 'wishlist'
  | 'scan'
  | 'import'
  | 'settings';

export interface TabRoute {
  view: View;
  /** The book id for `book`, the room id for `shelves`, else null. */
  id: string | null;
  /** The query string values that are not the default. */
  query: Record<string, string>;
}

/** The default value of each query key. A default value is left out of the URL. */
export const QUERY_DEFAULTS: Record<string, string> = {
  status: 'all',
  owned: 'yes',
  sort: 'author',
  view: 'grid',
  tab: 'out',
  mode: 'shelf',
  step: 'setup',
};

/** The query keys that each view keeps, in URL order. */
const VIEW_QUERY: Record<View, string[]> = {
  books: ['q', 'status', 'room', 'shelf', 'reader', 'subject', 'owned', 'sort', 'view'],
  book: [],
  shelves: [],
  loans: ['tab'],
  wishlist: [],
  scan: ['shelf', 'mode', 'step'],
  import: [],
  settings: [],
};

function parseQuery(search: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of new URLSearchParams(search)) out[key] = value;
  return out;
}

function cleanQuery(view: View, query: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const key of VIEW_QUERY[view]) {
    const value = query[key];
    if (value && value !== QUERY_DEFAULTS[key]) out[key] = value;
  }
  return out;
}

/**
 * Parse the tab path (after `/home-keeper/library`) into a route.
 *
 * The path can hold the query string. If it holds none, *search* gives it.
 * An unknown path gives the book list.
 */
export function parseRoute(path: string | undefined, search = ''): TabRoute {
  const raw = path ?? '';
  const q = raw.indexOf('?');
  const pathname = q >= 0 ? raw.slice(0, q) : raw;
  const query = parseQuery(q >= 0 ? raw.slice(q + 1) : search);
  const parts = pathname.split('/').filter(Boolean).map(decodeURIComponent);
  const head = parts[0] ?? 'books';
  let view: View = 'books';
  let id: string | null = null;
  if (head === 'books' && parts[1]) {
    view = 'book';
    id = parts[1];
  } else if (head === 'shelves') {
    view = 'shelves';
    id = parts[1] ?? null;
  } else if (['loans', 'wishlist', 'scan', 'import', 'settings'].includes(head)) {
    view = head as View;
  }
  return { view, id, query: cleanQuery(view, query) };
}

/** Build the tab path for a route. The inverse of `parseRoute`. */
export function buildPath(route: { view: View; id?: string | null; query?: Record<string, string> }): string {
  const id = route.id ? `/${encodeURIComponent(route.id)}` : '';
  let path: string;
  if (route.view === 'book') path = `/books${id}`;
  else if (route.view === 'shelves') path = `/shelves${id}`;
  else path = `/${route.view}`;
  const query = cleanQuery(route.view, route.query ?? {});
  const search = new URLSearchParams(query).toString();
  return search ? `${path}?${search}` : path;
}

/** A copy of *query* with *key* set to *value*. An empty value removes the key. */
export function withQuery(
  query: Record<string, string>,
  key: string,
  value: string | null | undefined,
): Record<string, string> {
  const out = { ...query };
  if (value) out[key] = value;
  else delete out[key];
  return out;
}

// ── Book filters ─────────────────────────────────────────────────────────────

export type StatusFilter = 'all' | 'unread' | 'reading' | 'read' | 'needs';
export const STATUS_FILTERS: StatusFilter[] = ['all', 'unread', 'reading', 'read', 'needs'];
export type SortKey = 'author' | 'title' | 'added' | 'published' | 'rating';
export const SORT_KEYS: SortKey[] = ['author', 'title', 'added', 'published', 'rating'];

export interface BookFilters {
  q: string;
  status: StatusFilter;
  room: string;
  shelf: string;
  reader: string;
  subject: string;
  owned: 'yes' | 'no' | 'all';
  sort: SortKey;
  view: 'grid' | 'rows';
}

function oneOf<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** Read the book filters from a route query. An unknown value reads as the default. */
export function readFilters(query: Record<string, string>): BookFilters {
  return {
    q: query.q ?? '',
    status: oneOf(query.status, STATUS_FILTERS, 'all'),
    room: query.room ?? '',
    shelf: query.shelf ?? '',
    reader: query.reader ?? '',
    subject: query.subject ?? '',
    owned: oneOf(query.owned, ['yes', 'no', 'all'] as const, 'yes'),
    sort: oneOf(query.sort, SORT_KEYS, 'author'),
    view: oneOf(query.view, ['grid', 'rows'] as const, 'grid'),
  };
}

/** True if a filter other than sort, layout and the owned default narrows the list. */
export function hasFilters(f: BookFilters): boolean {
  return Boolean(f.q || f.room || f.shelf || f.reader || f.subject || f.status !== 'all' || f.owned !== 'yes');
}

/** The reading row of *personId* for *book*, or null. */
export function readingOf(book: Book, personId: string | null | undefined): ReadingRow | null {
  if (!personId) return null;
  return book.reading?.[personId] ?? null;
}

/** The status of *personId* for *book*, or null. */
export function statusOf(book: Book, personId: string | null | undefined): ReadingStatus | null {
  return readingOf(book, personId)?.status ?? null;
}

/** The text that a search reads for a book. */
export function searchText(book: Book, personId: string | null): string {
  const parts = [
    book.title,
    book.subtitle,
    ...book.authors,
    book.isbn13,
    book.isbn10,
    book.series?.name,
    book.shared_notes,
    ...book.tags,
    readingOf(book, personId)?.private_notes,
  ];
  return fold(parts.filter(Boolean).join(' \n '));
}

/** True if every word of *q* is in the search text of *book*. */
export function matchesSearch(book: Book, q: string, personId: string | null): boolean {
  const words = fold(q).split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const text = searchText(book, personId);
  const digits = text.replace(/-/g, '');
  return words.every((w) => text.includes(w) || (/^[\d-]+x?$/.test(w) && digits.includes(w.replace(/-/g, ''))));
}

export interface FilterContext {
  idx: Index;
  me: string | null;
}

function inPlace(book: Book, f: BookFilters, ctx: FilterContext): boolean {
  if (!f.room && !f.shelf) return true;
  const copies = ctx.idx.copiesByBook.get(book.id) ?? [];
  return copies.some((c) => {
    if (f.shelf === 'none') return !c.shelf_id;
    if (f.shelf && c.shelf_id !== f.shelf) return false;
    if (f.room && shelfPath(ctx.idx, c.shelf_id).room?.id !== f.room) return false;
    return true;
  });
}

function matchesStatus(book: Book, status: StatusFilter, me: string | null): boolean {
  const mine = statusOf(book, me);
  switch (status) {
    case 'unread':
      return mine !== 'read';
    case 'reading':
      return mine === 'reading';
    case 'read':
      return mine === 'read';
    case 'needs':
      return book.needs_details;
    default:
      return true;
  }
}

/** True if *book* passes every filter except the status filter. */
export function matchesBase(book: Book, f: BookFilters, ctx: FilterContext): boolean {
  if (f.owned === 'yes' && !book.owned) return false;
  if (f.owned === 'no' && book.owned) return false;
  if (f.subject && !book.subjects.includes(f.subject)) return false;
  if (f.reader && statusOf(book, f.reader) !== 'read') return false;
  if (!inPlace(book, f, ctx)) return false;
  return matchesSearch(book, f.q, ctx.me);
}

/** The books that pass all the filters, sorted. */
export function filterBooks(books: Book[], f: BookFilters, ctx: FilterContext): Book[] {
  const out = books.filter((b) => matchesBase(b, f, ctx) && matchesStatus(b, f.status, ctx.me));
  return sortBooks(out, f.sort, ctx.me);
}

/** The count for each status chip, with the other filters applied. */
export function statusCounts(books: Book[], f: BookFilters, ctx: FilterContext): Record<StatusFilter, number> {
  const counts: Record<StatusFilter, number> = { all: 0, unread: 0, reading: 0, read: 0, needs: 0 };
  for (const book of books) {
    if (!matchesBase(book, f, ctx)) continue;
    for (const s of STATUS_FILTERS) if (matchesStatus(book, s, ctx.me)) counts[s] += 1;
  }
  return counts;
}

/** The sort key of an author name: the last word, then the full name. */
export function authorKey(name: string | undefined): string {
  const words = fold(name).trim().split(/\s+/).filter(Boolean);
  // A book with no author sorts after every book with an author.
  if (!words.length) return '\uffff';
  return `${words[words.length - 1]} ${words.join(' ')}`;
}

/** The year in a free text date such as "1969" or "March 2001", or null. */
export function yearOf(value: string | null | undefined): number | null {
  const m = String(value ?? '').match(/\b(\d{4})\b/);
  return m ? Number(m[1]) : null;
}

function seriesNumber(book: Book): number {
  const n = Number(book.series?.number);
  return Number.isFinite(n) ? n : 0;
}

/** Sort books by *key*. Title is the tiebreak for every key. */
export function sortBooks(books: Book[], key: SortKey, me: string | null): Book[] {
  const byTitle = (a: Book, b: Book) => fold(a.title).localeCompare(fold(b.title));
  const cmp: Record<SortKey, (a: Book, b: Book) => number> = {
    author: (a, b) =>
      authorKey(a.authors[0]).localeCompare(authorKey(b.authors[0])) ||
      fold(a.series?.name).localeCompare(fold(b.series?.name)) ||
      seriesNumber(a) - seriesNumber(b),
    title: () => 0,
    added: (a, b) => String(b.created_at).localeCompare(String(a.created_at)),
    published: (a, b) => (yearOf(a.published) ?? 99999) - (yearOf(b.published) ?? 99999),
    rating: (a, b) => (readingOf(b, me)?.rating ?? 0) - (readingOf(a, me)?.rating ?? 0),
  };
  return [...books].sort((a, b) => cmp[key](a, b) || byTitle(a, b));
}

/** The subjects of all books, sorted, with no duplicates. */
export function allSubjects(books: Book[]): string[] {
  return [...new Set(books.flatMap((b) => b.subjects))].sort((a, b) => a.localeCompare(b));
}

// ── ISBN ─────────────────────────────────────────────────────────────────────

/** Digits and a final X only. */
export function cleanIsbn(value: string): string {
  return String(value ?? '')
    .toUpperCase()
    .replace(/[^0-9X]/g, '');
}

/** True for an ISBN-10 with a correct check digit. */
export function isValidIsbn10(value: string): boolean {
  if (!/^\d{9}[\dX]$/.test(value)) return false;
  let sum = 0;
  for (let i = 0; i < 10; i++) {
    const d = value[i] === 'X' ? 10 : Number(value[i]);
    sum += d * (10 - i);
  }
  return sum % 11 === 0;
}

/** The EAN-13 check digit of the first 12 digits. */
export function ean13Check(first12: string): number {
  let sum = 0;
  for (let i = 0; i < 12; i++) sum += Number(first12[i]) * (i % 2 ? 3 : 1);
  return (10 - (sum % 10)) % 10;
}

/** True for an ISBN-13 (978 or 979) with a correct check digit. */
export function isValidIsbn13(value: string): boolean {
  if (!/^97[89]\d{10}$/.test(value)) return false;
  return ean13Check(value.slice(0, 12)) === Number(value[12]);
}

/** Convert a valid ISBN-10 to ISBN-13. */
export function isbn10to13(isbn10: string): string {
  const core = `978${isbn10.slice(0, 9)}`;
  return `${core}${ean13Check(core)}`;
}

/** An ISBN-13 from a scanned EAN-13 code, or null if the code is not a book. */
export function isbnFromEan(code: string): string | null {
  const digits = String(code ?? '').trim();
  return isValidIsbn13(digits) ? digits : null;
}

/** A typed ISBN as ISBN-13, or null if it is not a valid ISBN-10 or ISBN-13. */
export function normalizeIsbn(value: string): string | null {
  const v = cleanIsbn(value);
  if (v.length === 13) return isValidIsbn13(v) ? v : null;
  if (v.length === 10) return isValidIsbn10(v) ? isbn10to13(v) : null;
  return null;
}

/**
 * A gate for scanned codes: the same code is let through again only after
 * *windowMs*. The camera reads a barcode many times a second.
 */
export function makeCodeGate(windowMs: number): (code: string, nowMs: number) => boolean {
  const seen = new Map<string, number>();
  return (code, nowMs) => {
    const last = seen.get(code);
    if (last !== undefined && nowMs - last < windowMs) return false;
    seen.set(code, nowMs);
    return true;
  };
}

/** Call *fn* once, *ms* after the last call. `cancel` stops a pending call. */
export function debounce<A extends unknown[]>(
  fn: (...args: A) => void,
  ms: number,
): ((...args: A) => void) & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const wrapped = (...args: A) => {
    if (timer !== undefined) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = undefined;
      fn(...args);
    }, ms);
  };
  wrapped.cancel = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  };
  return wrapped;
}

// ── Drawing ──────────────────────────────────────────────────────────────────

/** FNV-1a hash of a string, as an unsigned 32-bit integer. */
export function hash(value: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Cover colors: a background and the ink for the title on it. */
export const COVER_COLORS: Array<[string, string]> = [
  ['#2f3e46', '#f1e9d2'],
  ['#1d4e89', '#fdf6e3'],
  ['#b5651d', '#fff8ec'],
  ['#5c2a6b', '#f6e9ff'],
  ['#264d3b', '#e8f3e0'],
  ['#8d6e3f', '#fffaf0'],
  ['#0f3d56', '#e3f2fd'],
  ['#7a2e2e', '#fdecea'],
  ['#3b6e3b', '#f1f8e9'],
  ['#a33b5c', '#fff0f5'],
  ['#37474f', '#eceff1'],
  ['#4e342e', '#efebe9'],
];

/** The cover colors of a book id. The same id always gives the same colors. */
export function coverColors(id: string): { bg: string; ink: string } {
  const [bg, ink] = COVER_COLORS[hash(id) % COVER_COLORS.length];
  return { bg, ink };
}

export interface Spine {
  id: string;
  title: string;
  w: number;
  h: number;
  color: string;
}

/**
 * The spines to draw for the books on a shelf. Width comes from the page count,
 * height and color from the book id.
 */
export function spines(books: Book[], max = 60): Spine[] {
  return books.slice(0, max).map((b) => {
    const h = hash(b.id);
    const w = b.pages ? Math.min(22, Math.max(8, Math.round(6 + b.pages / 40))) : 8 + (h % 10);
    return {
      id: b.id,
      title: b.title,
      w,
      h: 56 + ((h >>> 8) % 27),
      color: COVER_COLORS[h % COVER_COLORS.length][0],
    };
  });
}

// ── Dates and numbers ────────────────────────────────────────────────────────

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/** The local date of *now* as YYYY-MM-DD. */
export function todayISO(now: Date): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Days from date *a* to date *b* (both YYYY-MM-DD). Positive if *b* is later. */
export function daysBetween(a: string, b: string): number {
  const ms = Date.parse(`${b.slice(0, 10)}T00:00:00Z`) - Date.parse(`${a.slice(0, 10)}T00:00:00Z`);
  return Math.round(ms / 86400000);
}

export type DueKind = 'none' | 'overdue' | 'today' | 'soon' | 'later';

/** How a due date relates to *today*. "soon" is 1 to 3 days ahead. */
export function dueState(due: string | null | undefined, today: string): { kind: DueKind; days: number } {
  if (!due) return { kind: 'none', days: 0 };
  const days = daysBetween(today, due);
  if (days < 0) return { kind: 'overdue', days: -days };
  if (days === 0) return { kind: 'today', days: 0 };
  return { kind: days <= 3 ? 'soon' : 'later', days };
}

/** A whole number from a form value, or null for an empty or bad value. */
export function intOrNull(value: unknown): number | null {
  const s = String(value ?? '').trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isInteger(n) ? n : null;
}

/** A number from a form value, or null for an empty or bad value. */
export function numberOrNull(value: unknown): number | null {
  const s = String(value ?? '').trim().replace(',', '.');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** A comma list from a form as a list of trimmed values. */
export function splitList(value: string): string[] {
  return String(value ?? '')
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Reading progress from 0 to 100, or null with no page count. */
export function progress(page: number | null | undefined, pages: number | null | undefined): number | null {
  if (!pages || page == null) return null;
  return Math.max(0, Math.min(100, Math.round((page / pages) * 100)));
}

// ── Card ─────────────────────────────────────────────────────────────────────

export interface Activity {
  person: Person;
  book: Book;
  row: ReadingRow;
}

export interface CardModel {
  reading: Array<{ book: Book; row: ReadingRow }>;
  want: Book[];
  goal: { done: number; goal: number | null; pages: number; year: number };
  household: Activity[];
}

/** The data that the card shows for *personId* at *now*. */
export function cardModel(lib: Lib, personId: string | null, now: Date, maxActivity = 5): CardModel {
  const year = now.getFullYear();
  const reading: CardModel['reading'] = [];
  const want: Book[] = [];
  let done = 0;
  let pages = 0;
  const household: Activity[] = [];
  const person = new Map(lib.people.map((p) => [p.id, p]));
  for (const book of lib.books) {
    for (const [pid, row] of Object.entries(book.reading)) {
      if (pid === personId) {
        if (row.status === 'reading') reading.push({ book, row });
        if (row.status === 'want') want.push(book);
        if (row.status === 'read' && yearOf(row.finished) === year) {
          done += 1;
          pages += book.pages ?? 0;
        }
      } else if (row.status && row.status !== 'want' && person.get(pid)?.share_reading) {
        household.push({ person: person.get(pid)!, book, row });
      }
    }
  }
  household.sort((a, b) => String(b.row.updated_at).localeCompare(String(a.row.updated_at)));
  reading.sort((a, b) => String(b.row.updated_at).localeCompare(String(a.row.updated_at)));
  return {
    reading,
    want,
    goal: { done, goal: personId ? (person.get(personId)?.yearly_goal ?? null) : null, pages, year },
    household: household.slice(0, maxActivity),
  };
}

/** One item of *items*, picked with *rnd* (0 <= rnd < 1), or null for an empty list. */
export function pickRandom<T>(items: T[], rnd: number): T | null {
  if (!items.length) return null;
  return items[Math.min(items.length - 1, Math.floor(rnd * items.length))];
}

// ── Scan ─────────────────────────────────────────────────────────────────────

export interface ScanTally {
  added: number;
  moved: number;
  needs: number;
  duplicate: number;
  skipped: number;
}

/** Count the results of a scan session. */
export function scanTally(results: Array<Pick<ScanResult, 'result' | 'book'>>): ScanTally {
  const out: ScanTally = { added: 0, moved: 0, needs: 0, duplicate: 0, skipped: 0 };
  for (const r of results) {
    if (r.result === 'added') out.added += 1;
    else if (r.result === 'moved') out.moved += 1;
    else if (r.result === 'duplicate') out.duplicate += 1;
    else if (r.result === 'skipped') out.skipped += 1;
    if (r.result === 'not_found' || r.book?.needs_details) out.needs += 1;
  }
  return out;
}

// ── Loans ────────────────────────────────────────────────────────────────────

export type LoanTab = 'out' | 'in' | 'returned';

/** The loans of a tab. Open loans sort by due date, returned ones newest first. */
export function loansFor(loans: Loan[], tab: LoanTab): Loan[] {
  if (tab === 'returned') {
    return loans
      .filter((l) => l.returned)
      .sort((a, b) => String(b.returned).localeCompare(String(a.returned)));
  }
  return loans
    .filter((l) => !l.returned && l.direction === tab)
    .sort((a, b) => (a.due ?? '9999').localeCompare(b.due ?? '9999') || a.started.localeCompare(b.started));
}

/** The book value of a room: the sum of copy values. */
export function roomValue(lib: Lib, idx: Index, roomId: string): number {
  let sum = 0;
  for (const copy of lib.copies) {
    if (shelfPath(idx, copy.shelf_id).room?.id === roomId) sum += copy.value ?? 0;
  }
  return sum;
}

// ── Import ───────────────────────────────────────────────────────────────────

/** The number of data rows in a CSV text: records after the header, not lines. */
export function csvRowCount(text: string): number {
  let rows = 0;
  let quoted = false;
  let filled = false;
  for (const c of text) {
    if (c === '"') {
      quoted = !quoted;
      filled = true;
    } else if (c === '\n' && !quoted) {
      if (filled) rows += 1;
      filled = false;
    } else if (c !== '\r') {
      filled = true;
    }
  }
  if (filled) rows += 1;
  return Math.max(0, rows - 1);
}

// ── Covers ───────────────────────────────────────────────────────────────────

/** The life of a signed cover URL in seconds: the `expires` of `auth/sign_path`. */
export const COVER_SIGN_SECONDS = 3600;

/** After this time a cover is signed again, well before its URL expires. */
export const COVER_RESIGN_MS = 45 * 60 * 1000;

/** A signed URL is not used in its last minute, so an image does not load a dead URL. */
const COVER_USE_MS = COVER_SIGN_SECONDS * 1000 - 60 * 1000;

/**
 * Signed cover URLs. The cover view needs a signed-in user, and an `<img>` cannot
 * send the token, so each cover path is signed with `auth/sign_path` before the
 * render that shows it. An entry is reused until it is old, and calls for the
 * same path while a sign runs share that sign. A failed sign keeps the old URL.
 */
export class CoverUrls {
  private readonly _entries = new Map<string, { url: string; at: number }>();
  private readonly _pending = new Map<string, Promise<boolean>>();

  /** Forget every signed URL. */
  clear(): void {
    this._entries.clear();
  }

  /** The signed URL of *path* at *now*, or undefined if it has none that is usable. */
  get(path: string, now: number): string | undefined {
    const entry = this._entries.get(path);
    return entry && now - entry.at < COVER_USE_MS ? entry.url : undefined;
  }

  /** Sign each path that has no fresh URL. Resolves to true if a URL was signed. */
  async ensure(paths: Iterable<string>, sign: (path: string) => Promise<string>, now: number): Promise<boolean> {
    const jobs: Array<Promise<boolean>> = [];
    for (const path of new Set(paths)) {
      const entry = this._entries.get(path);
      if (entry && now - entry.at < COVER_RESIGN_MS) continue;
      let job = this._pending.get(path);
      if (!job) {
        job = sign(path)
          .then(
            (url) => {
              this._entries.set(path, { url, at: now });
              return true;
            },
            // Stryker disable next-line ArrowFunction: undefined and false both read as "not signed" in .some(Boolean).
            () => false,
          )
          .finally(() => this._pending.delete(path));
        this._pending.set(path, job);
      }
      jobs.push(job);
    }
    return (await Promise.all(jobs)).some(Boolean);
  }
}
