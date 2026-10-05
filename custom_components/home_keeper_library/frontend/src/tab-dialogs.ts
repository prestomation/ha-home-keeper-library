// The dialogs of the tab. Each dialog is a form; `tab.ts` reads the form data on
// submit and calls the websocket command. The dialog layer is separate from the
// view, so a data push does not clear what the user types.

import { t } from './i18n';
import { formatOptions, ICONS, options, personOptions, shelfOptions } from './markup';
import type { ViewCtx } from './tab-types';
import type { Copy } from './types';
import { escapeHTML, locationLabel } from './utils';

export type Dialog =
  | { kind: 'add-book' }
  | { kind: 'edit-book'; bookId: string }
  | { kind: 'copy'; bookId: string; copyId: string | null }
  | { kind: 'move'; copyId: string }
  | { kind: 'set-shelf' }
  | { kind: 'lend'; bookId: string | null }
  | { kind: 'borrow' }
  | { kind: 'wish-add'; bookId: string | null }
  | { kind: 'got-it'; bookId: string }
  | { kind: 'room'; roomId: string | null }
  | { kind: 'bookcase'; roomId: string; bookcaseId: string | null }
  | { kind: 'shelf'; bookcaseId: string; shelfId: string | null }
  | {
      kind: 'confirm';
      title: string;
      text: string;
      label: string;
      command: string;
      fields: Record<string, unknown>;
      after?: string;
    };

export interface DialogState {
  dialog: Dialog;
  error: string;
  busy: boolean;
}

const field = (label: string, input: string, cls = '') =>
  `<label class="hkl-field${cls ? ` ${cls}` : ''}">${escapeHTML(label)}${input}</label>`;

const text = (name: string, value: unknown = '', attrs = '') =>
  `<input name="${name}" value="${escapeHTML(value ?? '')}" data-k="d-${name}" ${attrs} />`;

const check = (name: string, label: string, on: boolean, hint = '') =>
  `<label class="hkl-check"><input type="checkbox" name="${name}" data-k="d-${name}"${on ? ' checked' : ''} /><span>${escapeHTML(label)}${hint ? `<span class="hkl-muted small block">${escapeHTML(hint)}</span>` : ''}</span></label>`;

function copyFields(ctx: ViewCtx, copy: Copy | null): string {
  const conditions: Array<[string, string]> = [['', t('common.none')], ...['new', 'fine', 'good', 'fair', 'poor'].map((c): [string, string] => [c, t(`condition.${c}`)])];
  return `<div class="hkl-fields">
    ${field(t('copy.shelf'), `<select name="shelf_id" data-k="d-shelf">${shelfOptions(ctx.lib, ctx.idx, copy?.shelf_id ?? null)}</select>`)}
    ${field(t('copy.format'), `<select name="format" data-k="d-format">${formatOptions(copy?.format ?? 'paperback')}</select>`)}
    ${field(t('copy.condition'), `<select name="condition" data-k="d-condition">${options(conditions, copy?.condition ?? '')}</select>`)}
    ${field(t('copy.acquired'), text('acquired', copy?.acquired, 'type="date"'))}
    ${field(t('copy.acquired_from'), text('acquired_from', copy?.acquired_from))}
    ${field(t('copy.price'), text('price', copy?.price, 'inputmode="decimal"'), 'small')}
    ${field(t('copy.value'), text('value', copy?.value, 'inputmode="decimal"'), 'small')}
  </div>
  ${check('signed', t('copy.signed'), Boolean(copy?.signed))}
  ${check('first_edition', t('copy.first_edition'), Boolean(copy?.first_edition))}
  ${field(t('copy.note'), text('note', copy?.note), 'wide')}`;
}

function body(ctx: ViewCtx, d: Dialog, areas: Array<[string, string]>): { title: string; html: string; submit: string; danger?: boolean } {
  switch (d.kind) {
    case 'add-book':
      return {
        title: t('dialog.add_book'),
        submit: t('action.add'),
        html: `${field(t('dialog.isbn_or_title'), text('query', '', 'required autocomplete="off"'), 'wide')}
          ${field(t('book.authors'), text('authors'), 'wide')}
          ${check('lookup', t('dialog.lookup'), true)}
          ${check('own', t('dialog.own_copy'), true)}
          <div class="hkl-fields">
            ${field(t('copy.shelf'), `<select name="shelf_id" data-k="d-shelf">${shelfOptions(ctx.lib, ctx.idx, null)}</select>`)}
            ${field(t('copy.format'), `<select name="format" data-k="d-format">${formatOptions('paperback')}</select>`)}
          </div>`,
      };
    case 'edit-book': {
      const b = ctx.idx.book.get(d.bookId);
      return {
        title: t('dialog.edit_book'),
        submit: t('action.save'),
        html: `<div class="hkl-fields">
          ${field(t('book.title'), text('title', b?.title, 'required'), 'wide')}
          ${field(t('book.subtitle'), text('subtitle', b?.subtitle), 'wide')}
          ${field(t('book.authors'), text('authors', b?.authors.join(', ')), 'wide')}
          ${field('ISBN', text('isbn', b?.isbn13 ?? b?.isbn10 ?? '', 'inputmode="numeric"'))}
          ${field(t('book.publisher'), text('publisher', b?.publisher))}
          ${field(t('book.published'), text('published', b?.published), 'small')}
          ${field(t('book.pages_label'), text('pages', b?.pages, 'type="number" min="0"'), 'small')}
          ${field(t('book.language'), text('language', b?.language), 'small')}
          ${field(t('book.series'), text('series_name', b?.series?.name))}
          ${field(t('book.series_number'), text('series_number', b?.series?.number), 'small')}
          ${field(t('book.subjects'), text('subjects', b?.subjects.join(', ')), 'wide')}
          ${field(t('book.tags'), text('tags', b?.tags.join(', ')), 'wide')}
        </div>
        ${field(t('book.description'), `<textarea name="description" rows="4" data-k="d-description">${escapeHTML(b?.description ?? '')}</textarea>`, 'wide')}
        ${b?.needs_details ? check('details_done', t('dialog.details_done'), true) : ''}`,
      };
    }
    case 'copy': {
      const copy = d.copyId ? (ctx.idx.copy.get(d.copyId) ?? null) : null;
      return { title: copy ? t('dialog.edit_copy') : t('dialog.add_copy'), submit: t('action.save'), html: copyFields(ctx, copy) };
    }
    case 'move': {
      const copy = ctx.idx.copy.get(d.copyId);
      const book = copy ? ctx.idx.book.get(copy.book_id) : undefined;
      return {
        title: t('dialog.move'),
        submit: t('action.move'),
        html: `<p class="hkl-muted">${escapeHTML(book?.title ?? '')}</p>${field(t('copy.shelf'), `<select name="shelf_id" data-k="d-shelf">${shelfOptions(ctx.lib, ctx.idx, copy?.shelf_id ?? null)}</select>`, 'wide')}`,
      };
    }
    case 'set-shelf': {
      const loose = ctx.idx.copiesByShelf.get('') ?? [];
      const rows = loose
        .map((c) => `<label class="hkl-check"><input type="checkbox" name="copy" value="${escapeHTML(c.id)}" checked />${escapeHTML(ctx.idx.book.get(c.book_id)?.title ?? '')} · ${escapeHTML(t(`format.kind_${c.format}`))}</label>`)
        .join('');
      return {
        title: t('dialog.set_shelf'),
        submit: t('action.move'),
        html: `${field(t('copy.shelf'), `<select name="shelf_id" data-k="d-shelf">${shelfOptions(ctx.lib, ctx.idx, ctx.lib.shelves[0]?.id ?? null, false)}</select>`, 'wide')}<div class="hkl-checklist">${rows}</div>`,
      };
    }
    case 'lend': {
      const avail = ctx.lib.copies
        .filter((c) => !ctx.idx.loanByCopy.has(c.id) && c.format !== 'ebook' && c.format !== 'audiobook')
        .filter((c) => !d.bookId || c.book_id === d.bookId)
        .map((c): [string, string] => [c.id, `${ctx.idx.book.get(c.book_id)?.title ?? ''} · ${c.shelf_id ? locationLabel(ctx.idx, c.shelf_id) : t('common.no_shelf')}`])
        .sort((a, b) => a[1].localeCompare(b[1]));
      return {
        title: t('dialog.lend'),
        submit: t('action.lend'),
        html: `${field(t('loan.copy'), `<select name="copy_id" required data-k="d-copy">${options(avail, avail[0]?.[0] ?? '')}</select>`, 'wide')}
          <div class="hkl-fields">
            ${field(t('loan.borrower'), text('party', '', 'required'))}
            ${field(t('loan.started'), text('started', ctx.today, 'type="date"'), 'small')}
            ${field(t('loan.return_by'), text('due', '', 'type="date"'), 'small')}
          </div>
          ${check('add_task', t('loan.add_task'), true, t('loan.add_task_hint'))}
          ${field(t('copy.note'), text('note', '', `placeholder="${escapeHTML(t('common.optional'))}"`), 'wide')}`,
      };
    }
    case 'borrow':
      return {
        title: t('dialog.borrow'),
        submit: t('action.add'),
        html: `${field(t('dialog.isbn_or_title'), text('query', '', 'required autocomplete="off"'), 'wide')}
          <div class="hkl-fields">
            ${field(t('loan.lender'), text('party', '', 'required'))}
            ${field(t('common.person'), `<select name="person_id" data-k="d-person">${personOptions(ctx.lib, ctx.me)}</select>`)}
            ${field(t('copy.format'), `<select name="format" data-k="d-format">${formatOptions('paperback')}</select>`)}
            ${field(t('loan.started'), text('started', ctx.today, 'type="date"'), 'small')}
            ${field(t('loan.due'), text('due', '', 'type="date"'), 'small')}
          </div>
          ${check('add_task', t('loan.add_task'), true, t('loan.add_task_hint'))}
          ${field(t('copy.note'), text('note', '', `placeholder="${escapeHTML(t('common.optional'))}"`), 'wide')}
          <p class="hkl-muted small">${escapeHTML(t('loan.borrow_hint'))}</p>`,
      };
    case 'wish-add': {
      const b = d.bookId ? ctx.idx.book.get(d.bookId) : undefined;
      return {
        title: t('dialog.wish_add'),
        submit: t('action.add'),
        html: `${b ? `<p><b>${escapeHTML(b.title)}</b></p>` : field(t('dialog.isbn_or_title'), text('query', '', 'required autocomplete="off"'), 'wide')}
          ${field(t('common.person'), `<select name="person_id" data-k="d-person">${personOptions(ctx.lib, ctx.me)}</select>`, 'wide')}
          ${check('buy', t('wishlist.buy'), false, t('wishlist.buy_hint'))}`,
      };
    }
    case 'got-it': {
      const b = ctx.idx.book.get(d.bookId);
      return {
        title: t('dialog.got_it'),
        submit: t('action.save'),
        html: `<p><b>${escapeHTML(b?.title ?? '')}</b></p><div class="hkl-fields">
          ${field(t('copy.shelf'), `<select name="shelf_id" data-k="d-shelf">${shelfOptions(ctx.lib, ctx.idx, null)}</select>`)}
          ${field(t('copy.format'), `<select name="format" data-k="d-format">${formatOptions('paperback')}</select>`)}
        </div>`,
      };
    }
    case 'room': {
      const r = d.roomId ? ctx.idx.room.get(d.roomId) : undefined;
      return {
        title: r ? t('dialog.edit_room') : t('dialog.add_room'),
        submit: r ? t('action.save') : t('action.add'),
        html: `${field(t('dialog.name'), text('name', r?.name, 'required'), 'wide')}
          ${field(t('dialog.area'), `<select name="area_id" data-k="d-area">${options([['', t('common.none')], ...areas], r?.area_id ?? '')}</select>`, 'wide')}
          <p class="hkl-muted small">${escapeHTML(t('shelves.area_hint'))}</p>`,
      };
    }
    case 'bookcase': {
      const c = d.bookcaseId ? ctx.idx.bookcase.get(d.bookcaseId) : undefined;
      return {
        title: c ? t('dialog.edit_bookcase') : t('dialog.add_bookcase'),
        submit: c ? t('action.save') : t('action.add'),
        html: `${field(t('dialog.name'), text('name', c?.name, 'required'), 'wide')}${field(t('copy.note'), text('note', c?.note), 'wide')}
          ${c ? '' : field(t('dialog.shelf_count'), text('shelves', 4, 'type="number" min="0" max="20"'), 'small')}`,
      };
    }
    case 'shelf': {
      const s = d.shelfId ? ctx.idx.shelf.get(d.shelfId) : undefined;
      const count = ctx.lib.shelves.filter((x) => x.bookcase_id === d.bookcaseId).length;
      return {
        title: s ? t('dialog.edit_shelf') : t('dialog.add_shelf'),
        submit: s ? t('action.save') : t('action.add'),
        html: field(t('dialog.name'), text('name', s?.name ?? t('dialog.shelf_default', { n: count + 1 }), 'required'), 'wide'),
      };
    }
    case 'confirm':
      return { title: d.title, submit: d.label, html: `<p>${escapeHTML(d.text)}</p>`, danger: true };
  }
}

/** The dialog layer markup. */
export function renderDialog(ctx: ViewCtx, state: DialogState, areas: Array<[string, string]>): string {
  const { title, html, submit, danger } = body(ctx, state.dialog, areas);
  return `<div class="hkl-scrim" data-act="dialog-scrim">
    <form class="hkl-dialog" data-form="dialog" role="dialog" aria-modal="true" aria-labelledby="hkl-dlg-title" novalidate>
      <div class="hkl-dlg-head"><h2 id="hkl-dlg-title">${escapeHTML(title)}</h2><button type="button" class="hkl-iconbtn" data-act="dialog-close" data-k="d-x" aria-label="${escapeHTML(t('action.close'))}">${ICONS.close}</button></div>
      <div class="hkl-dlg-body">${html}</div>
      ${state.error ? `<div class="hkl-error" role="alert">${escapeHTML(state.error)}</div>` : ''}
      <div class="hkl-dlg-actions">
        <button type="button" class="hkl-btn text" data-act="dialog-close" data-k="d-cancel">${escapeHTML(t('action.cancel'))}</button>
        <button type="submit" class="hkl-btn ${danger ? 'danger-primary' : 'primary'}" data-k="d-submit"${state.busy ? ' disabled' : ''}>${escapeHTML(submit)}</button>
      </div>
    </form>
  </div>`;
}
