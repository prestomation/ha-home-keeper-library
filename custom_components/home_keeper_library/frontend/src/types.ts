// Shared types for the Home Keeper Library tab and card.
//
// The raw shapes match `home_keeper_library/get_state` (see the build spec,
// sections 2 and 5). `utils.normalizeState` turns the raw reply into `Lib`,
// which has arrays in display order.

export type ReadingStatus = 'want' | 'reading' | 'read' | 'dnf';
export type CopyFormat = 'hardcover' | 'paperback' | 'ebook' | 'audiobook' | 'other';
export type CopyCondition = 'new' | 'fine' | 'good' | 'fair' | 'poor';

export interface Room {
  id: string;
  name: string;
  area_id: string | null;
  order: number;
}

export interface Bookcase {
  id: string;
  room_id: string;
  name: string;
  note: string;
  order: number;
}

export interface Shelf {
  id: string;
  bookcase_id: string;
  name: string;
  order: number;
}

export interface ReadingRow {
  status: ReadingStatus | null;
  rating: number | null;
  page: number | null;
  started: string | null;
  finished: string | null;
  read_count: number;
  private_notes?: string;
  updated_at: string;
}

export interface Wishlist {
  person_id: string;
  buy: boolean;
  added_at: string;
  todo_uid: string | null;
  bought: boolean;
}

export interface Book {
  id: string;
  title: string;
  subtitle: string;
  authors: string[];
  isbn13: string | null;
  isbn10: string | null;
  publisher: string;
  published: string;
  pages: number | null;
  language: string | null;
  subjects: string[];
  series: { name: string; number: number | string | null } | null;
  description: string;
  tags: string[];
  shared_notes: string;
  openlibrary: { edition_key: string | null; work_key: string | null; cover_id: number | null } | null;
  cover: { kind: 'openlibrary' | 'custom' | 'none'; file: string | null };
  needs_details: boolean;
  created_at: string;
  updated_at: string;
  wishlist: Wishlist | null;
  reading: Record<string, ReadingRow>;
  owned: boolean;
  cover_url: string | null;
}

export interface Copy {
  id: string;
  book_id: string;
  shelf_id: string | null;
  format: CopyFormat;
  condition: CopyCondition | null;
  acquired: string | null;
  acquired_from?: string;
  price?: number | null;
  value?: number | null;
  signed: boolean;
  first_edition: boolean;
  note: string;
  created_at: string;
}

export interface Loan {
  id: string;
  direction: 'out' | 'in';
  book_id: string;
  copy_id: string | null;
  party?: string;
  person_id: string | null;
  format: CopyFormat | null;
  started: string;
  due: string | null;
  returned: string | null;
  note: string;
  hk_task_id: string | null;
}

export interface PersonSettings {
  share_reading: boolean;
  wishlist_todo: string | null;
  yearly_goal: number | null;
  name?: string;
}

export interface Person extends PersonSettings {
  id: string;
  name: string;
}

/** The raw `get_state` reply. Collections can be an id map or a list. */
export interface RawState {
  rooms?: Record<string, Room> | Room[];
  bookcases?: Record<string, Bookcase> | Bookcase[];
  shelves?: Record<string, Shelf> | Shelf[];
  books?: Record<string, Book> | Book[];
  copies?: Record<string, Copy> | Copy[];
  loans?: Record<string, Loan> | Loan[];
  people?: Record<string, PersonSettings>;
  me?: { person_id: string | null; is_admin: boolean };
  currency?: string;
  home_keeper?: { tab: boolean };
}

/** The normalized library that every view reads. */
export interface Lib {
  rooms: Room[];
  bookcases: Bookcase[];
  shelves: Shelf[];
  books: Book[];
  copies: Copy[];
  loans: Loan[];
  people: Person[];
  me: { person_id: string | null; is_admin: boolean };
  currency: string;
}

/** The subset of the `hass` object that the tab and the card use. */
export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface HomeAssistant {
  language?: string;
  locale?: { language?: string };
  states?: Record<string, HassEntity>;
  areas?: Record<string, { area_id: string; name: string }>;
  user?: { id: string; name: string; is_admin: boolean };
  connection: {
    sendMessagePromise<T = unknown>(msg: Record<string, unknown>): Promise<T>;
    subscribeMessage<T = unknown>(
      cb: (msg: T) => void,
      msg: Record<string, unknown>,
    ): Promise<() => void | Promise<void>>;
  };
  fetchWithAuth?: (path: string, init?: RequestInit) => Promise<Response>;
}

/** Host API v1 that the Home Keeper panel gives to the tab. */
export interface TabHost {
  apiVersion: number;
  navigate(path: string, opts?: { replace?: boolean }): void;
  taskLink(taskId: string): string;
  applianceLink(id: string): string;
  showToast(text: string): void;
}

/** The result of `scan_isbn`. */
export interface ScanResult {
  result: 'added' | 'duplicate' | 'moved' | 'skipped' | 'not_found';
  book: Book | null;
  copy: Copy | null;
  existing_copies: Copy[];
}

/** One row of the `import_csv` reply. */
export interface ImportRow {
  line?: number;
  title?: string;
  authors?: string[] | string;
  isbn?: string | null;
  shelf?: string;
  action?: string;
  status?: string | null;
  message?: string;
}

/** The `import_csv` reply. */
export interface ImportSummary {
  counts?: Record<string, number>;
  shelves?: Record<string, number>;
  rows?: ImportRow[];
  total?: number;
}
