// The `home-keeper-library-tab` element. The Home Keeper panel loads it at
// `/home-keeper/library/...` and gives it `hass`, `narrow`, `route` and `host`
// (host API v1, build spec section 10).
//
// The URL is the source of truth. The `route` setter is the only place that
// changes the view. Every navigation goes through `host.navigate`. The view is
// 1 HTML string per render, and 1 delegated listener per event type reads the
// `data-act`, `data-chg`, `data-input` and `data-form` attributes.

import { errorText, LibraryApi, MAX_COVER_BYTES, MAX_IMPORT_BYTES, type Fields } from './api';
import { renderKeepFocus } from './dom';
import { setLanguage, t, tn } from './i18n';
import { ensureMarkdown, wireMarkdown } from './markdown';
import { wireCovers } from './markup';
import { Scanner } from './scanner';
import { STYLES } from './styles';
import { booksPath, renderBook, renderBooks } from './tab-books';
import { renderDialog, type Dialog, type DialogState } from './tab-dialogs';
import { renderImport } from './tab-import';
import { renderLoans, renderSettings, renderWishlist } from './tab-lists';
import { cameraBlocked, isBorrowedMode, renderScan, routeShelf } from './tab-scan';
import { renderShelves } from './tab-shelves';
import type { ImportState, ScanEntry, UiState, ViewCtx } from './tab-types';
import type { Book, HomeAssistant, ImportSummary, Lib, RawState, ReadingStatus, ScanResult, TabHost } from './types';
import {
  buildIndex,
  buildPath,
  csvRowCount,
  debounce,
  escapeHTML,
  intOrNull,
  isbnFromEan,
  makeCodeGate,
  normalizeIsbn,
  normalizeState,
  numberOrNull,
  parseRoute,
  readFilters,
  readingOf,
  shelfPath,
  splitList,
  todayISO,
  withQuery,
  type Index,
  type TabRoute,
} from './utils';
import { PANEL_VERSION } from 'panel-version';

const PAGE = 240;

function freshImport(personId: string | null): ImportState {
  return {
    source: 'goodreads',
    personId,
    shelfId: '',
    fileName: '',
    content: '',
    rowCount: 0,
    importNotes: true,
    replaceReading: false,
    summary: null,
    busy: false,
    error: '',
    done: false,
  };
}

function freshUi(): UiState {
  return {
    limit: PAGE,
    notesTab: 'shared',
    editNotes: false,
    readingPerson: null,
    scan: {
      method: 'camera',
      roomId: null,
      results: [],
      manualOpen: false,
      markRead: false,
      cameraError: '',
      torch: null,
      party: '',
      personId: null,
      due: '',
      addTask: true,
    },
    import: freshImport(null),
    todoEntities: [],
    exportFormat: 'goodreads',
    exportPerson: '',
  };
}

/** The id of a created object from a command reply (`{id}` or `{<noun>: {id}}`). */
export function replyId(res: unknown, noun: string): string | null {
  const r = res as Record<string, unknown> | null;
  if (!r || typeof r !== 'object') return null;
  if (typeof r.id === 'string') return r.id;
  const inner = r[noun] as { id?: unknown } | undefined;
  return inner && typeof inner.id === 'string' ? inner.id : null;
}

export class HomeKeeperLibraryTab extends HTMLElement {
  private _hass?: HomeAssistant;
  private _api?: LibraryApi;
  private _host: TabHost | null = null;
  private _route: TabRoute = parseRoute('');
  private _lib: Lib | null = null;
  private _idx: Index | null = null;
  private _error = '';
  private _lang = '';
  private _unsub?: () => void | Promise<void>;
  private _subscribing = false;
  private _refreshing: Promise<void> | null = null;
  private _again = false;
  private _dryRunSeq = 0;
  private _ui: UiState = freshUi();
  private _dialog: DialogState | null = null;
  private _scanner: Scanner | null = null;
  private _stopTimer: ReturnType<typeof setTimeout> | undefined;
  private _gate = makeCodeGate(3000);
  private _scanKey = 0;
  private _booksPath = '/books';
  private _todoLoaded = false;
  private readonly _root: ShadowRoot;
  private readonly _main: HTMLElement;
  private readonly _dlg: HTMLElement;
  private readonly _search = debounce((q: string) => this._setFilter('q', q), 250);

  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'open' });
    this._root.innerHTML = `<style>${STYLES}</style><div class="hkl-root" id="main"></div><div id="dlg"></div>`;
    this._main = this._root.getElementById('main')!;
    this._dlg = this._root.getElementById('dlg')!;
    this._root.addEventListener('click', (ev) => this._onClick(ev as MouseEvent));
    this._root.addEventListener('change', (ev) => void this._onChange(ev));
    this._root.addEventListener('input', (ev) => this._onInput(ev));
    this._root.addEventListener('submit', (ev) => this._onSubmit(ev as SubmitEvent));
    this._root.addEventListener('keydown', (ev) => this._onKey(ev as KeyboardEvent));
  }

  // ── Host properties ────────────────────────────────────────────────────────

  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    if (this._api) this._api.setHass(hass);
    else this._api = new LibraryApi(hass);
    const lang = hass.locale?.language || hass.language || 'en';
    if (lang !== this._lang) {
      this._lang = lang;
      setLanguage(lang);
      if (!first) this._render();
    }
    if (first) void this._start();
  }
  get hass(): HomeAssistant | undefined {
    return this._hass;
  }

  set narrow(_value: boolean) {
    // CSS picks the layout. The tab accepts `narrow` for the host API only.
  }

  set host(host: TabHost | null) {
    this._host = host;
  }
  get host(): TabHost | null {
    return this._host;
  }

  set route(route: { path: string }) {
    const prev = this._route;
    const search = route.path.includes('?') ? '' : (globalThis.location?.search ?? '');
    this._route = parseRoute(route.path, search);
    if (this._route.view === 'books') this._booksPath = buildPath(this._route);
    if (prev.view !== this._route.view || prev.id !== this._route.id) {
      this._ui.editNotes = false;
      this._ui.limit = PAGE;
      if (this._route.view === 'import' && prev.view !== 'import') this._ui.import = freshImport(this._lib?.me.person_id ?? null);
    }
    if (prev.view === 'book' && prev.id !== this._route.id) this._ui.readingPerson = null;
    this._syncScanner();
    if (this._route.view === 'settings') void this._loadTodo();
    this._render();
  }
  get route(): { path: string } {
    return { path: buildPath(this._route) };
  }

  connectedCallback(): void {
    if (this._hass && !this._unsub && !this._subscribing) void this._subscribe();
    // Home Keeper redraws its panel when the data changes. The redraw moves this
    // tab out of the page and back in. Keep the camera, or start it again.
    clearTimeout(this._stopTimer);
    this._stopTimer = undefined;
    this._scanner?.resume();
    this._syncScanner();
  }

  disconnectedCallback(): void {
    void this._unsub?.();
    this._unsub = undefined;
    this._search.cancel();
    // Stop the camera only if the tab does not come back at once.
    clearTimeout(this._stopTimer);
    this._stopTimer = setTimeout(() => {
      this._stopTimer = undefined;
      if (!this.isConnected) this._stopScanner();
    }, 0);
  }

  // ── Data ───────────────────────────────────────────────────────────────────

  private async _start(): Promise<void> {
    this._render();
    void ensureMarkdown().then((ok) => ok && this._render());
    await this._refresh();
    if (this._route.view === 'settings') void this._loadTodo();
    await this._subscribe();
  }

  private async _subscribe(): Promise<void> {
    if (!this._api || this._unsub || this._subscribing) return;
    this._subscribing = true;
    try {
      this._unsub = await this._api.subscribe(() => void this._refresh());
      // The tab can leave the page while the subscription starts.
      if (!this.isConnected) {
        void this._unsub();
        this._unsub = undefined;
      }
    } catch (err) {
      this._error = errorText(err);
    } finally {
      this._subscribing = false;
    }
  }

  /** Fetch `get_state`. Calls during a fetch run 1 more fetch after it. */
  private _refresh(): Promise<void> {
    if (this._refreshing) {
      this._again = true;
      return this._refreshing;
    }
    this._refreshing = (async () => {
      do {
        this._again = false;
        try {
          this._setState(await this._api!.getState());
          this._error = '';
        } catch (err) {
          this._error = errorText(err);
        }
        this._render();
      } while (this._again);
    })().finally(() => {
      this._refreshing = null;
    });
    return this._refreshing;
  }

  private _setState(raw: RawState): void {
    this._lib = normalizeState(raw);
    this._idx = buildIndex(this._lib);
    if (!this._ui.import.personId) this._ui.import.personId = this._lib.me.person_id;
  }

  private async _loadTodo(): Promise<void> {
    if (this._todoLoaded || !this._api) return;
    this._todoLoaded = true;
    try {
      this._ui.todoEntities = await this._api.listTodoEntities();
      this._render();
    } catch {
      this._todoLoaded = false;
    }
  }

  /** Run a command, show a toast, then fetch the state. Returns true if the command worked. */
  private async _run(command: string, fields: Fields, okText = ''): Promise<boolean> {
    try {
      await this._api!.call(command, fields);
      if (okText) this._toast(okText);
      void this._refresh();
      return true;
    } catch (err) {
      this._toast(errorText(err));
      // Show the stored values again, not the change that failed.
      this._render();
      return false;
    }
  }

  private _toast(text: string): void {
    if (this._host) this._host.showToast(text);
    else this.dispatchEvent(new CustomEvent('hass-notification', { detail: { message: text }, bubbles: true, composed: true }));
  }

  // ── Navigation ─────────────────────────────────────────────────────────────

  private _go(path: string, replace = false): void {
    if (this._host) this._host.navigate(path, { replace });
    else this.route = { path };
  }

  private _setFilter(key: string, value: string): void {
    let query = withQuery(this._route.query, key, value);
    if (key === 'room' && value && this._idx && query.shelf && query.shelf !== 'none') {
      if (shelfPath(this._idx, query.shelf).room?.id !== value) query = withQuery(query, 'shelf', '');
    }
    this._go(booksPath(query), true);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  private _ctx(): ViewCtx | null {
    if (!this._lib || !this._idx) return null;
    const states = this._hass?.states ?? {};
    return {
      lib: this._lib,
      idx: this._idx,
      route: this._route,
      me: this._lib.me.person_id,
      today: todayISO(new Date()),
      ui: this._ui,
      booksPath: this._booksPath,
      taskLink: (id) => this._host?.taskLink(id) ?? `/home-keeper/tasks/${encodeURIComponent(id)}`,
      areaName: (id) => this._hass?.areas?.[id]?.name ?? id,
      todoName: (id) => String(states[id]?.attributes?.friendly_name ?? id),
    };
  }

  private _viewHtml(ctx: ViewCtx): string {
    switch (this._route.view) {
      case 'book':
        return renderBook(ctx, ctx.idx.book.get(this._route.id ?? ''));
      case 'shelves':
        return renderShelves(ctx);
      case 'loans':
        return renderLoans(ctx);
      case 'wishlist':
        return renderWishlist(ctx);
      case 'scan':
        return renderScan(ctx);
      case 'settings':
        return renderSettings(ctx);
      case 'import':
        return renderBooks({ ...ctx, route: parseRoute(this._booksPath) }) + renderImport(ctx);
      default:
        return renderBooks(ctx);
    }
  }

  private _render(): void {
    const ctx = this._ctx();
    const foot = `<div class="hkl-foot">${escapeHTML(t('common.version', { version: PANEL_VERSION }))}</div>`;
    if (!ctx) {
      this._main.innerHTML = this._error
        ? `<div class="hkl-error" role="alert">${escapeHTML(this._error)}</div>`
        : `<div class="hkl-loading">${escapeHTML(t('common.loading'))}</div>`;
      return;
    }
    const err = this._error ? `<div class="hkl-error" role="alert">${escapeHTML(this._error)}</div>` : '';
    const admin = ctx.lib.me.is_admin ? '' : `<div class="hkl-banner warn">${escapeHTML(t('common.admin_only'))}</div>`;
    this._main.dataset.view = this._route.view;
    renderKeepFocus(this._root, this._main, `${admin}${err}${this._viewHtml(ctx)}${this._route.view === 'scan' ? '' : foot}`);
    wireMarkdown(this._main);
    wireCovers(this._main, this._api, () => this._render());
    const slot = this._main.querySelector('[data-slot="video"]');
    if (slot && this._scanner) {
      slot.appendChild(this._scanner.video);
      this._scanner.resume();
    }
  }

  private _renderDialog(): void {
    const ctx = this._ctx();
    if (!this._dialog || !ctx) {
      this._dlg.innerHTML = '';
      return;
    }
    const areas = Object.values(this._hass?.areas ?? {})
      .map((a): [string, string] => [a.area_id, a.name])
      .sort((a, b) => a[1].localeCompare(b[1]));
    this._dlg.innerHTML = renderDialog(ctx, this._dialog, areas);
    const first = this._dlg.querySelector<HTMLElement>('input:not([type=hidden]):not([type=checkbox]), select, textarea');
    (first ?? this._dlg.querySelector<HTMLElement>('[data-k="d-submit"]'))?.focus();
  }

  /** Show the busy state and the error of the open dialog. The form keeps what the user typed. */
  private _showDialogStatus(): void {
    const state = this._dialog;
    const form = this._dlg.querySelector<HTMLFormElement>('form[data-form="dialog"]');
    if (!state || !form) {
      this._renderDialog();
      return;
    }
    const submit = form.querySelector<HTMLButtonElement>('[data-k="d-submit"]');
    if (submit) submit.disabled = state.busy;
    let error = [...form.children].find((c): c is HTMLElement => c.classList.contains('hkl-error'));
    if (!state.error) {
      error?.remove();
      return;
    }
    if (!error) {
      error = document.createElement('div');
      error.className = 'hkl-error';
      error.setAttribute('role', 'alert');
      form.querySelector('.hkl-dlg-actions')?.before(error);
    }
    error.textContent = state.error;
  }

  private _openDialog(dialog: Dialog): void {
    this._dialog = { dialog, error: '', busy: false };
    this._renderDialog();
  }

  private _closeDialog(): void {
    this._dialog = null;
    this._renderDialog();
  }

  // ── Events ─────────────────────────────────────────────────────────────────

  private _onClick(ev: MouseEvent): void {
    const target = ev.target as HTMLElement;
    const el = target.closest<HTMLElement>('[data-act]');
    if (!el) return;
    const act = el.dataset.act!;
    if (act.endsWith('scrim') && el !== target) return;
    // With no `host.openTask` (Home Keeper before 0.30), the link opens the task.
    if (act === 'open-task' && !this._host?.openTask) return;
    if (el.tagName === 'A') {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      ev.preventDefault();
    }
    void this._act(act, el);
  }

  private _onKey(ev: KeyboardEvent): void {
    if (ev.key !== 'Escape') return;
    if (this._dialog) {
      this._closeDialog();
      ev.stopPropagation();
    } else if (this._route.view === 'import') {
      void this._act('import-close', this);
    }
  }

  private _onInput(ev: Event): void {
    const el = ev.target as HTMLInputElement;
    if (el.dataset?.input === 'q') this._search(el.value);
  }

  private async _onChange(ev: Event): Promise<void> {
    const el = ev.target as HTMLInputElement;
    const kind = el.dataset?.chg;
    if (!kind) return;
    const value = el.type === 'checkbox' ? el.checked : el.value;
    const key = el.dataset.key ?? '';
    const id = el.dataset.id ?? '';
    switch (kind) {
      case 'filter':
        this._setFilter(key, String(value));
        return;
      case 'reading-person':
        this._ui.readingPerson = String(value);
        this._render();
        return;
      case 'reading-field': {
        const v = key === 'page' || key === 'read_count' ? intOrNull(value) : String(value) || null;
        await this._setReading({ [key]: key === 'read_count' ? (v ?? 0) : v });
        return;
      }
      case 'cover-file':
        await this._uploadCover(el);
        return;
      case 'wish-buy':
        await this._run('update_wishlist', { book_id: id, buy: Boolean(value) });
        return;
      case 'person': {
        const fields: Fields = { person_id: id };
        if (key === 'share_reading') fields.share_reading = Boolean(value);
        if (key === 'yearly_goal') fields.yearly_goal = intOrNull(value);
        if (key === 'wishlist_todo') fields.wishlist_todo = String(value) || null;
        await this._run('set_person_settings', fields, t('settings.saved'));
        return;
      }
      case 'export-format':
        this._ui.exportFormat = value === 'library' ? 'library' : 'goodreads';
        return;
      case 'export-person':
        this._ui.exportPerson = String(value);
        return;
      case 'scan-method':
        this._ui.scan.method = value === 'manual' ? 'manual' : 'camera';
        this._render();
        return;
      case 'scan-field': {
        const s = this._ui.scan as unknown as Record<string, unknown>;
        s[key] = value;
        return;
      }
      case 'scan-markread':
        this._ui.scan.markRead = Boolean(value);
        return;
      case 'import': {
        const s = this._ui.import as unknown as Record<string, unknown>;
        s[key] = value;
        if (this._ui.import.content) await this._dryRun();
        else this._render();
        return;
      }
      case 'import-file':
        await this._readImportFile(el);
        return;
    }
  }

  private _onSubmit(ev: SubmitEvent): void {
    const form = ev.target as HTMLFormElement;
    const kind = form.dataset?.form;
    if (!kind) return;
    ev.preventDefault();
    if (kind === 'dialog') void this._submitDialog(form);
    if (kind === 'notes') void this._saveNotes(form);
    if (kind === 'currency') void this._saveCurrency(form);
    if (kind === 'isbn') {
      const input = form.elements.namedItem('isbn') as HTMLInputElement;
      const isbn = normalizeIsbn(input.value);
      if (!isbn) {
        this._toast(t('scan.bad_isbn'));
        return;
      }
      input.value = '';
      void this._scanIsbn(isbn);
    }
  }

  private _book(): Book | undefined {
    return this._idx?.book.get(this._route.id ?? '');
  }

  private async _act(act: string, el: HTMLElement): Promise<void> {
    const id = el.dataset.id ?? '';
    const value = el.dataset.value ?? '';
    const book = this._book();
    const lib = this._lib;
    const idx = this._idx;
    switch (act) {
      case 'nav':
        this._go(el.dataset.path ?? '/books', el.dataset.replace === '1');
        return;
      case 'back':
        this._go(this._booksPath, true);
        return;
      case 'open-task':
        this._host?.openTask?.(id);
        return;
      case 'status':
        this._setFilter('status', value);
        return;
      case 'layout':
        this._setFilter('view', value);
        return;
      case 'clear-filters': {
        const f = readFilters(this._route.query);
        this._go(booksPath({ sort: f.sort, view: f.view }), true);
        return;
      }
      case 'more':
        this._ui.limit += PAGE;
        this._render();
        return;
      case 'set-status':
        if (book) await this._setStatus(book, value as ReadingStatus);
        return;
      case 'rate': {
        const row = book ? readingOf(book, this._readingPerson()) : null;
        const n = Number(value);
        await this._setReading({ rating: row?.rating === n ? null : n });
        return;
      }
      case 'notes-tab':
        this._ui.notesTab = value === 'private' ? 'private' : 'shared';
        this._ui.editNotes = false;
        this._render();
        return;
      case 'notes-edit':
        this._ui.editNotes = true;
        this._render();
        this._main.querySelector<HTMLElement>('[data-k="notes-text"]')?.focus();
        return;
      case 'notes-cancel':
        this._ui.editNotes = false;
        this._render();
        return;
      case 'return-loan':
        await this._run('return_loan', { loan_id: id }, t('loan.returned_toast'));
        return;
      case 'delete-loan':
        this._openDialog({ kind: 'confirm', title: t('dialog.delete_loan'), text: t('dialog.delete_loan_text'), label: t('action.delete'), command: 'delete_loan', fields: { loan_id: id } });
        return;
      case 'move-copy':
        this._openDialog({ kind: 'move', copyId: id });
        return;
      case 'add-book':
        this._openDialog({ kind: 'add-book' });
        return;
      case 'edit-book':
        if (book) this._openDialog({ kind: 'edit-book', bookId: book.id });
        return;
      case 'scan-details':
        this._openDialog({ kind: 'edit-book', bookId: id });
        return;
      case 'add-copy':
        if (book) this._openDialog({ kind: 'copy', bookId: book.id, copyId: null });
        return;
      case 'edit-copy':
        if (book) this._openDialog({ kind: 'copy', bookId: book.id, copyId: id });
        return;
      case 'delete-copy':
        this._openDialog({ kind: 'confirm', title: t('dialog.delete_copy'), text: t('dialog.delete_copy_text'), label: t('action.delete'), command: 'delete_copy', fields: { copy_id: id } });
        return;
      case 'delete-book':
        if (book) {
          this._openDialog({ kind: 'confirm', title: t('dialog.delete_book'), text: t('dialog.delete_book_text', { title: book.title }), label: t('action.delete'), command: 'delete_book', fields: { book_id: book.id }, after: this._booksPath });
        }
        return;
      case 'refresh-book':
        if (book) await this._run('refresh_book', { book_id: book.id }, t('book.refreshed'));
        return;
      case 'change-cover':
        this._main.querySelector<HTMLInputElement>('[data-k="cover-file"]')?.click();
        return;
      case 'use-ol-cover':
        if (book) await this._run('set_cover', { book_id: book.id, kind: 'openlibrary' });
        return;
      case 'lend':
        this._openDialog({ kind: 'lend', bookId: el.dataset.book ?? null });
        return;
      case 'borrow':
        this._openDialog({ kind: 'borrow' });
        return;
      case 'wish-add':
        this._openDialog({ kind: 'wish-add', bookId: null });
        return;
      case 'wish-this':
        if (book) this._openDialog({ kind: 'wish-add', bookId: book.id });
        return;
      case 'got-it':
        this._openDialog({ kind: 'got-it', bookId: id });
        return;
      case 'wish-remove':
        await this._run('remove_from_wishlist', { book_id: id }, t('wishlist.removed'));
        return;
      case 'add-room':
        this._openDialog({ kind: 'room', roomId: null });
        return;
      case 'edit-room':
        this._openDialog({ kind: 'room', roomId: id });
        return;
      case 'delete-room':
        this._openDialog({ kind: 'confirm', title: t('dialog.delete_room'), text: t('dialog.delete_place_text', { name: idx?.room.get(id)?.name ?? '' }), label: t('action.delete'), command: 'delete_room', fields: { room_id: id, force: true }, after: '/shelves' });
        return;
      case 'add-bookcase':
        this._openDialog({ kind: 'bookcase', roomId: id, bookcaseId: null });
        return;
      case 'edit-bookcase': {
        const bc = idx?.bookcase.get(id);
        if (bc) this._openDialog({ kind: 'bookcase', roomId: bc.room_id, bookcaseId: id });
        return;
      }
      case 'delete-bookcase':
        this._openDialog({ kind: 'confirm', title: t('dialog.delete_bookcase'), text: t('dialog.delete_place_text', { name: idx?.bookcase.get(id)?.name ?? '' }), label: t('action.delete'), command: 'delete_bookcase', fields: { bookcase_id: id, force: true } });
        return;
      case 'add-shelf':
        this._openDialog({ kind: 'shelf', bookcaseId: id, shelfId: null });
        return;
      case 'edit-shelf': {
        const sh = idx?.shelf.get(id);
        if (sh) this._openDialog({ kind: 'shelf', bookcaseId: sh.bookcase_id, shelfId: id });
        return;
      }
      case 'delete-shelf':
        this._openDialog({ kind: 'confirm', title: t('dialog.delete_shelf'), text: t('dialog.delete_place_text', { name: idx?.shelf.get(id)?.name ?? '' }), label: t('action.delete'), command: 'delete_shelf', fields: { shelf_id: id, force: true } });
        return;
      case 'set-shelf':
        this._openDialog({ kind: 'set-shelf' });
        return;
      case 'dialog-close':
      case 'dialog-scrim':
        this._closeDialog();
        return;
      case 'export':
        await this._export();
        return;
      case 'import-pick':
        this._main.querySelector<HTMLInputElement>('[data-k="im-file"]')?.click();
        return;
      case 'import-run':
        await this._runImport();
        return;
      case 'import-close':
      case 'import-close-scrim':
        this._ui.import = freshImport(lib?.me.person_id ?? null);
        this._go(this._booksPath, true);
        return;
      default:
        await this._scanAct(act, el);
    }
  }

  // ── Reading ────────────────────────────────────────────────────────────────

  private _readingPerson(): string | null {
    return this._ui.readingPerson ?? this._lib?.me.person_id ?? null;
  }

  private async _setReading(fields: Fields, bookId?: string, personId?: string | null): Promise<boolean> {
    const id = bookId ?? this._route.id;
    const pid = personId ?? this._readingPerson();
    if (!id || !pid) {
      this._toast(t('common.no_person'));
      return false;
    }
    return this._run('set_reading', { book_id: id, person_id: pid, ...fields });
  }

  private async _setStatus(book: Book, status: ReadingStatus): Promise<void> {
    const row = readingOf(book, this._readingPerson());
    const today = todayISO(new Date());
    const fields: Fields = { status };
    if (status === 'reading' && !row?.started) fields.started = today;
    if (status === 'read' && row?.status !== 'read') {
      fields.finished = today;
      fields.read_count = (row?.read_count ?? 0) + 1;
    }
    await this._setReading(fields, book.id);
  }

  private async _saveNotes(form: HTMLFormElement): Promise<void> {
    const book = this._book();
    if (!book) return;
    const text = (form.elements.namedItem('text') as HTMLTextAreaElement).value;
    const saved =
      this._ui.notesTab === 'shared'
        ? await this._run('update_book', { book_id: book.id, shared_notes: text })
        : await this._setReading({ private_notes: text });
    // If the save fails, the editor stays open with the text.
    if (saved) this._ui.editNotes = false;
    this._render();
  }

  private async _saveCurrency(form: HTMLFormElement): Promise<void> {
    const input = form.elements.namedItem('currency') as HTMLInputElement;
    const currency = input.value.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(currency)) {
      this._toast(t('settings.currency_bad'));
      return;
    }
    if (currency === this._lib?.currency) return;
    await this._run('set_settings', { currency }, t('settings.saved'));
  }

  private async _uploadCover(input: HTMLInputElement): Promise<void> {
    const book = this._book();
    const file = input.files?.[0];
    input.value = '';
    if (!book || !file) return;
    if (file.size > MAX_COVER_BYTES) {
      this._toast(t('book.cover_too_big'));
      return;
    }
    try {
      const fileId = await this._api!.uploadCover(file);
      await this._run('set_cover', { book_id: book.id, kind: 'custom', file_id: fileId }, t('book.cover_saved'));
    } catch (err) {
      this._toast(errorText(err));
    }
  }

  // ── Dialog submit ──────────────────────────────────────────────────────────

  private async _submitDialog(form: HTMLFormElement): Promise<void> {
    const state = this._dialog;
    if (!state || state.busy) return;
    const data = new FormData(form);
    const str = (name: string) => String(data.get(name) ?? '').trim();
    const on = (name: string) => data.get(name) === 'on';
    const d = state.dialog;
    state.busy = true;
    state.error = '';
    this._showDialogStatus();
    try {
      const api = this._api!;
      let after: string | undefined;
      switch (d.kind) {
        case 'add-book': {
          const query = str('query');
          if (!query) throw new Error(t('dialog.need_title'));
          const isbn = normalizeIsbn(query);
          const res = await api.call<Record<string, unknown>>('add_book', {
            ...(isbn ? { isbn } : { title: query }),
            authors: splitList(str('authors')),
            lookup: on('lookup'),
          });
          const bookId = replyId(res, 'book');
          const existing = Boolean(res?.existing ?? (res?.book as Record<string, unknown> | undefined)?.existing);
          if (existing) this._toast(t('dialog.existing'));
          else if (bookId && on('own')) await api.call('add_copy', { book_id: bookId, shelf_id: str('shelf_id') || null, format: str('format') });
          if (bookId) after = `/books/${encodeURIComponent(bookId)}`;
          break;
        }
        case 'edit-book': {
          const isbn = str('isbn');
          const series = str('series_name');
          const fields: Fields = {
            book_id: d.bookId,
            title: str('title'),
            subtitle: str('subtitle'),
            authors: splitList(str('authors')),
            publisher: str('publisher'),
            published: str('published'),
            pages: intOrNull(str('pages')),
            language: str('language') || null,
            series: series ? { name: series, number: numberOrNull(str('series_number')) } : null,
            subjects: splitList(str('subjects')),
            tags: splitList(str('tags')),
            description: str('description'),
          };
          if (isbn) {
            const norm = normalizeIsbn(isbn);
            if (!norm) throw new Error(t('scan.bad_isbn'));
            fields.isbn13 = norm;
          } else {
            fields.isbn13 = null;
            fields.isbn10 = null;
          }
          if (on('details_done')) fields.needs_details = false;
          await api.call('update_book', fields);
          break;
        }
        case 'copy': {
          const fields: Fields = {
            format: str('format'),
            condition: str('condition') || null,
            acquired: str('acquired') || null,
            acquired_from: str('acquired_from'),
            price: numberOrNull(str('price')),
            value: numberOrNull(str('value')),
            signed: on('signed'),
            first_edition: on('first_edition'),
            note: str('note'),
          };
          const shelf = str('shelf_id') || null;
          if (d.copyId) {
            await api.call('update_copy', { copy_id: d.copyId, ...fields });
            if ((this._idx?.copy.get(d.copyId)?.shelf_id ?? null) !== shelf) await api.call('move_copy', { copy_id: d.copyId, shelf_id: shelf });
          } else {
            await api.call('add_copy', { book_id: d.bookId, shelf_id: shelf, ...fields });
          }
          break;
        }
        case 'move':
          await api.call('move_copy', { copy_id: d.copyId, shelf_id: str('shelf_id') || null });
          break;
        case 'set-shelf': {
          const shelf = str('shelf_id') || null;
          for (const copyId of data.getAll('copy')) await api.call('move_copy', { copy_id: String(copyId), shelf_id: shelf });
          break;
        }
        case 'lend':
          if (!str('copy_id') || !str('party')) throw new Error(t('dialog.need_party'));
          await api.call('lend_book', {
            copy_id: str('copy_id'),
            party: str('party'),
            started: str('started') || undefined,
            due: str('due') || undefined,
            note: str('note'),
            add_task: on('add_task'),
          });
          this._toast(t('loan.lent_toast'));
          break;
        case 'borrow': {
          const query = str('query');
          if (!query || !str('party')) throw new Error(t('dialog.need_party'));
          const isbn = normalizeIsbn(query);
          await api.call('borrow_book', {
            ...(isbn ? { isbn } : { title: query }),
            party: str('party'),
            person_id: str('person_id'),
            format: str('format'),
            started: str('started') || undefined,
            due: str('due') || undefined,
            note: str('note'),
            add_task: on('add_task'),
          });
          break;
        }
        case 'wish-add': {
          const query = str('query');
          const isbn = query ? normalizeIsbn(query) : null;
          if (!d.bookId && !query) throw new Error(t('dialog.need_title'));
          await api.call('add_to_wishlist', {
            ...(d.bookId ? { book_id: d.bookId } : isbn ? { isbn } : { title: query }),
            person_id: str('person_id'),
            buy: on('buy'),
          });
          this._toast(t('wishlist.added'));
          break;
        }
        case 'got-it':
          await api.call('got_wishlist_book', { book_id: d.bookId, shelf_id: str('shelf_id') || null, format: str('format') });
          break;
        case 'room': {
          const fields = { name: str('name'), area_id: str('area_id') || null };
          if (!fields.name) throw new Error(t('dialog.need_name'));
          if (d.roomId) await api.call('update_room', { room_id: d.roomId, ...fields });
          else {
            const res = await api.call('add_room', fields);
            const roomId = replyId(res, 'room');
            if (roomId) after = `/shelves/${encodeURIComponent(roomId)}`;
          }
          break;
        }
        case 'bookcase': {
          const fields = { name: str('name'), note: str('note') };
          if (!fields.name) throw new Error(t('dialog.need_name'));
          if (d.bookcaseId) await api.call('update_bookcase', { bookcase_id: d.bookcaseId, ...fields });
          else {
            const res = await api.call('add_bookcase', { room_id: d.roomId, ...fields });
            const caseId = replyId(res, 'bookcase');
            const n = Math.min(20, intOrNull(str('shelves')) ?? 0);
            for (let i = 1; caseId && i <= n; i++) {
              await api.call('add_shelf', { bookcase_id: caseId, name: t('dialog.shelf_default', { n: i }), order: i });
            }
          }
          break;
        }
        case 'shelf': {
          const name = str('name');
          if (!name) throw new Error(t('dialog.need_name'));
          if (d.shelfId) await api.call('update_shelf', { shelf_id: d.shelfId, name });
          else {
            const order = (this._lib?.shelves.filter((s) => s.bookcase_id === d.bookcaseId).length ?? 0) + 1;
            await api.call('add_shelf', { bookcase_id: d.bookcaseId, name, order });
          }
          break;
        }
        case 'confirm':
          await api.call(d.command, d.fields);
          after = d.after;
          break;
      }
      // The user can close this dialog and open a new one during the call.
      if (this._dialog === state) this._closeDialog();
      void this._refresh();
      if (after) this._go(after, d.kind === 'confirm');
    } catch (err) {
      state.busy = false;
      state.error = errorText(err);
      if (this._dialog === state) this._showDialogStatus();
    }
  }

  // ── Import and export ──────────────────────────────────────────────────────

  private async _readImportFile(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const s = this._ui.import;
    if (file.size > MAX_IMPORT_BYTES) {
      s.error = t('import.too_big');
      this._render();
      return;
    }
    s.fileName = file.name;
    s.content = await file.text();
    s.rowCount = csvRowCount(s.content);
    s.summary = null;
    s.done = false;
    s.error = '';
    if (/storygraph/i.test(file.name)) s.source = 'storygraph';
    await this._dryRun();
  }

  private _importFields(dryRun: boolean): Fields {
    const s = this._ui.import;
    return {
      content: s.content,
      source: s.source,
      person_id: s.personId ?? this._lib?.me.person_id ?? undefined,
      shelf_id: s.shelfId || null,
      import_notes: s.importNotes,
      replace_reading: s.replaceReading,
      dry_run: dryRun,
    };
  }

  private async _dryRun(): Promise<void> {
    const s = this._ui.import;
    // A change of the source, the person or the shelf starts a new preview.
    // Only the reply of the latest preview is used.
    const run = ++this._dryRunSeq;
    s.busy = true;
    s.error = '';
    this._render();
    let summary: ImportSummary | null = null;
    let error = '';
    try {
      summary = await this._api!.importCsv(this._importFields(true));
    } catch (err) {
      error = errorText(err);
    }
    if (run !== this._dryRunSeq || this._ui.import !== s) return;
    s.summary = summary;
    s.error = error;
    s.busy = false;
    this._render();
  }

  private async _runImport(): Promise<void> {
    const s = this._ui.import;
    if (!s.summary || s.busy) return;
    s.busy = true;
    this._render();
    try {
      s.summary = await this._api!.importCsv(this._importFields(false));
      s.done = true;
      this._toast(t('import.done'));
      void this._refresh();
    } catch (err) {
      s.error = errorText(err);
    }
    s.busy = false;
    this._render();
  }

  private async _export(): Promise<void> {
    try {
      const res = await this._api!.exportCsv({ format: this._ui.exportFormat, person_id: this._ui.exportPerson || undefined });
      const blob = new Blob([res.content], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = res.filename || 'library.csv';
      this._root.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      this._toast(errorText(err));
    }
  }

  // ── Scan ───────────────────────────────────────────────────────────────────

  private _scanPath(query: Record<string, string>): string {
    return buildPath({ view: 'scan', query });
  }

  private _syncScanner(): void {
    const want = this._route.view === 'scan' && this._route.query.step === 'camera' && this._ui.scan.method === 'camera';
    if (!want) {
      this._stopScanner();
      return;
    }
    if (this._scanner) return;
    const scanner = new Scanner((code) => this._onCode(code));
    this._scanner = scanner;
    this._ui.scan.cameraError = '';
    void scanner.start().then((res) => {
      // The user left the camera step while the camera started.
      if (this._scanner !== scanner) {
        scanner.stop();
        return;
      }
      if (res !== 'ok') {
        this._ui.scan.cameraError = res;
        this._ui.scan.manualOpen = true;
        this._scanner = null;
      } else {
        this._ui.scan.torch = scanner.torchSupported() ? false : null;
      }
      this._render();
    });
  }

  private _stopScanner(): void {
    this._scanner?.stop();
    this._scanner = null;
  }

  private _onCode(code: string): void {
    const isbn = isbnFromEan(code);
    if (!this._gate(isbn ?? code, Date.now())) return;
    if (!isbn) {
      this._toast(t('scan.not_isbn'));
      return;
    }
    navigator.vibrate?.(40);
    void this._scanIsbn(isbn);
  }

  private async _scanIsbn(isbn: string): Promise<void> {
    const s = this._ui.scan;
    const entry: ScanEntry = { key: ++this._scanKey, isbn, pending: true, res: null };
    s.results.push(entry);
    this._render();
    try {
      if (this._route.query.mode === 'borrowed') {
        const res = await this._api!.call<Record<string, unknown>>('borrow_book', {
          isbn,
          party: s.party || t('loan.unknown_party'),
          person_id: s.personId ?? this._lib?.me.person_id ?? undefined,
          due: s.due || undefined,
          started: todayISO(new Date()),
          add_task: s.addTask,
        });
        const book = (res?.book as Book | undefined) ?? null;
        entry.res = { result: 'added', book, copy: null, existing_copies: [] };
      } else {
        entry.res = await this._api!.scanIsbn({ isbn, shelf_id: routeShelf(this._ctx()!), on_duplicate: 'ask' });
      }
    } catch (err) {
      entry.error = errorText(err);
    }
    entry.pending = false;
    this._render();
    void this._refresh();
  }

  private async _scanDuplicate(entry: ScanEntry, choice: 'move' | 'add_copy' | 'skip'): Promise<void> {
    entry.choice = choice;
    entry.pending = true;
    this._render();
    try {
      entry.res = await this._api!.scanIsbn({ isbn: entry.isbn, shelf_id: routeShelf(this._ctx()!), on_duplicate: choice });
    } catch (err) {
      entry.error = errorText(err);
    }
    entry.pending = false;
    this._render();
    void this._refresh();
  }

  /** Set "Read" for me on each book that the session added or moved. */
  private async _applyMarkRead(): Promise<void> {
    const s = this._ui.scan;
    const me = this._lib?.me.person_id;
    if (!s.markRead || !me || isBorrowedMode(this._ctx()!)) return;
    const books = new Set(
      s.results
        .filter((r) => r.res && (r.res.result === 'added' || r.res.result === 'moved') && r.res.book)
        .map((r) => (r.res as ScanResult).book!.id),
    );
    const today = todayISO(new Date());
    for (const bookId of books) {
      await this._run('set_reading', { book_id: bookId, person_id: me, status: 'read', finished: today });
    }
    if (books.size) this._toast(tn('scan.marked_read', books.size));
  }

  private async _scanAct(act: string, el: HTMLElement): Promise<void> {
    const s = this._ui.scan;
    const q = this._route.query;
    switch (act) {
      case 'scan-room':
        s.roomId = el.dataset.id ?? null;
        this._render();
        return;
      case 'scan-start': {
        const ctx = this._ctx();
        if (ctx && cameraBlocked(ctx)) return;
        s.results = [];
        s.manualOpen = s.method === 'manual';
        this._gate = makeCodeGate(3000);
        this._go(this._scanPath({ ...q, step: 'camera' }));
        return;
      }
      case 'scan-manual':
        s.manualOpen = !s.manualOpen;
        this._render();
        this._main.querySelector<HTMLElement>('[data-k="isbn-input"]')?.focus();
        return;
      case 'scan-dup': {
        const entry = s.results.find((r) => String(r.key) === el.dataset.key);
        const choice = el.dataset.value as 'move' | 'add_copy' | 'skip';
        if (entry) await this._scanDuplicate(entry, choice);
        return;
      }
      case 'scan-torch':
        if (this._scanner && s.torch !== null) {
          s.torch = !s.torch;
          await this._scanner.setTorch(s.torch).catch(() => undefined);
          this._render();
        }
        return;
      case 'scan-done':
        this._go(this._scanPath({ ...q, step: 'summary' }), true);
        return;
      case 'scan-next':
        await this._applyMarkRead();
        s.results = [];
        this._go(this._scanPath({ ...q, shelf: el.dataset.id ?? '', step: 'camera' }), true);
        return;
      case 'scan-finish': {
        await this._applyMarkRead();
        s.results = [];
        const room = this._idx ? shelfPath(this._idx, routeShelf(this._ctx()!)).room : null;
        this._go(q.mode === 'borrowed' ? buildPath({ view: 'loans', query: { tab: 'in' } }) : room ? `/shelves/${encodeURIComponent(room.id)}` : '/books', true);
        return;
      }
      case 'scan-setup':
        this._go(this._scanPath({ ...q, step: '' }), true);
        return;
      case 'scan-exit':
        this._go(q.mode === 'borrowed' ? '/loans' : this._booksPath, true);
        return;
    }
  }
}
