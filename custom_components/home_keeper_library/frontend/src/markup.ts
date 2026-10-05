// Markup helpers that the tab views share. Each helper returns an HTML string
// and escapes every user value.

import { t } from './i18n';
import type { Book, Lib, Person, ReadingStatus } from './types';
import { coverColors, escapeHTML, initials, personColor, type Index, type TabRoute } from './utils';

/** The panel URL of the tab. A tab path is added after it. */
export const TAB_BASE = '/home-keeper/library';

const svg = (d: string, size = 18) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;

export const ICONS = {
  scan: svg('<path d="M3 7V4h3M18 4h3v3M21 17v3h-3M6 20H3v-3M7 8v8M10 8v8M13 8v8M17 8v8"/>'),
  search: svg('<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>'),
  grid: svg('<rect x="4" y="4" width="6" height="7"/><rect x="14" y="4" width="6" height="7"/><rect x="4" y="14" width="6" height="7"/><rect x="14" y="14" width="6" height="7"/>', 16),
  rows: svg('<path d="M4 6h16M4 12h16M4 18h16"/>', 16),
  home: svg('<path d="M3 11l9-7 9 7v9H3z"/>', 14),
  back: svg('<path d="M15 6l-6 6 6 6"/>'),
  close: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  star: '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  torch: svg('<path d="M9 2h6l-1 6h-4zM10 8h4v12a2 2 0 01-4 0z"/>'),
  check: svg('<path d="M5 12l5 5 9-10"/>', 16),
};

/** The full panel href of a tab path, for a real link. */
export function href(path: string): string {
  return `${TAB_BASE}${path}`;
}

/** A link inside the tab. The click goes through `host.navigate`. */
export function link(path: string, label: string, cls = ''): string {
  return `<a href="${escapeHTML(href(path))}" data-act="nav" data-path="${escapeHTML(path)}"${cls ? ` class="${cls}"` : ''}>${label}</a>`;
}

/** The cover of a book: the image, or a colored block with the title. */
export function cover(book: Book, size: 'tile' | 'thumb' | 'large' = 'tile', badge = ''): string {
  const { bg, ink } = coverColors(book.id);
  const author = book.authors[0] ?? '';
  const img = book.cover_url
    ? `<img src="${escapeHTML(book.cover_url)}" alt="" loading="lazy" />`
    : `<span class="hkl-cover-title">${escapeHTML(book.title)}</span>${size === 'thumb' ? '' : `<span class="hkl-cover-author">${escapeHTML(author)}</span>`}`;
  return `<span class="hkl-cover hkl-cover-${size}${book.cover_url ? ' has-img' : ''}" style="--c:${bg};--ink:${ink}" aria-hidden="true">${img}${badge}</span>`;
}

/** A round person mark with the initial, and the name as its label. */
export function personDot(person: Person | undefined, status: ReadingStatus | null = null): string {
  if (!person) return '';
  const ring = status === 'read' ? ' ring-read' : status === 'reading' ? ' ring-reading' : '';
  const label = status ? `${person.name}: ${statusLabel(status)}` : person.name;
  return `<span class="hkl-dot${ring}" style="--p:${personColor(person.id)}" title="${escapeHTML(label)}" role="img" aria-label="${escapeHTML(label)}">${escapeHTML(initials(person.name))}</span>`;
}

/** The label of a reading status. Null is "Not read". */
export function statusLabel(status: ReadingStatus | null): string {
  return t(`status.${status ?? 'none'}`);
}

/** A status pill with a text label. */
export function statusPill(status: ReadingStatus | null): string {
  return `<span class="hkl-pill st-${status ?? 'none'}">${escapeHTML(statusLabel(status))}</span>`;
}

/** `<option>` elements. */
export function options(items: Array<[string, string]>, selected: string | null | undefined): string {
  return items
    .map(
      ([value, label]) =>
        `<option value="${escapeHTML(value)}"${value === (selected ?? '') ? ' selected' : ''}>${escapeHTML(label)}</option>`,
    )
    .join('');
}

/** The shelf options in display order, with "No shelf" first. */
export function shelfOptions(lib: Lib, idx: Index, selected: string | null, withNone = true): string {
  const items: Array<[string, string]> = withNone ? [['', t('common.no_shelf')]] : [];
  for (const room of lib.rooms) {
    for (const bc of lib.bookcases.filter((c) => c.room_id === room.id)) {
      for (const sh of lib.shelves.filter((s) => s.bookcase_id === bc.id)) {
        items.push([sh.id, `${room.name} › ${bc.name} › ${sh.name}`]);
      }
    }
  }
  void idx;
  return options(items, selected);
}

/** The person options. */
export function personOptions(lib: Lib, selected: string | null): string {
  return options(
    lib.people.map((p) => [p.id, p.name]),
    selected,
  );
}

/** The format options of a copy or a loan. */
export function formatOptions(selected: string | null, withEmpty = false): string {
  const items: Array<[string, string]> = ['hardcover', 'paperback', 'ebook', 'audiobook', 'other'].map((f) => [
    f,
    t(`format.kind_${f}`),
  ]);
  return options(withEmpty ? [['', t('common.none')], ...items] : items, selected);
}

/** The top navigation of the tab, with the view actions on the right. */
export function navBar(route: TabRoute, counts: { loans: number; wishlist: number }, actions = ''): string {
  const items: Array<[string, string, string, number | null]> = [
    ['books', '/books', t('nav.books'), null],
    ['shelves', '/shelves', t('nav.shelves'), null],
    ['loans', '/loans', t('nav.loans'), counts.loans],
    ['wishlist', '/wishlist', t('nav.wishlist'), counts.wishlist],
    ['settings', '/settings', t('nav.settings'), null],
  ];
  const current = route.view === 'book' || route.view === 'import' ? 'books' : route.view;
  const chips = items
    .map(([view, path, label, count]) => {
      const on = view === current;
      const badge = count ? ` <span class="hkl-badge${view === 'loans' ? ' warn' : ''}">${count}</span>` : '';
      return `<button class="hkl-navchip${on ? ' on' : ''}" data-act="nav" data-path="${path}" data-k="nav-${view}"${on ? ' aria-current="page"' : ''}>${escapeHTML(label)}${badge}</button>`;
    })
    .join('');
  return `<div class="hkl-navrow"><nav class="hkl-nav" aria-label="${escapeHTML(t('nav.label'))}">${chips}</nav><div class="hkl-spacer"></div><div class="hkl-actions">${actions}</div></div>`;
}

/** A button. `weight` is primary, tonal or text. */
export function button(label: string, act: string, weight: 'primary' | 'tonal' | 'text' | 'outline' | 'danger' = 'tonal', attrs = ''): string {
  return `<button class="hkl-btn ${weight}" data-act="${act}" ${attrs}>${label}</button>`;
}
