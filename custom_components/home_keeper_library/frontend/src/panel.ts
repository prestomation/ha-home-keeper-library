import { HomeKeeperLibraryApi } from './api';
import { setLanguage, t, tn } from './i18n';
import type { HomeAssistant, Item, Route } from './types';
import { buildPath, escapeHTML, formatDate, parseRoute, PanelRoute } from './utils';
import { PANEL_VERSION } from 'panel-version';

/**
 * The Home Keeper Library sidebar panel (a `panel_custom` web component).
 *
 * Navigation is high-fidelity deep-linked: the URL is the single source of
 * truth. HA hands us a `route` for every in-panel URL change (including
 * Back/Forward); the `route` setter is the ONLY place that flips `_nav`. We
 * navigate by changing the URL via `_navigate`, never by mutating `_nav`
 * directly. Route parse/build are pure functions in utils.ts.
 */
export class HomeKeeperLibraryPanel extends HTMLElement {
  private _hass?: HomeAssistant;
  private _api?: HomeKeeperLibraryApi;
  private _route?: Route;
  private _nav: PanelRoute = { view: 'list', detailId: null };
  private _items: Item[] = [];
  private _loaded = false;
  private _adding = false;
  private _error = '';

  // ── HA-provided properties ────────────────────────────────────────────────
  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    this._api = new HomeKeeperLibraryApi(hass);
    setLanguage(hass.language);
    if (first) {
      void this._refresh();
    }
  }

  set route(route: Route) {
    this._route = route;
    this._nav = parseRoute(route);
    this._render();
  }
  get route(): Route | undefined {
    return this._route;
  }

  set narrow(_v: boolean) {
    /* accepted from HA; layout is responsive via CSS */
  }
  set panel(_v: unknown) {
    /* panel config from HA; unused */
  }

  // ── Navigation ────────────────────────────────────────────────────────────
  /** Change the panel URL; HA re-sets `route`, which flows back through `set route`. */
  private _navigate(state: PanelRoute, replace = false): void {
    const prefix = this._route?.prefix ?? '/home-keeper-library';
    const url = prefix + buildPath(state);
    history[replace ? 'replaceState' : 'pushState'](null, '', url);
    this.dispatchEvent(
      new CustomEvent('location-changed', { bubbles: true, composed: true }),
    );
  }

  // ── Data ──────────────────────────────────────────────────────────────────
  private async _refresh(): Promise<void> {
    if (!this._api) return;
    try {
      this._items = await this._api.list();
      this._error = '';
    } catch (err) {
      this._error = String(err);
    }
    this._loaded = true;
    this._render();
  }

  // ── Render ────────────────────────────────────────────────────────────────
  private _render(): void {
    if (!this._loaded) {
      this.innerHTML = `<div class="hkl-loading">…</div>`;
      return;
    }
    const detail = this._nav.detailId
      ? this._items.find((i) => i.id === this._nav.detailId)
      : null;
    if (this._nav.detailId && !detail) {
      this._renderGone();
      return;
    }
    if (detail) {
      this._renderDetail(detail);
      return;
    }
    this._renderList();
  }

  private _styles(): string {
    return `<style>
      .hkl-root { padding: 16px; max-width: 720px; margin: 0 auto; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
      .hkl-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
      .hkl-toolbar-title { font-size: 1.4rem; font-weight: 500; }
      .hkl-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 12px; margin-bottom: 8px; cursor: pointer; background: var(--card-background-color, #fff); }
      .hkl-name { font-weight: 500; }
      .hkl-value { color: var(--secondary-text-color, #666); }
      .hkl-empty, .hkl-gone { color: var(--secondary-text-color, #666); padding: 24px 0; }
      .hkl-btn { cursor: pointer; border: none; border-radius: 10px; padding: 8px 14px; background: var(--primary-color, #03a9f4); color: #fff; font-size: 0.95rem; }
      .hkl-btn.secondary { background: transparent; color: var(--primary-color, #03a9f4); }
      .hkl-form { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 12px; padding: 16px; margin-bottom: 16px; background: var(--card-background-color, #fff); }
      .hkl-form label { display: block; font-size: 0.85rem; color: var(--secondary-text-color, #666); margin: 8px 0 4px; }
      .hkl-form input { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid var(--divider-color, #ccc); border-radius: 8px; font-size: 1rem; }
      .hkl-form-actions { display: flex; gap: 8px; margin-top: 16px; }
      .hkl-error { color: var(--error-color, #db4437); margin: 8px 0; }
      .hkl-meta { color: var(--secondary-text-color, #666); font-size: 0.85rem; }
      .hkl-foot { color: var(--secondary-text-color, #999); font-size: 0.75rem; margin-top: 24px; text-align: center; }
    </style>`;
  }

  private _renderList(): void {
    const rows = this._items
      .map(
        (i) => `
        <div class="hkl-row detail-open" data-detail-id="${escapeHTML(i.id)}">
          <span class="hkl-name">${escapeHTML(i.name)}</span>
          <span class="hkl-value">${escapeHTML(i.value)}</span>
        </div>`,
      )
      .join('');
    const count = this._items.length
      ? `<div class="hkl-meta">${escapeHTML(tn('count', this._items.length))}</div>`
      : '';
    this.innerHTML = `${this._styles()}
      <div class="hkl-root">
        <div class="hkl-toolbar">
          <span class="hkl-toolbar-title">${escapeHTML(t('panel.title'))}</span>
          <button id="add-btn" class="hkl-btn">${escapeHTML(t('panel.add'))}</button>
        </div>
        ${this._error ? `<div class="hkl-error">${escapeHTML(this._error)}</div>` : ''}
        ${this._adding ? this._formHtml() : ''}
        ${count}
        ${this._items.length ? rows : `<div class="hkl-empty">${escapeHTML(t('panel.empty'))}</div>`}
        <div class="hkl-foot">v${escapeHTML(PANEL_VERSION)}</div>
      </div>`;
    this._wireList();
  }

  private _formHtml(): string {
    return `
      <form id="hkl-item-form" class="hkl-form">
        <label for="hkl-name">${escapeHTML(t('panel.name'))}</label>
        <input id="hkl-name" name="name" type="text" autocomplete="off" />
        <label for="hkl-value">${escapeHTML(t('panel.value'))}</label>
        <input id="hkl-value" name="value" type="number" value="0" />
        <div class="hkl-form-actions">
          <button type="submit" class="hkl-btn" id="hkl-save">${escapeHTML(t('panel.save'))}</button>
          <button type="button" class="hkl-btn secondary" id="hkl-cancel">${escapeHTML(t('panel.cancel'))}</button>
        </div>
      </form>`;
  }

  private _wireList(): void {
    this.querySelector('#add-btn')?.addEventListener('click', () => {
      this._adding = !this._adding;
      this._render();
    });
    this.querySelectorAll<HTMLElement>('.detail-open').forEach((el) => {
      el.addEventListener('click', () => {
        const id = el.dataset.detailId!;
        this._navigate({ view: 'list', detailId: id });
      });
    });
    const form = this.querySelector<HTMLFormElement>('#hkl-item-form');
    if (form) {
      this.querySelector('#hkl-cancel')?.addEventListener('click', () => {
        this._adding = false;
        this._render();
      });
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        void this._submitAdd(form);
      });
    }
  }

  private async _submitAdd(form: HTMLFormElement): Promise<void> {
    const name = (form.elements.namedItem('name') as HTMLInputElement).value.trim();
    const value = Number((form.elements.namedItem('value') as HTMLInputElement).value || '0');
    if (!name) {
      this._error = t('panel.name_required');
      this._render();
      return;
    }
    try {
      await this._api!.add(name, Math.trunc(value));
      this._adding = false;
      await this._refresh();
    } catch (err) {
      this._error = String(err);
      this._render();
    }
  }

  private _renderDetail(item: Item): void {
    this.innerHTML = `${this._styles()}
      <div class="hkl-root">
        <div class="hkl-toolbar">
          <button id="back-btn" class="hkl-btn secondary">← ${escapeHTML(t('panel.back'))}</button>
          <button id="del-btn" class="hkl-btn">${escapeHTML(t('panel.delete'))}</button>
        </div>
        <h2 class="hkl-name">${escapeHTML(item.name)}</h2>
        <form id="hkl-edit-form" class="hkl-form">
          <label for="hkl-name">${escapeHTML(t('panel.name'))}</label>
          <input id="hkl-name" name="name" type="text" value="${escapeHTML(item.name)}" />
          <label for="hkl-value">${escapeHTML(t('panel.value'))}</label>
          <input id="hkl-value" name="value" type="number" value="${escapeHTML(item.value)}" />
          <div class="hkl-form-actions">
            <button type="submit" class="hkl-btn">${escapeHTML(t('panel.save'))}</button>
          </div>
        </form>
        <div class="hkl-meta">${escapeHTML(t('panel.created'))}: ${escapeHTML(formatDate(item.created))}</div>
        ${this._error ? `<div class="hkl-error">${escapeHTML(this._error)}</div>` : ''}
      </div>`;
    this.querySelector('#back-btn')?.addEventListener('click', () =>
      this._navigate({ view: 'list', detailId: null }, true),
    );
    this.querySelector('#del-btn')?.addEventListener('click', () =>
      void this._delete(item.id),
    );
    const form = this.querySelector<HTMLFormElement>('#hkl-edit-form');
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      void this._submitEdit(item.id, form);
    });
  }

  private async _submitEdit(id: string, form: HTMLFormElement): Promise<void> {
    const name = (form.elements.namedItem('name') as HTMLInputElement).value.trim();
    const value = Number((form.elements.namedItem('value') as HTMLInputElement).value || '0');
    if (!name) {
      this._error = t('panel.name_required');
      this._render();
      return;
    }
    try {
      await this._api!.update(id, { name, value: Math.trunc(value) });
      await this._refresh();
    } catch (err) {
      this._error = String(err);
      this._render();
    }
  }

  private async _delete(id: string): Promise<void> {
    try {
      await this._api!.remove(id);
      await this._refresh();
      // Closing a deleted detail is a lateral move -> replace so Back doesn't
      // return to the gone object.
      this._navigate({ view: 'list', detailId: null }, true);
    } catch (err) {
      this._error = String(err);
      this._render();
    }
  }

  private _renderGone(): void {
    this.innerHTML = `${this._styles()}
      <div class="hkl-root">
        <div class="hkl-toolbar">
          <button id="back-btn" class="hkl-btn secondary">← ${escapeHTML(t('panel.back'))}</button>
        </div>
        <div class="hkl-gone">${escapeHTML(t('panel.gone'))}</div>
      </div>`;
    this.querySelector('#back-btn')?.addEventListener('click', () =>
      this._navigate({ view: 'list', detailId: null }, true),
    );
  }
}
