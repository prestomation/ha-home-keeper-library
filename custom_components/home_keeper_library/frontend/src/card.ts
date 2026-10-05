// The `home-keeper-library-card` dashboard card and its visual editor.
//
// Any user can add the card. It shows the reading of the caller's own person.
// An admin can set `person` in the config to show another person. The data
// comes from `get_state`, which the backend projects for a non-admin user.

import { errorText, LibraryApi } from './api';
import { renderKeepFocus } from './dom';
import { formatAgo, formatNumber, setLanguage, t, tn } from './i18n';
import { cover, personDot, statusLabel } from './markup';
import { TOKENS } from './styles';
import type { Book, HomeAssistant, Lib } from './types';
import {
  buildIndex,
  cardModel,
  daysBetween,
  debounce,
  escapeHTML,
  locationLabel,
  matchesSearch,
  normalizeState,
  personNames,
  pickRandom,
  progress,
  readingOf,
  todayISO,
  type Index,
} from './utils';

export interface CardConfig {
  type: string;
  title?: string;
  person?: string;
  search?: boolean;
  reading?: boolean;
  want?: boolean;
  goal?: boolean;
  household?: boolean;
}

export const SECTIONS = ['search', 'reading', 'want', 'goal', 'household'] as const;
type Section = (typeof SECTIONS)[number];

export const CARD_TAG = 'home-keeper-library-card';
export const EDITOR_TAG = 'home-keeper-library-card-editor';

const CARD_CSS = `
:host { display: block; ${TOKENS} }
ha-card { display: block; background: var(--ha-card-background, var(--hkl-surface)); border-radius: var(--ha-card-border-radius, 12px); border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--hkl-divider)); color: var(--hkl-text); font-family: var(--hkl-font); overflow: hidden; }
* { box-sizing: border-box; }
.c { padding: 16px; display: flex; flex-direction: column; gap: 16px; font-size: 14px; }
.head { display: flex; align-items: center; gap: 10px; }
.head h2 { margin: 0; font-size: 18px; font-weight: 500; flex: 1 1 auto; }
.muted { color: var(--hkl-muted); }
.small { font-size: 12px; }
.eyebrow { font-size: 12px; font-weight: 500; letter-spacing: .6px; text-transform: uppercase; color: var(--hkl-muted); }
.sec { display: flex; flex-direction: column; gap: 8px; }
.search { display: flex; align-items: center; height: 40px; padding: 0 12px; border: 1px solid var(--hkl-outline); border-radius: 20px; background: var(--hkl-surface); }
.search input { border: none; outline: none; background: transparent; color: var(--hkl-text); font: 14px var(--hkl-font); width: 100%; }
.item { display: flex; align-items: center; gap: 12px; }
.main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.main b { font-weight: 500; }
.btn { height: 32px; padding: 0 14px; border: none; border-radius: 16px; background: var(--hkl-tonal); color: var(--hkl-tonal-ink); font: 500 13px var(--hkl-font); cursor: pointer; white-space: nowrap; }
.btn.text { background: none; }
.btns { display: flex; gap: 6px; flex-wrap: wrap; }
.bar { height: 6px; border-radius: 3px; background: var(--hkl-chip); overflow: hidden; }
.bar > span { display: block; height: 100%; background: var(--hkl-primary); }
.pill { font-size: 11px; background: var(--hkl-chip); border-radius: 10px; padding: 2px 8px; white-space: nowrap; }
.covers { display: grid; grid-template-columns: repeat(auto-fill, minmax(64px, 1fr)); gap: 8px; }
.pick { outline: 3px solid var(--hkl-primary); outline-offset: 2px; border-radius: 6px; }
.goal { display: flex; align-items: center; gap: 14px; }
.ring { flex: 0 0 64px; }
.ring circle { fill: none; stroke-width: 7; }
.ring .bg { stroke: var(--hkl-chip); }
.ring .fg { stroke: var(--hkl-primary); stroke-linecap: round; transform: rotate(-90deg); transform-origin: 50% 50%; }
.ring text { fill: var(--hkl-text); font: 700 18px var(--hkl-font); }
.act { display: flex; align-items: center; gap: 8px; line-height: 1.35; }
.page { display: flex; gap: 6px; align-items: center; }
.page input { width: 80px; height: 32px; border: 1px solid var(--hkl-outline); border-radius: 8px; padding: 0 8px; background: var(--hkl-surface); color: var(--hkl-text); }
.hkl-cover { position: relative; display: flex; flex-direction: column; justify-content: space-between; aspect-ratio: 2 / 3; border-radius: 3px 6px 6px 3px; background: var(--c); color: var(--ink); box-shadow: 0 1px 2px rgba(0,0,0,.25), inset 4px 0 0 rgba(0,0,0,.12); padding: 8px 6px 6px 10px; overflow: hidden; }
.hkl-cover.has-img { padding: 0; }
.hkl-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hkl-cover-title { font-family: Georgia, serif; font-weight: 700; font-size: 11px; line-height: 1.15; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; }
.hkl-cover-author { font-size: 7px; letter-spacing: .6px; text-transform: uppercase; opacity: .85; }
.hkl-cover-thumb { width: 40px; flex: 0 0 40px; padding: 4px 3px 3px 7px; }
.hkl-cover-thumb .hkl-cover-title { font-size: 6px; }
.big .hkl-cover-thumb { width: 56px; flex-basis: 56px; }
.hkl-dot { width: 24px; height: 24px; flex: 0 0 24px; border-radius: 12px; background: var(--p); color: #fff; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.err { color: var(--hkl-error-ink); }
`;

/** The section toggles of a config. A missing toggle is on. */
export function sectionsOn(config: CardConfig): Record<Section, boolean> {
  const out = {} as Record<Section, boolean>;
  for (const s of SECTIONS) out[s] = config[s] !== false;
  return out;
}

export class HomeKeeperLibraryCard extends HTMLElement {
  private _hass?: HomeAssistant;
  private _api?: LibraryApi;
  private _config: CardConfig = { type: `custom:${CARD_TAG}` };
  private _lib: Lib | null = null;
  private _idx: Index | null = null;
  private _error = '';
  private _q = '';
  private _pick: string | null = null;
  private _pageFor: string | null = null;
  private _unsub?: () => void | Promise<void>;
  private _subscribing = false;
  private _lang = '';
  private readonly _root: ShadowRoot;
  private readonly _body: HTMLElement;
  private readonly _search = debounce(() => this._render(), 150);

  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'open' });
    this._root.innerHTML = `<style>${CARD_CSS}</style><ha-card><div class="c"></div></ha-card>`;
    this._body = this._root.querySelector('.c')!;
    this._root.addEventListener('click', (ev) => void this._onClick(ev));
    this._root.addEventListener('input', (ev) => {
      const el = ev.target as HTMLInputElement;
      if (el.dataset.k === 'q') {
        this._q = el.value;
        this._search();
      }
    });
    this._root.addEventListener('submit', (ev) => {
      ev.preventDefault();
      void this._savePage(ev.target as HTMLFormElement);
    });
  }

  setConfig(config: CardConfig): void {
    if (!config || typeof config !== 'object') throw new Error('Invalid configuration');
    this._config = { ...config };
    this._render();
  }

  getCardSize(): number {
    return 6;
  }

  getGridOptions(): Record<string, number> {
    return { columns: 6, min_columns: 4, rows: 8, min_rows: 4 };
  }

  static getConfigElement(): HTMLElement {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(): CardConfig {
    return { type: `custom:${CARD_TAG}` };
  }

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

  connectedCallback(): void {
    if (this._hass && !this._unsub && !this._subscribing) void this._subscribe();
  }

  disconnectedCallback(): void {
    void this._unsub?.();
    this._unsub = undefined;
    this._search.cancel();
  }

  private async _start(): Promise<void> {
    this._render();
    await this._refresh();
    await this._subscribe();
  }

  private async _subscribe(): Promise<void> {
    if (!this._api || this._unsub || this._subscribing) return;
    this._subscribing = true;
    try {
      this._unsub = await this._api.subscribe(() => void this._refresh());
    } catch {
      // The card still shows the first fetch.
    } finally {
      this._subscribing = false;
    }
  }

  private async _refresh(): Promise<void> {
    if (!this._api) return;
    try {
      this._lib = normalizeState(await this._api.getState(), personNames(this._hass?.states));
      this._idx = buildIndex(this._lib);
      this._error = '';
    } catch (err) {
      this._error = errorText(err);
    }
    this._render();
  }

  /** The person that the card shows. */
  private _person(): string | null {
    const lib = this._lib;
    if (!lib) return null;
    if (this._config.person && lib.me.is_admin) return this._config.person;
    return lib.me.person_id;
  }

  private _render(): void {
    const lib = this._lib;
    const idx = this._idx;
    if (!lib || !idx) {
      this._body.innerHTML = this._error ? `<div class="err">${escapeHTML(this._error)}</div>` : `<div class="muted">${escapeHTML(t('common.loading'))}</div>`;
      return;
    }
    const pid = this._person();
    const person = pid ? idx.person.get(pid) : undefined;
    const on = sectionsOn(this._config);
    const owned = lib.books.filter((b) => b.owned).length;
    const title = this._config.title || t('card.title', { name: person?.name ?? '' });
    const head = `<div class="head">${personDot(person)}<h2>${escapeHTML(title)}</h2><span class="muted small">${escapeHTML(tn('count.books', owned))}</span></div>`;
    if (!pid) {
      this._body.innerHTML = `${head}<div class="muted">${escapeHTML(t('card.no_person'))}</div>`;
      return;
    }
    const now = new Date();
    const today = todayISO(now);
    const model = cardModel(lib, pid, now);
    const parts: string[] = [head];
    if (this._error) parts.push(`<div class="err">${escapeHTML(this._error)}</div>`);
    if (on.search) parts.push(this._searchHtml(lib, idx, pid));
    if (on.reading) {
      const rows = model.reading
        .map(({ book, row }) => {
          const pr = progress(row.page, book.pages);
          const page = row.page != null ? (book.pages ? t('book.page_of', { page: row.page, pages: book.pages }) : t('book.page_n', { page: row.page })) : '';
          const id = escapeHTML(book.id);
          const pageForm = this._pageFor === book.id
            ? `<form class="page" data-book="${id}"><input name="page" type="number" min="0" inputmode="numeric" data-k="page-${id}" value="${escapeHTML(row.page ?? '')}" aria-label="${escapeHTML(t('book.page'))}" /><button class="btn" type="submit">${escapeHTML(t('action.save'))}</button></form>`
            : `<div class="btns"><button class="btn" data-act="page" data-id="${id}" data-k="sp-${id}">${escapeHTML(t('card.set_page'))}</button><button class="btn" data-act="read" data-id="${id}" data-k="rd-${id}">${escapeHTML(t('status.read'))}</button></div>`;
          return `<div class="item big">${cover(book, 'thumb')}<div class="main"><b>${escapeHTML(book.title)}</b><span class="muted small">${escapeHTML(book.authors.join(', '))}</span>${pr != null ? `<span class="bar" role="img" aria-label="${pr}%"><span style="width:${pr}%"></span></span>` : ''}${page ? `<span class="muted small">${escapeHTML(page)}</span>` : ''}${pageForm}</div></div>`;
        })
        .join('');
      parts.push(`<div class="sec"><span class="eyebrow">${escapeHTML(t('status.reading'))}</span>${rows || `<span class="muted">${escapeHTML(t('card.no_reading'))}</span>`}</div>`);
    }
    if (on.want) {
      const covers = model.want
        .slice(0, 12)
        .map((b) => `<span class="${b.id === this._pick ? 'pick' : ''}" title="${escapeHTML(b.title)}">${cover(b, 'tile')}</span>`)
        .join('');
      const pick = this._pick ? idx.book.get(this._pick) : undefined;
      const pickLine = pick
        ? `<span class="small">${escapeHTML(t('card.pick', { title: pick.title }))}${this._where(idx, pick) ? ` · ${escapeHTML(this._where(idx, pick))}` : ''}</span>`
        : '';
      parts.push(`<div class="sec"><span class="eyebrow">${escapeHTML(t('status.want'))} · ${model.want.length}</span>${covers ? `<div class="covers">${covers}</div>` : `<span class="muted">${escapeHTML(t('card.no_want'))}</span>`}${model.want.length ? `<div class="btns"><button class="btn" data-act="random" data-k="random">${escapeHTML(t('card.random'))}</button></div>${pickLine}` : ''}</div>`);
    }
    if (on.goal) {
      const { done, goal, pages, year } = model.goal;
      const pct = goal ? Math.min(1, done / goal) : 0;
      const c = 2 * Math.PI * 26;
      const ring = `<svg class="ring" width="64" height="64" viewBox="0 0 64 64" aria-hidden="true"><circle class="bg" cx="32" cy="32" r="26"/><circle class="fg" cx="32" cy="32" r="26" stroke-dasharray="${(c * pct).toFixed(1)} ${c.toFixed(1)}"/><text x="32" y="38" text-anchor="middle">${done}</text></svg>`;
      const line = goal ? t('card.goal_of', { done, goal, year }) : tn('card.goal_none', done, { year });
      const sub = [goal ? t('card.goal', { goal }) : '', tn('book.pages', pages, { n: formatNumber(pages) })].filter(Boolean).join(' · ');
      parts.push(`<div class="goal">${ring}<div class="main"><b>${escapeHTML(line)}</b><span class="muted small">${escapeHTML(sub)}</span></div></div>`);
    }
    if (on.household) {
      const rows = model.household
        .map(({ person: p, book, row }) => {
          const days = row.updated_at ? Math.max(0, daysBetween(row.updated_at.slice(0, 10), today)) : null;
          const extra = [row.rating ? tn('book.stars', row.rating) : '', days != null ? formatAgo(days) : ''].filter(Boolean).join(' · ');
          return `<div class="act">${personDot(p)}<span>${escapeHTML(t(`card.act_${row.status}`, { name: p.name }))} <b>${escapeHTML(book.title)}</b>${extra ? ` <span class="muted">· ${escapeHTML(extra)}</span>` : ''}</span></div>`;
        })
        .join('');
      parts.push(`<div class="sec"><span class="eyebrow">${escapeHTML(t('book.household'))}</span>${rows || `<span class="muted">${escapeHTML(t('card.no_activity'))}</span>`}</div>`);
    }
    renderKeepFocus(this._root, this._body, parts.join(''));
  }

  private _where(idx: Index, book: Book): string {
    const copy = (idx.copiesByBook.get(book.id) ?? []).find((c) => c.shelf_id);
    return copy ? locationLabel(idx, copy.shelf_id) : '';
  }

  private _searchHtml(lib: Lib, idx: Index, pid: string): string {
    const input = `<label class="search"><input type="search" data-k="q" value="${escapeHTML(this._q)}" placeholder="${escapeHTML(t('card.search_placeholder'))}" aria-label="${escapeHTML(t('card.search_label'))}" /></label>`;
    if (!this._q.trim()) return `<div class="sec">${input}</div>`;
    const hits = lib.books.filter((b) => matchesSearch(b, this._q, pid)).slice(0, 5);
    const rows = hits
      .map((b) => {
        const st = readingOf(b, pid)?.status ?? null;
        const where = this._where(idx, b) || (b.owned ? t('common.no_shelf') : t('book.not_owned'));
        const action = st
          ? `<span class="pill">${escapeHTML(statusLabel(st))}</span>`
          : `<button class="btn" data-act="want" data-id="${escapeHTML(b.id)}" data-k="w-${escapeHTML(b.id)}">${escapeHTML(t('status.want'))}</button>`;
        return `<div class="item">${cover(b, 'thumb')}<div class="main"><b>${escapeHTML(b.title)}</b><span class="muted small">${escapeHTML(where)}</span></div>${action}</div>`;
      })
      .join('');
    return `<div class="sec">${input}${rows || `<span class="muted">${escapeHTML(t('books.no_match'))}</span>`}</div>`;
  }

  /** `set_reading` for the card person. A caller sends `person_id` only for another person. */
  private async _setReading(bookId: string, fields: Record<string, unknown>): Promise<void> {
    const pid = this._person();
    const self = pid === this._lib?.me.person_id;
    try {
      await this._api!.call('set_reading', { book_id: bookId, ...(self ? {} : { person_id: pid }), ...fields });
      await this._refresh();
    } catch (err) {
      this._error = errorText(err);
      this._render();
    }
  }

  private async _onClick(ev: Event): Promise<void> {
    const el = (ev.target as HTMLElement).closest<HTMLElement>('[data-act]');
    if (!el || !this._lib) return;
    const id = el.dataset.id ?? '';
    switch (el.dataset.act) {
      case 'want':
        await this._setReading(id, { status: 'want' });
        return;
      case 'read': {
        const book = this._idx?.book.get(id);
        const row = book ? readingOf(book, this._person()) : null;
        await this._setReading(id, { status: 'read', finished: todayISO(new Date()), read_count: (row?.read_count ?? 0) + 1 });
        return;
      }
      case 'page':
        this._pageFor = id;
        this._render();
        this._body.querySelector<HTMLInputElement>(`[data-k="page-${CSS.escape(id)}"]`)?.focus();
        return;
      case 'random': {
        const model = cardModel(this._lib, this._person(), new Date());
        this._pick = pickRandom(model.want, Math.random())?.id ?? null;
        this._render();
        return;
      }
    }
  }

  private async _savePage(form: HTMLFormElement): Promise<void> {
    const bookId = form.dataset.book;
    if (!bookId) return;
    const raw = (form.elements.namedItem('page') as HTMLInputElement).value;
    const page = raw === '' ? null : Math.max(0, Math.round(Number(raw)));
    this._pageFor = null;
    await this._setReading(bookId, { page: Number.isFinite(page) ? page : null });
  }
}

/** The visual editor of the card. Plain DOM: a title, a person and the section toggles. */
export class HomeKeeperLibraryCardEditor extends HTMLElement {
  private _config: CardConfig = { type: `custom:${CARD_TAG}` };
  private _hass?: HomeAssistant;

  setConfig(config: CardConfig): void {
    this._config = { ...config };
    this._render();
  }

  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    setLanguage(hass.locale?.language || hass.language || 'en');
    if (first) this._render();
  }

  private _render(): void {
    const names = personNames(this._hass?.states);
    const persons = Object.entries(names).sort((a, b) => a[1].localeCompare(b[1]));
    const opts = [['', t('editor.person_me')], ...persons]
      .map(([v, l]) => `<option value="${escapeHTML(v)}"${v === (this._config.person ?? '') ? ' selected' : ''}>${escapeHTML(l)}</option>`)
      .join('');
    const on = sectionsOn(this._config);
    const toggles = SECTIONS.map(
      (s) => `<label class="row"><input type="checkbox" data-key="${s}"${on[s] ? ' checked' : ''} />${escapeHTML(t(`editor.section_${s}`))}</label>`,
    ).join('');
    this.innerHTML = `<style>
      .hkl-ed { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; font-family: var(--ha-font-family-body, Roboto, sans-serif); color: var(--primary-text-color, #212121); }
      .hkl-ed label.f { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--secondary-text-color, #616161); }
      .hkl-ed input[type=text], .hkl-ed select { height: 40px; padding: 0 10px; border: 1px solid var(--divider-color, #bdbdbd); border-radius: 8px; background: var(--card-background-color, #fff); color: inherit; font-size: 14px; }
      .hkl-ed .row { display: flex; gap: 8px; align-items: center; font-size: 14px; }
      .hkl-ed .hint { font-size: 12px; color: var(--secondary-text-color, #616161); }
    </style>
    <div class="hkl-ed">
      <label class="f">${escapeHTML(t('editor.title'))}<input type="text" data-key="title" value="${escapeHTML(this._config.title ?? '')}" /></label>
      <label class="f">${escapeHTML(t('common.person'))}<select data-key="person">${opts}</select></label>
      <span class="hint">${escapeHTML(t('editor.person_hint'))}</span>
      <span class="hint">${escapeHTML(t('editor.sections'))}</span>
      ${toggles}
    </div>`;
    this.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-key]').forEach((el) => {
      el.addEventListener('change', () => this._changed(el));
    });
  }

  private _changed(el: HTMLInputElement | HTMLSelectElement): void {
    const key = el.dataset.key as keyof CardConfig;
    const next: CardConfig = { ...this._config };
    if (el instanceof HTMLInputElement && el.type === 'checkbox') {
      if (el.checked) delete next[key as Section];
      else (next as unknown as Record<string, unknown>)[key] = false;
    } else if (el.value) {
      (next as unknown as Record<string, unknown>)[key] = el.value;
    } else {
      delete next[key];
    }
    this._config = next;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: next }, bubbles: true, composed: true }));
  }
}
