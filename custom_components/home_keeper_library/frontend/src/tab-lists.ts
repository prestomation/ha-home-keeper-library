// The Loans, Wishlist and Settings views.

import { formatDate, t, tn } from './i18n';
import { button, cover, ICONS, navBar, options, personDot, statusLabel } from './markup';
import { navCounts } from './tab-books';
import type { ViewCtx } from './tab-types';
import type { Book, Loan } from './types';
import { dueState, escapeHTML, loansFor, readingOf, type LoanTab } from './utils';

const LOAN_TABS: LoanTab[] = ['out', 'in', 'returned'];

function dueText(ctx: ViewCtx, loan: Loan): { text: string; cls: string } {
  if (loan.returned) return { text: t('loan.returned_on', { date: formatDate(loan.returned) }), cls: '' };
  const due = dueState(loan.due, ctx.today);
  switch (due.kind) {
    case 'none':
      return { text: t('loan.no_date'), cls: '' };
    case 'overdue':
      return { text: tn('loan.overdue_days', due.days), cls: 'late' };
    case 'today':
      return { text: t('loan.due_today'), cls: 'soon' };
    case 'soon':
      return { text: tn('loan.due_in_days', due.days), cls: 'soon' };
    default:
      return { text: tn('loan.due_in_days', due.days), cls: '' };
  }
}

function loanRow(ctx: ViewCtx, loan: Loan): string {
  const book = ctx.idx.book.get(loan.book_id);
  const title = book?.title ?? t('loan.unknown_book');
  const meta: string[] = [loan.party ?? ''];
  if (loan.direction === 'in') {
    const person = loan.person_id ? ctx.idx.person.get(loan.person_id) : undefined;
    if (person) meta.push(person.name);
    if (loan.format) meta.push(t(`format.kind_${loan.format}`));
    if (book && loan.person_id) meta.push(statusLabel(readingOf(book, loan.person_id)?.status ?? null));
  } else {
    meta.push(t('loan.since', { date: formatDate(loan.started) }));
  }
  const due = dueText(ctx, loan);
  const task = loan.hk_task_id && !loan.returned
    ? `<a class="hkl-task" href="${escapeHTML(ctx.taskLink(loan.hk_task_id))}">${ICONS.home}${escapeHTML(t('loan.task'))}</a>`
    : '';
  const id = escapeHTML(loan.id);
  const act = loan.returned
    ? button(escapeHTML(t('action.delete')), 'delete-loan', 'text', `data-id="${id}" data-k="dl-${id}"`)
    : button(escapeHTML(t('action.return')), 'return-loan', 'tonal', `data-id="${id}" data-k="rl-${id}"`);
  const open = book ? `data-act="nav" data-path="/books/${escapeHTML(encodeURIComponent(book.id))}"` : '';
  return `<div class="hkl-listrow ${due.cls}">
    <span class="hkl-edge"></span>
    ${book ? cover(book, 'thumb') : ''}
    <span class="hkl-row-main"><button class="hkl-row-title hkl-link plain" ${open} data-k="lb-${id}">${escapeHTML(title)}</button><span class="hkl-row-sub">${escapeHTML(meta.filter(Boolean).join(' · '))}</span>${loan.note ? `<span class="hkl-row-loc">${escapeHTML(loan.note)}</span>` : ''}</span>
    ${task}
    <span class="hkl-pill due ${due.cls}">${escapeHTML(due.text)}</span>
    ${act}
  </div>`;
}

/** The Loans view. */
export function renderLoans(ctx: ViewCtx): string {
  const tab = (LOAN_TABS.includes(ctx.route.query.tab as LoanTab) ? ctx.route.query.tab : 'out') as LoanTab;
  const tabs = LOAN_TABS.map((k) => {
    const on = k === tab;
    const n = loansFor(ctx.lib.loans, k).length;
    return `<button class="hkl-subtab${on ? ' on' : ''}" data-act="nav" data-replace="1" data-path="/loans${k === 'out' ? '' : `?tab=${k}`}" data-k="lt-${k}"${on ? ' aria-current="page"' : ''}>${escapeHTML(t(`loans.tab_${k}`))} <span class="hkl-seg-n">${n}</span></button>`;
  }).join('');
  const rows = loansFor(ctx.lib.loans, tab);
  const actions = `${button(escapeHTML(t('action.lend_book')), 'lend', 'primary', 'data-k="lend-book"')}${button(escapeHTML(t('action.add_borrowed')), 'borrow', 'tonal', 'data-k="add-borrowed"')}${button(escapeHTML(t('action.scan_borrowed')), 'nav', 'text', 'data-path="/scan?mode=borrowed" data-k="scan-borrowed"')}`;
  return `${navBar(ctx.route, navCounts(ctx), actions)}
  <section class="hkl-card">
    <div class="hkl-subtabs">${tabs}</div>
    <div class="hkl-list">${rows.map((l) => loanRow(ctx, l)).join('') || `<div class="hkl-empty">${escapeHTML(t(`loans.empty_${tab}`))}</div>`}</div>
  </section>`;
}

function wishRow(ctx: ViewCtx, book: Book): string {
  const w = book.wishlist!;
  const person = ctx.idx.person.get(w.person_id);
  const series = book.series?.name ? (book.series.number != null ? t('book.series_n', { name: book.series.name, n: book.series.number }) : book.series.name) : '';
  const meta = [book.authors.join(', '), series, w.bought ? t('wishlist.bought') : ''].filter(Boolean).join(' · ');
  const id = escapeHTML(book.id);
  return `<div class="hkl-listrow">
    ${cover(book, 'thumb')}
    <span class="hkl-row-main"><button class="hkl-row-title hkl-link plain" data-act="nav" data-path="/books/${escapeHTML(encodeURIComponent(book.id))}" data-k="wb-${id}">${escapeHTML(book.title)}</button><span class="hkl-row-sub">${escapeHTML(meta)}</span></span>
    <span class="hkl-who">${personDot(person)}<span>${escapeHTML(person?.name ?? '')}</span></span>
    <label class="hkl-check"><input type="checkbox" data-chg="wish-buy" data-id="${id}" data-k="buy-${id}"${w.buy ? ' checked' : ''} />${escapeHTML(t('wishlist.buy'))}</label>
    ${button(escapeHTML(t('action.got_it')), 'got-it', 'tonal', `data-id="${id}" data-k="got-${id}"`)}
    <button class="hkl-link danger" data-act="wish-remove" data-id="${id}" data-k="wr-${id}">${escapeHTML(t('action.remove'))}</button>
  </div>`;
}

/** The Wishlist view. */
export function renderWishlist(ctx: ViewCtx): string {
  const books = ctx.lib.books
    .filter((b) => b.wishlist)
    .sort((a, b) => String(b.wishlist!.added_at).localeCompare(String(a.wishlist!.added_at)));
  const lists = ctx.lib.people
    .map((p) => {
      const ent = p.wishlist_todo ? ctx.todoName(p.wishlist_todo) : '';
      return `<span class="hkl-todo">${personDot(p)}${escapeHTML(ent ? t('wishlist.list_for', { name: p.name, list: ent }) : t('wishlist.no_list_for', { name: p.name }))}</span>`;
    })
    .join('');
  const actions = button(escapeHTML(t('action.add_to_wishlist')), 'wish-add', 'primary', 'data-k="wish-add"');
  return `${navBar(ctx.route, navCounts(ctx), actions)}
  <div class="hkl-banner info"><div class="hkl-todos">${lists}<span class="hkl-muted small">${escapeHTML(t('wishlist.buy_hint'))}</span></div><span class="hkl-spacer"></span>${button(escapeHTML(t('action.change')), 'nav', 'text', 'data-path="/settings" data-k="wish-change"')}</div>
  <section class="hkl-card"><div class="hkl-list">${books.map((b) => wishRow(ctx, b)).join('') || `<div class="hkl-empty">${escapeHTML(t('wishlist.empty'))}</div>`}</div></section>
  <p class="hkl-muted small">${escapeHTML(t('wishlist.scan_hint'))}</p>`;
}

/** The Settings view: people settings, currency and export. */
export function renderSettings(ctx: ViewCtx): string {
  const todo: Array<[string, string]> = [['', t('settings.no_list')], ...ctx.ui.todoEntities.map((e): [string, string] => [e.entity_id, e.name || e.entity_id])];
  const rows = ctx.lib.people
    .map((p) => {
      const id = escapeHTML(p.id);
      const known = todo.some(([v]) => v === (p.wishlist_todo ?? ''));
      const items = known || !p.wishlist_todo ? todo : [...todo, [p.wishlist_todo, p.wishlist_todo] as [string, string]];
      return `<tr>
        <th scope="row"><span class="hkl-who">${personDot(p)}<span>${escapeHTML(p.name)}</span></span></th>
        <td><label class="hkl-check"><input type="checkbox" data-chg="person" data-key="share_reading" data-id="${id}" data-k="ps-${id}"${p.share_reading ? ' checked' : ''} /><span class="hkl-sr">${escapeHTML(t('settings.share_reading'))}</span></label></td>
        <td><input class="hkl-input narrow" type="number" min="0" data-chg="person" data-key="yearly_goal" data-id="${id}" data-k="pg-${id}" value="${escapeHTML(p.yearly_goal ?? '')}" aria-label="${escapeHTML(t('settings.yearly_goal'))}" /></td>
        <td><select class="hkl-input" data-chg="person" data-key="wishlist_todo" data-id="${id}" data-k="pt-${id}" aria-label="${escapeHTML(t('settings.wishlist_list'))}">${options(items, p.wishlist_todo ?? '')}</select></td>
      </tr>`;
    })
    .join('');
  const persons: Array<[string, string]> = [['', t('settings.export_all')], ...ctx.lib.people.map((p): [string, string] => [p.id, p.name])];
  return `${navBar(ctx.route, navCounts(ctx))}
  <section class="hkl-card">
    <h2>${escapeHTML(t('settings.people'))}</h2>
    <p class="hkl-muted small">${escapeHTML(t('settings.people_hint'))}</p>
    <div class="hkl-tablewrap"><table class="hkl-table">
      <thead><tr><th>${escapeHTML(t('common.person'))}</th><th>${escapeHTML(t('settings.share_reading'))}</th><th>${escapeHTML(t('settings.yearly_goal'))}</th><th>${escapeHTML(t('settings.wishlist_list'))}</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="4" class="hkl-muted">${escapeHTML(t('settings.no_people'))}</td></tr>`}</tbody>
    </table></div>
  </section>
  <section class="hkl-card">
    <h2>${escapeHTML(t('settings.currency'))}</h2>
    <span class="hkl-kv"><span>${escapeHTML(t('settings.currency'))}</span><span>${escapeHTML(ctx.lib.currency)}</span></span>
    <p class="hkl-muted small">${escapeHTML(t('settings.currency_hint'))}</p>
  </section>
  <section class="hkl-card">
    <h2>${escapeHTML(t('settings.export'))}</h2>
    <div class="hkl-fields">
      <label class="hkl-field">${escapeHTML(t('copy.format'))}<select data-chg="export-format" data-k="ex-format">${options([['goodreads', t('import.source_goodreads')], ['library', t('import.source_library')]], ctx.ui.exportFormat)}</select></label>
      <label class="hkl-field">${escapeHTML(t('common.person'))}<select data-chg="export-person" data-k="ex-person">${options(persons, ctx.ui.exportPerson)}</select></label>
    </div>
    ${button(escapeHTML(t('action.export')), 'export', 'tonal', 'data-k="export"')}
  </section>`;
}
