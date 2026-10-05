// The Scan flow views: setup (room, shelf, method), camera and summary.

import { t, tn } from './i18n';
import { button, cover, ICONS, personOptions } from './markup';
import type { ScanEntry, ViewCtx } from './tab-types';
import { buildPath, escapeHTML, locationLabel, nextShelf, scanTally, shelfPath } from './utils';

/** True when the scan adds borrowed books (`;mode=borrowed`). */
export function isBorrowedMode(ctx: ViewCtx): boolean {
  return ctx.route.query.mode === 'borrowed';
}

/** The shelf of the scan route, or null for "No shelf". */
export function routeShelf(ctx: ViewCtx): string | null {
  const id = ctx.route.query.shelf;
  return id && ctx.idx.shelf.has(id) ? id : null;
}

function head(title: string, backAct: string): string {
  return `<header class="hkl-scan-head"><button class="hkl-iconbtn" data-act="${backAct}" data-k="scan-back" aria-label="${escapeHTML(t('action.back'))}">${ICONS.back}</button><span>${escapeHTML(title)}</span></header>`;
}

function methodStep(ctx: ViewCtx): string {
  const m = ctx.ui.scan.method;
  const radio = (value: 'camera' | 'manual', title: string, hint: string) =>
    `<label class="hkl-radio${m === value ? ' on' : ''}"><input type="radio" name="method" value="${value}" data-chg="scan-method" data-k="m-${value}"${m === value ? ' checked' : ''} /><span><b>${escapeHTML(title)}</b><span class="hkl-muted">${escapeHTML(hint)}</span></span></label>`;
  return `<div class="hkl-step"><span class="hkl-eyebrow">${escapeHTML(t('scan.method'))}</span>
    ${radio('camera', t('scan.method_camera'), t('scan.method_camera_hint'))}
    ${radio('manual', t('scan.method_manual'), t('scan.method_manual_hint'))}
  </div>`;
}

function setupShelf(ctx: ViewCtx): string {
  const shelfId = routeShelf(ctx);
  const roomId = ctx.ui.scan.roomId ?? shelfPath(ctx.idx, shelfId).room?.id ?? ctx.lib.rooms[0]?.id ?? null;
  const rooms = ctx.lib.rooms
    .map((r) => `<button class="hkl-choice${r.id === roomId ? ' on' : ''}" data-act="scan-room" data-id="${escapeHTML(r.id)}" data-k="sr-${escapeHTML(r.id)}" aria-pressed="${r.id === roomId}">${escapeHTML(r.name)}</button>`)
    .join('');
  const cases = ctx.lib.bookcases
    .filter((c) => c.room_id === roomId)
    .map((c) => {
      const shelves = ctx.lib.shelves
        .filter((s) => s.bookcase_id === c.id)
        .map((s) => `<button class="hkl-choice${s.id === shelfId ? ' on' : ''}" data-act="nav" data-replace="1" data-path="${escapeHTML(buildPath({ view: 'scan', query: { shelf: s.id } }))}" data-k="sh-${escapeHTML(s.id)}" aria-pressed="${s.id === shelfId}">${escapeHTML(s.name)}</button>`)
        .join('');
      return `<span class="hkl-sub">${escapeHTML(c.name)}</span><div class="hkl-choices">${shelves || `<span class="hkl-muted small">${escapeHTML(t('shelves.no_shelves'))}</span>`}</div>`;
    })
    .join('');
  const none = `<div class="hkl-choices"><button class="hkl-choice${!shelfId ? ' on' : ''}" data-act="nav" data-replace="1" data-path="/scan" data-k="sh-none" aria-pressed="${!shelfId}">${escapeHTML(t('common.no_shelf'))}</button></div>`;
  const target = shelfId ? (ctx.idx.shelf.get(shelfId)?.name ?? '') : t('common.no_shelf');
  return `<div class="hkl-scan">
    ${head(t('scan.title'), 'scan-exit')}
    <div class="hkl-scan-body">
      ${rooms ? `<div class="hkl-step"><span class="hkl-eyebrow">${escapeHTML(t('scan.room'))}</span><div class="hkl-choices">${rooms}</div></div>` : ''}
      <div class="hkl-step"><span class="hkl-eyebrow">${escapeHTML(t('scan.shelf'))}</span>${cases}${none}</div>
      ${methodStep(ctx)}
    </div>
    <div class="hkl-scan-foot">${button(escapeHTML(t('scan.start_into', { shelf: target })), 'scan-start', 'primary', 'data-k="scan-start"')}</div>
  </div>`;
}

function setupBorrowed(ctx: ViewCtx): string {
  const s = ctx.ui.scan;
  return `<div class="hkl-scan">
    ${head(t('scan.title_borrowed'), 'scan-exit')}
    <div class="hkl-scan-body">
      <div class="hkl-step">
        <label class="hkl-field">${escapeHTML(t('loan.lender'))}<input data-chg="scan-field" data-key="party" data-k="sb-party" value="${escapeHTML(s.party)}" /></label>
        <label class="hkl-field">${escapeHTML(t('common.person'))}<select data-chg="scan-field" data-key="personId" data-k="sb-person">${personOptions(ctx.lib, s.personId ?? ctx.me)}</select></label>
        <label class="hkl-field">${escapeHTML(t('loan.due'))}<input type="date" data-chg="scan-field" data-key="due" data-k="sb-due" value="${escapeHTML(s.due)}" /></label>
        <label class="hkl-check"><input type="checkbox" data-chg="scan-field" data-key="addTask" data-k="sb-task"${s.addTask ? ' checked' : ''} />${escapeHTML(t('loan.add_task'))}</label>
      </div>
      ${methodStep(ctx)}
    </div>
    <div class="hkl-scan-foot">${button(escapeHTML(t('scan.start')), 'scan-start', 'primary', 'data-k="scan-start"')}</div>
  </div>`;
}

function resultRow(ctx: ViewCtx, e: ScanEntry): string {
  const book = e.res?.book ?? null;
  const thumb = book ? cover(book, 'thumb') : '<span class="hkl-cover hkl-cover-thumb blank" aria-hidden="true"></span>';
  const title = book?.title ?? e.title ?? e.isbn;
  const by = book ? [book.authors.join(', '), book.published].filter(Boolean).join(' · ') : '';
  const k = `data-key="${e.key}"`;
  let sub = escapeHTML(by);
  let right = '';
  let cls = '';
  if (e.pending) {
    sub = escapeHTML(t('scan.looking_up'));
  } else if (e.error) {
    sub = escapeHTML(e.error);
    cls = 'late';
  } else if (e.res?.result === 'duplicate' && !e.choice) {
    const where = e.res.existing_copies
      .map((c) => (c.shelf_id ? locationLabel(ctx.idx, c.shelf_id) : t('common.no_shelf')))
      .join(', ');
    sub = escapeHTML(t('scan.already_in', { place: where }));
    right = `<div class="hkl-dup">${button(escapeHTML(t('scan.move_here')), 'scan-dup', 'tonal', `${k} data-value="move" data-k="dup-m-${e.key}"`)}${button(escapeHTML(t('scan.add_copy')), 'scan-dup', 'tonal', `${k} data-value="add_copy" data-k="dup-a-${e.key}"`)}${button(escapeHTML(t('scan.skip')), 'scan-dup', 'text', `${k} data-value="skip" data-k="dup-s-${e.key}"`)}</div>`;
    cls = 'dup';
  } else if (e.res?.result === 'not_found') {
    sub = escapeHTML(t('scan.no_match'));
    right = book ? button(escapeHTML(t('action.add_details')), 'scan-details', 'tonal', `data-id="${escapeHTML(book.id)}" data-k="det-${e.key}"`) : '';
    cls = 'warn';
  } else {
    const label = e.res?.result ? t(`scan.result_${e.res.result}`) : t('scan.result_added');
    const wish = e.res?.from_wishlist === true ? `<span class="hkl-pill st-want" data-k="from-wish-${e.key}">${escapeHTML(t('scan.from_wishlist'))}</span>` : '';
    right = `<span class="hkl-pills">${wish}<span class="hkl-pill ok">${escapeHTML(label)}</span></span>`;
  }
  return `<div class="hkl-result ${cls}">${thumb}<span class="hkl-row-main"><b>${escapeHTML(title)}</b><span class="hkl-row-sub">${sub}</span></span>${right}</div>`;
}

function cameraStep(ctx: ViewCtx): string {
  const s = ctx.ui.scan;
  const camera = s.method === 'camera' && !s.cameraError;
  const msg = s.method === 'camera' && s.cameraError
    ? `<div class="hkl-cam-msg" role="alert">${escapeHTML(t(`scan.camera_${s.cameraError}`))}</div>`
    : '';
  const cam = camera
    ? `<div class="hkl-cam"><div class="hkl-cam-video" data-slot="video"></div><div class="hkl-frame" aria-hidden="true"></div>${s.torch !== null ? `<button class="hkl-iconbtn torch${s.torch ? ' on' : ''}" data-act="scan-torch" data-k="torch" aria-pressed="${s.torch}" aria-label="${escapeHTML(t('scan.torch'))}">${ICONS.torch}</button>` : ''}<span class="hkl-cam-hint">${escapeHTML(t('scan.frame_hint'))}</span></div>`
    : '';
  const added = s.results.filter((r) => r.res?.result === 'added' || r.res?.result === 'moved' || (isBorrowedMode(ctx) && r.res)).length;
  const manual = s.manualOpen || !camera
    ? `<form class="hkl-isbn" data-form="isbn"><input name="isbn" inputmode="numeric" autocomplete="off" data-k="isbn-input" aria-label="${escapeHTML(t('scan.isbn'))}" placeholder="${escapeHTML(t('scan.isbn_placeholder'))}" /><button class="hkl-btn primary" type="submit" data-k="isbn-add">${escapeHTML(t('action.add'))}</button></form>`
    : '';
  const shelfId = routeShelf(ctx);
  const next = !isBorrowedMode(ctx) && shelfId ? nextShelf(ctx.lib, shelfId) : null;
  const where = isBorrowedMode(ctx) ? t('scan.title_borrowed') : shelfId ? locationLabel(ctx.idx, shelfId) : t('common.no_shelf');
  const counter = isBorrowedMode(ctx) ? tn('scan.borrowed_count', added) : t('scan.added_count', { n: added });
  return `<div class="hkl-scan cam">
    ${head(where, 'scan-setup')}
    ${cam}${msg}
    <div class="hkl-tray">
      <div class="hkl-tray-head"><span>${escapeHTML(counter)}</span>${camera ? button(escapeHTML(t('scan.enter_isbn')), 'scan-manual', 'outline', 'data-k="scan-manual"') : ''}</div>
      ${manual}
      <div class="hkl-results" aria-live="polite">${[...s.results].reverse().map((r) => resultRow(ctx, r)).join('')}</div>
      <div class="hkl-tray-foot">${next ? button(escapeHTML(t('scan.next_shelf', { shelf: next.name })), 'scan-next', 'outline', `data-id="${escapeHTML(next.id)}" data-k="scan-next"`) : ''}${button(escapeHTML(t('action.done')), 'scan-done', 'primary', 'data-k="scan-done"')}</div>
    </div>
  </div>`;
}

function summaryStep(ctx: ViewCtx): string {
  const s = ctx.ui.scan;
  const tally = scanTally(s.results.filter((r) => r.res).map((r) => ({ result: r.res!.result, book: r.res!.book })));
  const shelfId = routeShelf(ctx);
  const where = isBorrowedMode(ctx) ? t('scan.title_borrowed') : shelfId ? locationLabel(ctx.idx, shelfId) : t('common.no_shelf');
  const tiles = [
    ['added', tally.added],
    ['moved', tally.moved],
    ['needs', tally.needs],
  ]
    .map(([k, n]) => `<div class="hkl-stat"><b>${n}</b><span>${escapeHTML(t(`scan.sum_${k}`))}</span></div>`)
    .join('');
  const rows = s.results
    .filter((r) => r.res)
    .map((r) => {
      const book = r.res!.book;
      const res = r.res!.result;
      let label = t(`scan.result_${res}`);
      if (res === 'moved' && r.res!.existing_copies[0]?.shelf_id) {
        const from = shelfPath(ctx.idx, r.res!.existing_copies[0].shelf_id).room?.name;
        if (from) label = t('scan.moved_from', { place: from });
      }
      if (res === 'not_found') label = t('action.add_details');
      return `<div class="hkl-result">${book ? cover(book, 'thumb') : '<span class="hkl-cover hkl-cover-thumb blank"></span>'}<span class="hkl-row-main"><b>${escapeHTML(book?.title ?? r.isbn)}</b><span class="hkl-row-sub">${escapeHTML(book && res !== 'not_found' ? book.authors.join(', ') : t('scan.no_match'))}</span></span><span class="hkl-pill ${res === 'not_found' ? 'warn' : 'ok'}">${escapeHTML(label)}</span></div>`;
    })
    .join('');
  const next = !isBorrowedMode(ctx) && shelfId ? nextShelf(ctx.lib, shelfId) : null;
  const markRead = !isBorrowedMode(ctx) && ctx.me
    ? `<label class="hkl-check big"><input type="checkbox" data-chg="scan-markread" data-k="markread"${s.markRead ? ' checked' : ''} />${escapeHTML(t('scan.mark_read'))}</label>`
    : '';
  return `<div class="hkl-scan">
    ${head(t('scan.summary'), 'scan-setup')}
    <div class="hkl-scan-body">
      <div class="hkl-stats">${tiles}</div>
      <span class="hkl-eyebrow">${escapeHTML(where)}</span>
      <div class="hkl-results">${rows || `<div class="hkl-empty">${escapeHTML(t('scan.nothing'))}</div>`}</div>
      ${markRead}
    </div>
    <div class="hkl-scan-foot">${button(escapeHTML(t('action.done')), 'scan-finish', 'outline', 'data-k="scan-finish"')}${next ? button(escapeHTML(t('scan.scan_shelf', { shelf: next.name })), 'scan-next', 'primary', `data-id="${escapeHTML(next.id)}" data-k="scan-next"`) : ''}</div>
  </div>`;
}

/** The Scan flow. The step is in the `step` query value. */
export function renderScan(ctx: ViewCtx): string {
  const step = ctx.route.query.step;
  if (step === 'camera') return cameraStep(ctx);
  if (step === 'summary') return summaryStep(ctx);
  return isBorrowedMode(ctx) ? setupBorrowed(ctx) : setupShelf(ctx);
}
