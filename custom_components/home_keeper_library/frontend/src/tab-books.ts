// The Books view (grid and rows) and the Book detail view.

import { formatDate, formatMoney, t, tn } from './i18n';
import { markdownBlock } from './markdown';
import {
  button,
  cover,
  taskLinkHtml,
  ICONS,
  link,
  navBar,
  options,
  personDot,
  statusLabel,
  statusPill,
} from './markup';
import type { ViewCtx } from './tab-types';
import type { Book, Copy, Loan, ReadingStatus } from './types';
import {
  allSubjects,
  buildPath,
  dueState,
  escapeHTML,
  filterBooks,
  hasFilters,
  locationLabel,
  progress,
  readFilters,
  readingOf,
  shelfPath,
  shortLocation,
  SORT_KEYS,
  STATUS_FILTERS,
  statusCounts,
  type BookFilters,
} from './utils';

export function navCounts(ctx: ViewCtx): { loans: number; wishlist: number } {
  return {
    loans: ctx.lib.loans.filter((l) => !l.returned).length,
    wishlist: ctx.lib.books.filter((b) => b.wishlist && !b.wishlist.bought).length,
  };
}

function menu(label: string, key: string, items: Array<[string, string]>, value: string): string {
  return `<label class="hkl-menu"><span class="hkl-menu-label">${escapeHTML(label)}</span><select data-chg="filter" data-key="${key}" data-k="f-${key}">${options(items, value)}</select></label>`;
}

function readerDots(ctx: ViewCtx, book: Book): string {
  return ctx.lib.people
    .map((p) => {
      const st = readingOf(book, p.id)?.status ?? null;
      return st === 'read' || st === 'reading' ? personDot(p, st) : '';
    })
    .join('');
}

function loanPill(ctx: ViewCtx, book: Book): string {
  const loan = ctx.idx.activeLoans.get(book.id)?.[0];
  if (!loan) return '';
  const due = loan.due ? ` · ${t('loan.due_short', { date: formatDate(loan.due, false) })}` : '';
  const label = loan.direction === 'out' ? t('loan.lent_pill', { party: loan.party ?? '' }) : t('loan.borrowed_pill', { party: loan.party ?? '' });
  const late = dueState(loan.due, ctx.today).kind === 'overdue' ? ' late' : '';
  return `<span class="hkl-pill loan${late}">${escapeHTML(label)}${escapeHTML(due)}</span>`;
}

function firstShelf(ctx: ViewCtx, book: Book): string | null {
  const copies = ctx.idx.copiesByBook.get(book.id) ?? [];
  return copies.find((c) => c.shelf_id)?.shelf_id ?? null;
}

function tile(ctx: ViewCtx, book: Book): string {
  const path = `/books/${encodeURIComponent(book.id)}`;
  const loc = book.owned ? shortLocation(ctx.idx, firstShelf(ctx, book)) || t('common.no_shelf') : '';
  const badge = book.cover?.kind === 'custom' ? `<span class="hkl-cover-badge">${escapeHTML(t('book.custom_cover'))}</span>` : '';
  return `<a class="hkl-tile" href="/home-keeper/library${escapeHTML(path)}" data-act="nav" data-path="${escapeHTML(path)}" data-k="b-${escapeHTML(book.id)}">
    ${cover(book, 'tile', badge)}
    <span class="hkl-tile-title">${escapeHTML(book.title)}</span>
    <span class="hkl-tile-author">${escapeHTML(book.authors.join(', '))}</span>
    <span class="hkl-tile-meta">${loc ? `<span class="hkl-loc">${escapeHTML(loc)}</span>` : ''}${book.wishlist ? `<span class="hkl-loc">${escapeHTML(t('nav.wishlist'))}</span>` : ''}</span>
    <span class="hkl-tile-readers">${readerDots(ctx, book)}</span>
    ${book.needs_details ? `<span class="hkl-pill warn">${escapeHTML(t('filter.needs'))}</span>` : ''}
    ${loanPill(ctx, book)}
  </a>`;
}

function row(ctx: ViewCtx, book: Book): string {
  const path = `/books/${encodeURIComponent(book.id)}`;
  const loc = book.owned ? shortLocation(ctx.idx, firstShelf(ctx, book)) || t('common.no_shelf') : t('book.not_owned');
  return `<a class="hkl-row" href="/home-keeper/library${escapeHTML(path)}" data-act="nav" data-path="${escapeHTML(path)}" data-k="b-${escapeHTML(book.id)}">
    ${cover(book, 'thumb')}
    <span class="hkl-row-main"><span class="hkl-row-title">${escapeHTML(book.title)}</span><span class="hkl-row-sub">${escapeHTML(book.authors.join(', '))}</span><span class="hkl-row-loc">${escapeHTML(loc)}</span></span>
    <span class="hkl-row-dots">${readerDots(ctx, book)}${loanPill(ctx, book)}</span>
    ${statusPill(readingOf(book, ctx.me)?.status ?? null)}
  </a>`;
}

function summaryLine(ctx: ViewCtx, f: BookFilters, count: number): string {
  const parts: string[] = [];
  if (f.room) parts.push(ctx.idx.room.get(f.room)?.name ?? '');
  if (f.shelf === 'none') parts.push(t('common.no_shelf'));
  else if (f.shelf) parts.push(ctx.idx.shelf.get(f.shelf)?.name ?? '');
  if (f.reader) parts.push(t('filter.read_by_name', { name: ctx.idx.person.get(f.reader)?.name ?? '' }));
  if (f.subject) parts.push(f.subject);
  if (f.owned === 'no') parts.push(t('filter.owned_no'));
  if (f.owned === 'all') parts.push(t('filter.owned_all'));
  if (f.q) parts.push(`"${f.q}"`);
  const label = parts.filter(Boolean).join(' · ');
  return `<div class="hkl-summary">${label ? `<span class="hkl-eyebrow">${escapeHTML(label)}</span>` : ''}<span class="hkl-badge">${escapeHTML(tn('count.books', count))}</span>${hasFilters(f) ? `<button class="hkl-link" data-act="clear-filters" data-k="clear">${escapeHTML(t('filter.clear'))}</button>` : ''}</div>`;
}

/** The Books view. */
export function renderBooks(ctx: ViewCtx): string {
  const f = readFilters(ctx.route.query);
  const fctx = { idx: ctx.idx, me: ctx.me };
  const books = filterBooks(ctx.lib.books, f, fctx);
  const counts = statusCounts(ctx.lib.books, f, fctx);
  const chips = STATUS_FILTERS.map((s) => {
    const on = f.status === s;
    return `<button class="hkl-seg${on ? ' on' : ''}" data-act="status" data-value="${s}" data-k="st-${s}" aria-pressed="${on}">${escapeHTML(t(`filter.${s}`))} <span class="hkl-seg-n">${counts[s]}</span></button>`;
  }).join('');
  const rooms: Array<[string, string]> = [['', t('filter.any')], ...ctx.lib.rooms.map((r): [string, string] => [r.id, r.name])];
  const shelves: Array<[string, string]> = [['', t('filter.any')], ['none', t('common.no_shelf')]];
  for (const sh of ctx.lib.shelves) {
    const { room, bookcase } = shelfPath(ctx.idx, sh.id);
    if (f.room && room?.id !== f.room) continue;
    shelves.push([sh.id, [room?.name, bookcase?.name, sh.name].filter(Boolean).join(' › ')]);
  }
  const readers: Array<[string, string]> = [['', t('filter.anyone')], ...ctx.lib.people.map((p): [string, string] => [p.id, p.name])];
  const subjects: Array<[string, string]> = [['', t('filter.any')], ...allSubjects(ctx.lib.books).map((s): [string, string] => [s, s])];
  const sorts = SORT_KEYS.map((k): [string, string] => [k, t(`sort.${k}`)]);
  const owned: Array<[string, string]> = [
    ['yes', t('filter.owned_yes')],
    ['all', t('filter.owned_all')],
    ['no', t('filter.owned_no')],
  ];
  const shown = books.slice(0, ctx.ui.limit);
  const list = f.view === 'rows'
    ? `<div class="hkl-rows">${shown.map((b) => row(ctx, b)).join('')}</div>`
    : `<div class="hkl-grid">${shown.map((b) => tile(ctx, b)).join('')}</div>`;
  const more = books.length > shown.length
    ? `<div class="hkl-more">${button(escapeHTML(t('books.show_more', { n: books.length - shown.length })), 'more', 'outline', 'data-k="more"')}</div>`
    : '';
  const empty = !books.length
    ? `<div class="hkl-empty">${escapeHTML(ctx.lib.books.length ? t('books.no_match') : t('books.empty'))}</div>`
    : '';
  const actions = `${button(`${ICONS.scan}${escapeHTML(t('action.scan_books'))}`, 'nav', 'primary', 'data-path="/scan" data-k="scan-books"')}
    ${button(escapeHTML(t('action.add_book')), 'add-book', 'tonal', 'data-k="add-book"')}
    ${button(escapeHTML(t('action.import')), 'nav', 'text', 'data-path="/import" data-k="import"')}`;
  return `${navBar(ctx.route, navCounts(ctx), actions)}
  <div class="hkl-filterbar">
    <div class="hkl-segs" role="group" aria-label="${escapeHTML(t('filter.status_label'))}">${chips}</div>
    <label class="hkl-search">${ICONS.search}<input type="search" data-input="q" data-k="q" aria-label="${escapeHTML(t('books.search_label'))}" placeholder="${escapeHTML(t('books.search_placeholder'))}" value="${escapeHTML(f.q)}" /></label>
  </div>
  <div class="hkl-menus">
    ${menu(t('filter.room'), 'room', rooms, f.room)}
    ${menu(t('filter.shelf'), 'shelf', shelves, f.shelf)}
    ${menu(t('filter.read_by'), 'reader', readers, f.reader)}
    ${menu(t('filter.subject'), 'subject', subjects, f.subject)}
    ${menu(t('filter.owned'), 'owned', owned, f.owned)}
    ${menu(t('filter.sort'), 'sort', sorts, f.sort)}
    <div class="hkl-spacer"></div>
    <div class="hkl-toggle" role="group" aria-label="${escapeHTML(t('books.layout'))}">
      <button data-act="layout" data-value="grid" data-k="lay-grid" class="${f.view === 'grid' ? 'on' : ''}" aria-pressed="${f.view === 'grid'}" aria-label="${escapeHTML(t('books.layout_grid'))}" title="${escapeHTML(t('books.layout_grid'))}">${ICONS.grid}</button>
      <button data-act="layout" data-value="rows" data-k="lay-rows" class="${f.view === 'rows' ? 'on' : ''}" aria-pressed="${f.view === 'rows'}" aria-label="${escapeHTML(t('books.layout_rows'))}" title="${escapeHTML(t('books.layout_rows'))}">${ICONS.rows}</button>
    </div>
  </div>
  ${summaryLine(ctx, f, books.length)}
  ${empty}${list}${more}
  <div class="hkl-legend"><span><span class="hkl-ring ring-read" aria-hidden="true"></span>${escapeHTML(t('status.read'))}</span><span><span class="hkl-ring ring-reading" aria-hidden="true"></span>${escapeHTML(t('status.reading'))}</span></div>`;
}

// ── Book detail ──────────────────────────────────────────────────────────────

const STATUSES: ReadingStatus[] = ['want', 'reading', 'read', 'dnf'];

function stars(rating: number | null): string {
  const out: string[] = [];
  for (let i = 1; i <= 5; i++) {
    const on = rating != null && i <= rating;
    out.push(`<button class="hkl-star${on ? ' on' : ''}" data-act="rate" data-value="${i}" data-k="star-${i}" aria-label="${escapeHTML(tn('book.stars', i))}" aria-pressed="${on}">${ICONS.star}</button>`);
  }
  return `<div class="hkl-stars" role="group" aria-label="${escapeHTML(t('book.rating'))}">${out.join('')}</div>`;
}

function loanBox(ctx: ViewCtx, loan: Loan): string {
  const due = dueState(loan.due, ctx.today);
  const dueText = loan.due
    ? due.kind === 'overdue'
      ? tn('loan.overdue_days', due.days)
      : t('loan.due_on', { date: formatDate(loan.due) })
    : t('loan.no_date');
  const task = loan.hk_task_id
    ? `${taskLinkHtml(ctx, loan.hk_task_id)} · `
    : '';
  const head = loan.direction === 'out' ? t('book.loan_out') : t('book.loan_in');
  return `<div class="hkl-box${due.kind === 'overdue' ? ' late' : ''}">
    <span class="hkl-eyebrow">${escapeHTML(head)}</span>
    <span class="hkl-box-main">${escapeHTML(t('loan.party_since', { party: loan.party ?? '', date: formatDate(loan.started) }))}</span>
    <span class="hkl-box-sub">${task}${escapeHTML(dueText)}</span>
    <span class="hkl-box-actions">${button(escapeHTML(t('action.return')), 'return-loan', 'tonal', `data-id="${escapeHTML(loan.id)}" data-k="ret-${escapeHTML(loan.id)}"`)}</span>
  </div>`;
}

function copyBox(ctx: ViewCtx, copy: Copy, index: number, total: number): string {
  const loc = copy.shelf_id ? locationLabel(ctx.idx, copy.shelf_id) : t('common.no_shelf');
  const room = shelfPath(ctx.idx, copy.shelf_id).room;
  const label = total > 1 ? t('book.location_n', { n: index + 1 }) : t('book.location');
  const lent = ctx.idx.loanByCopy.get(copy.id);
  return `<div class="hkl-box">
    <span class="hkl-eyebrow">${escapeHTML(label)}</span>
    <span class="hkl-box-main">${escapeHTML(loc)}</span>
    <span class="hkl-box-sub">${escapeHTML(t(`format.kind_${copy.format}`))}${lent ? ` · ${escapeHTML(t('loan.lent_pill', { party: lent.party ?? '' }))}` : ''}</span>
    <span class="hkl-box-actions">${button(escapeHTML(t('action.move')), 'move-copy', 'tonal', `data-id="${escapeHTML(copy.id)}" data-k="mv-${escapeHTML(copy.id)}"`)}${room ? button(escapeHTML(t('action.open_shelf')), 'nav', 'text', `data-path="/shelves/${escapeHTML(encodeURIComponent(room.id))}" data-k="os-${escapeHTML(copy.id)}"`) : ''}</span>
  </div>`;
}

function copyDetails(ctx: ViewCtx, copies: Copy[]): string {
  if (!copies.length) {
    return `<section class="hkl-card"><h2>${escapeHTML(t('book.copy_details'))}</h2><p class="hkl-muted">${escapeHTML(t('book.no_copies'))}</p>${button(escapeHTML(t('action.add_copy')), 'add-copy', 'tonal', 'data-k="add-copy"')}</section>`;
  }
  const cur = ctx.lib.currency;
  const blocks = copies
    .map((c) => {
      const kv = (k: string, v: string) => (v ? `<span class="hkl-kv"><span>${escapeHTML(k)}</span><span>${escapeHTML(v)}</span></span>` : '');
      const bought = [c.acquired ? formatDate(c.acquired) : '', c.acquired_from ?? ''].filter(Boolean).join(' · ');
      const flags = [c.signed ? t('copy.signed') : '', c.first_edition ? t('copy.first_edition') : ''].filter(Boolean);
      return `<div class="hkl-copy">
        ${copies.length > 1 ? `<span class="hkl-eyebrow">${escapeHTML(locationLabel(ctx.idx, c.shelf_id) || t('common.no_shelf'))}</span>` : ''}
        ${kv(t('copy.format'), t(`format.kind_${c.format}`))}
        ${kv(t('copy.condition'), c.condition ? t(`condition.${c.condition}`) : '')}
        ${kv(t('copy.bought'), bought)}
        ${kv(t('copy.price'), formatMoney(c.price, cur))}
        ${kv(t('copy.value'), formatMoney(c.value, cur))}
        ${flags.length ? `<span class="hkl-chips">${flags.map((x) => `<span class="hkl-chip">${escapeHTML(x)}</span>`).join('')}</span>` : ''}
        ${c.note ? `<span class="hkl-muted">${escapeHTML(c.note)}</span>` : ''}
        <span class="hkl-box-actions">${button(escapeHTML(t('action.edit_copy')), 'edit-copy', 'text', `data-id="${escapeHTML(c.id)}" data-k="ec-${escapeHTML(c.id)}"`)}${button(escapeHTML(t('action.delete_copy')), 'delete-copy', 'text', `data-id="${escapeHTML(c.id)}" data-k="dc-${escapeHTML(c.id)}"`)}</span>
      </div>`;
    })
    .join('');
  return `<section class="hkl-card"><h2>${escapeHTML(t('book.copy_details'))}</h2>${blocks}${button(escapeHTML(t('action.add_copy')), 'add-copy', 'text', 'data-k="add-copy"')}</section>`;
}

function readingSection(ctx: ViewCtx, book: Book): string {
  const pid = ctx.ui.readingPerson ?? ctx.me;
  const row = readingOf(book, pid);
  const st = row?.status ?? null;
  const seg = STATUSES.map((s) => {
    const on = st === s;
    return `<button class="hkl-seg${on ? ' on' : ''}" data-act="set-status" data-value="${s}" data-k="rs-${s}" aria-pressed="${on}">${on ? ICONS.check : ''}${escapeHTML(statusLabel(s))}</button>`;
  }).join('');
  const facts: string[] = [];
  if (row?.status === 'read' && row.finished) facts.push(t('book.read_on', { date: formatDate(row.finished) }));
  if (row && row.read_count > 1) facts.push(tn('book.read_times', row.read_count));
  const people = ctx.lib.people.filter((p) => p.id !== pid);
  const household = people
    .map((p) => {
      const r = readingOf(book, p.id);
      const pr = r?.status === 'reading' ? progress(r.page, book.pages) : null;
      const page = r?.status === 'reading' && r.page != null
        ? book.pages ? t('book.page_of', { page: r.page, pages: book.pages }) : t('book.page_n', { page: r.page })
        : '';
      const stars = r?.rating ? ` · ${tn('book.stars', r.rating)}` : '';
      return `<div class="hkl-hh">${personDot(p)}<span class="hkl-hh-name">${escapeHTML(p.name)}</span><span class="hkl-pill st-${r?.status ?? 'none'}">${escapeHTML(statusLabel(r?.status ?? null))}</span>${pr != null ? `<span class="hkl-bar" role="img" aria-label="${pr}%"><span style="width:${pr}%"></span></span>` : ''}<span class="hkl-muted">${escapeHTML(page + stars)}</span></div>`;
    })
    .join('');
  const pick = ctx.lib.people.length > 1
    ? `<label class="hkl-inline">${escapeHTML(t('common.person'))} <select data-chg="reading-person" data-k="rp">${options(ctx.lib.people.map((p) => [p.id, p.name]), pid)}</select></label>`
    : `<span class="hkl-muted">${escapeHTML(t('common.person'))} ${escapeHTML(ctx.idx.person.get(pid ?? '')?.name ?? '')}</span>`;
  const pageField = `<label class="hkl-field small">${escapeHTML(t('book.page'))}<input type="number" min="0" inputmode="numeric" data-chg="reading-field" data-key="page" data-k="r-page" value="${escapeHTML(row?.page ?? '')}" /></label>`;
  const started = `<label class="hkl-field small">${escapeHTML(t('book.started'))}<input type="date" data-chg="reading-field" data-key="started" data-k="r-started" value="${escapeHTML(row?.started ?? '')}" /></label>`;
  const finished = `<label class="hkl-field small">${escapeHTML(t('book.finished'))}<input type="date" data-chg="reading-field" data-key="finished" data-k="r-finished" value="${escapeHTML(row?.finished ?? '')}" /></label>`;
  const count = `<label class="hkl-field small">${escapeHTML(t('book.read_count'))}<input type="number" min="0" data-chg="reading-field" data-key="read_count" data-k="r-count" value="${escapeHTML(row?.read_count ?? 0)}" /></label>`;
  return `<section class="hkl-card">
    <div class="hkl-card-head"><h2>${escapeHTML(t('book.reading_status'))}</h2>${pick}</div>
    <div class="hkl-reading">
      <div class="hkl-segs" role="group" aria-label="${escapeHTML(t('book.reading_status'))}">${seg}</div>
      ${stars(row?.rating ?? null)}
      ${facts.length ? `<span class="hkl-muted">${escapeHTML(facts.join(' · '))}</span>` : ''}
    </div>
    <div class="hkl-fields">${pageField}${started}${finished}${count}</div>
    ${household ? `<span class="hkl-eyebrow">${escapeHTML(t('book.household'))}</span><div class="hkl-household">${household}</div>` : ''}
  </section>`;
}

function notesSection(ctx: ViewCtx, book: Book): string {
  const pid = ctx.ui.readingPerson ?? ctx.me;
  const tab = ctx.ui.notesTab;
  const text = tab === 'shared' ? book.shared_notes : (readingOf(book, pid)?.private_notes ?? '');
  const tabs = (['shared', 'private'] as const)
    .map((k) => `<button class="hkl-subtab${tab === k ? ' on' : ''}" data-act="notes-tab" data-value="${k}" data-k="nt-${k}" aria-pressed="${tab === k}">${escapeHTML(t(`book.notes_${k}`))}</button>`)
    .join('');
  const body = ctx.ui.editNotes
    ? `<form data-form="notes" class="hkl-notes-form"><textarea name="text" rows="6" data-k="notes-text" aria-label="${escapeHTML(t(`book.notes_${tab}`))}">${escapeHTML(text)}</textarea><div class="hkl-dlg-actions">${button(escapeHTML(t('action.cancel')), 'notes-cancel', 'text', 'type="button" data-k="notes-cancel"')}<button class="hkl-btn primary" type="submit" data-k="notes-save">${escapeHTML(t('action.save'))}</button></div></form>`
    : `${markdownBlock(text) || `<p class="hkl-muted">${escapeHTML(t('book.no_notes'))}</p>`}${button(escapeHTML(t('action.edit_notes')), 'notes-edit', 'text', 'data-k="notes-edit"')}`;
  return `<section class="hkl-card"><div class="hkl-subtabs">${tabs}</div>${body}${tab === 'private' ? `<span class="hkl-muted small">${escapeHTML(t('book.private_hint'))}</span>` : ''}</section>`;
}

/** The Book detail view. */
export function renderBook(ctx: ViewCtx, book: Book | undefined): string {
  const back = `<button class="hkl-back" data-act="back" data-k="back">${ICONS.back}${escapeHTML(t('action.back'))}</button>`;
  if (!book) {
    return `${navBar(ctx.route, navCounts(ctx))}${back}<div class="hkl-empty">${escapeHTML(t('book.gone'))}</div>`;
  }
  const copies = ctx.idx.copiesByBook.get(book.id) ?? [];
  const loans = ctx.idx.activeLoans.get(book.id) ?? [];
  const series = book.series?.name
    ? ` · ${link(booksPath({ q: book.series.name }), escapeHTML(book.series.number != null && book.series.number !== '' ? t('book.series_n', { name: book.series.name, n: book.series.number }) : book.series.name))}`
    : '';
  const authors = book.authors.map((a) => link(booksPath({ q: a }), escapeHTML(a))).join(', ');
  const meta = [
    book.published,
    book.publisher,
    book.pages ? tn('book.pages', book.pages) : '',
    book.isbn13 ? `ISBN ${book.isbn13}` : book.isbn10 ? `ISBN ${book.isbn10}` : '',
  ].filter(Boolean).map((x) => escapeHTML(x));
  const olKey = book.openlibrary?.edition_key || book.openlibrary?.work_key;
  if (olKey) {
    meta.push(`<a href="https://openlibrary.org/${olKey.startsWith('/') ? '' : 'books/'}${escapeHTML(olKey.replace(/^\//, ''))}" target="_blank" rel="noreferrer noopener">Open Library</a>`);
  }
  const tags = [...book.subjects.slice(0, 6), ...book.tags]
    .map((x) => `<span class="hkl-chip">${escapeHTML(x)}</span>`)
    .join('');
  const wish = book.wishlist
    ? `<div class="hkl-banner">${escapeHTML(t('book.on_wishlist', { name: ctx.idx.person.get(book.wishlist.person_id)?.name ?? '' }))}${button(escapeHTML(t('action.got_it')), 'got-it', 'tonal', `data-id="${escapeHTML(book.id)}" data-k="got-it"`)}</div>`
    : '';
  const needs = book.needs_details
    ? `<div class="hkl-banner warn">${escapeHTML(t('book.needs_details'))}${button(escapeHTML(t('action.add_details')), 'edit-book', 'tonal', 'data-k="needs-edit"')}</div>`
    : '';
  const badge = book.cover?.kind === 'custom' ? `<span class="hkl-cover-badge">${escapeHTML(t('book.custom_cover'))}</span>` : '';
  const useOl = book.openlibrary?.cover_id && book.cover?.kind !== 'openlibrary'
    ? button(escapeHTML(t('action.use_ol_cover')), 'use-ol-cover', 'text', 'data-k="use-ol"')
    : '';
  const actions = [
    button(escapeHTML(t('action.edit')), 'edit-book', 'tonal', 'data-k="edit-book"'),
    copies.some((c) => !ctx.idx.loanByCopy.has(c.id)) ? button(escapeHTML(t('action.lend')), 'lend', 'tonal', `data-book="${escapeHTML(book.id)}" data-k="lend"`) : '',
    button(escapeHTML(t('action.refresh')), 'refresh-book', 'tonal', 'data-k="refresh"'),
    book.wishlist ? '' : button(escapeHTML(t('action.add_to_wishlist')), 'wish-this', 'text', 'data-k="wish-this"'),
    button(escapeHTML(t('action.delete')), 'delete-book', 'danger', 'data-k="delete-book"'),
  ].join('');
  return `${navBar(ctx.route, navCounts(ctx))}
  ${back}
  <div class="hkl-detail">
    <div class="hkl-detail-cover">
      ${cover(book, 'large', badge)}
      <div class="hkl-cover-actions">${button(escapeHTML(t('action.change_cover')), 'change-cover', 'tonal', 'data-k="change-cover"')}${useOl}</div>
      <input type="file" accept="image/jpeg,image/png,image/webp" data-chg="cover-file" data-k="cover-file" hidden />
    </div>
    <div class="hkl-detail-info">
      <h1>${escapeHTML(book.title)}</h1>
      ${book.subtitle ? `<span class="hkl-subtitle">${escapeHTML(book.subtitle)}</span>` : ''}
      <span class="hkl-byline">${authors}${series}</span>
      <span class="hkl-muted">${meta.join(' · ')}</span>
      ${tags ? `<div class="hkl-chips">${tags}</div>` : ''}
      ${needs}${wish}
      <div class="hkl-boxes">${copies.map((c, i) => copyBox(ctx, c, i, copies.length)).join('')}${loans.map((l) => loanBox(ctx, l)).join('')}</div>
      ${book.description ? `<p class="hkl-desc">${escapeHTML(book.description)}</p>` : ''}
    </div>
  </div>
  ${readingSection(ctx, book)}
  <div class="hkl-two">${notesSection(ctx, book)}${copyDetails(ctx, copies)}</div>
  <div class="hkl-detail-actions">${actions}</div>`;
}

/** The path of the book list for a filter set. */
export function booksPath(query: Record<string, string>): string {
  return buildPath({ view: 'books', query });
}
