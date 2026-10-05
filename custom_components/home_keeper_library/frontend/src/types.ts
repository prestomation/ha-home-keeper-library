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
  copy_count: number;
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
  /** Not in the reply for another person when the viewer is not an admin. */
  wishlist_todo?: string | null;
  yearly_goal: number | null;
}

/** 1 entry of `people` in the `get_state` reply. */
export interface RawPerson extends PersonSettings {
  person_id: string;
  name: string;
  entity_id: string | null;
}

export interface Person {
  id: string;
  name: string;
  share_reading: boolean;
  wishlist_todo: string | null;
  yearly_goal: number | null;
  /** The avatar color, from the person order (`utils.PERSON_COLORS`). */
  color: string;
}

/** The viewer: the person of the Home Assistant user, and the admin flag. */
export interface Me {
  person_id: string | null;
  name: string | null;
  is_admin: boolean;
}

/** The `home_keeper_library/get_state` reply (`projections.project_state`). */
export interface RawState {
  revision: number;
  rooms: Room[];
  bookcases: Bookcase[];
  shelves: Shelf[];
  books: Book[];
  copies: Copy[];
  loans: Loan[];
  /** The people of Home Assistant, by person id. */
  people: Record<string, RawPerson>;
  me: Me;
  currency: string;
  home_keeper: { tab: boolean };
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
  me: Me;
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
  callApi?: <T = unknown>(method: 'GET' | 'POST', path: string, parameters?: Record<string, unknown>) => Promise<T>;
}

/** Host API v1 that the Home Keeper panel gives to the tab. */
export interface TabHost {
  apiVersion: number;
  navigate(path: string, opts?: { replace?: boolean }): void;
  taskLink(taskId: string): string;
  applianceLink(id: string): string;
  /** Open a task in the panel. Home Keeper 0.30 and later. */
  openTask?(taskId: string): void;
  /** Open an appliance in the panel. Home Keeper 0.30 and later. */
  openAppliance?(id: string): void;
  showToast(text: string): void;
}

/** The result of `scan_isbn`. */
export interface ScanResult {
  result: 'added' | 'duplicate' | 'moved' | 'skipped' | 'not_found';
  book: Book | null;
  copy: Copy | null;
  existing_copies: Copy[];
  /** True when the scan added the first copy of a wishlist book. Missing reads as false. */
  from_wishlist?: boolean;
}

/** One row of the `import_csv` reply. */
export interface ImportRow {
  line: number;
  title: string;
  authors: string[];
  isbn: string | null;
  book_id: string | null;
  action: 'new' | 'existing' | 'title_match' | 'error';
  /** The error text, or '' for a row with no error. */
  message: string;
}

/** The `import_csv` reply. `rows` holds the first 200 rows; `truncated` says there are more. */
export interface ImportSummary {
  dry_run: boolean;
  counts: Record<string, number>;
  rows: ImportRow[];
  truncated: boolean;
}
