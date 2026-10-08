// The Import dialog: source, person, shelf, file, dry run preview, import.

import { formatNumber, t, tn } from './i18n';
import { button, ICONS, options, personOptions, shelfOptions } from './markup';
import type { ViewCtx } from './tab-types';
import type { ImportRow } from './types';
import { escapeHTML } from './utils';

/** The preview rows: the count keys of `import_csv` and their labels. */
export const PREVIEW_KEYS = ['read', 'reading', 'want', 'dnf', 'wishlist', 'copies', 'tags', 'errors'] as const;

/** The match counts that show as pills. */
export const MATCH_KEYS = ['existing', 'new', 'title_match'] as const;

/** The number of result rows that the preview shows. */
export const PREVIEW_ROWS = 200;

/** The text of the result of 1 row: the error, or the match. */
function rowResult(row: ImportRow): string {
  return row.message || t(`import.action_${row.action}`);
}

/** The Import dialog markup. */
export function renderImport(ctx: ViewCtx): string {
  const s = ctx.ui.import;
  const person = s.personId ?? ctx.me;
  const personName = ctx.idx.person.get(person ?? '')?.name ?? '';
  const sources: Array<[string, string]> = [
    ['goodreads', t('import.source_goodreads')],
    ['storygraph', t('import.source_storygraph')],
    ['library', t('import.source_library')],
  ];
  const counts = s.summary?.counts ?? {};
  const preview = s.summary
    ? `<span class="hkl-eyebrow">${escapeHTML(s.done ? t('import.result') : t('import.preview'))}</span>
      <div class="hkl-tablewrap"><table class="hkl-table">
        <thead><tr><th>${escapeHTML(t('import.col_result', { name: personName }))}</th><th class="num">${escapeHTML(t('import.col_rows'))}</th></tr></thead>
        <tbody>${PREVIEW_KEYS.filter((k) => counts[k]).map((k) => `<tr><td>${escapeHTML(t(`import.row_${k}`))}</td><td class="num">${formatNumber(counts[k])}</td></tr>`).join('') || `<tr><td colspan="2" class="hkl-muted">${escapeHTML(t('import.no_changes'))}</td></tr>`}</tbody>
      </table></div>
      <div class="hkl-chips">${MATCH_KEYS.map((k) => `<span class="hkl-chip">${escapeHTML(t(`import.match_${k}`, { n: formatNumber(counts[k] ?? 0) }))}</span>`).join('')}</div>
      ${s.summary.rows.length ? `<details class="hkl-details"><summary>${escapeHTML(tn('import.rows_shown', Math.min(PREVIEW_ROWS, s.summary.rows.length)))}</summary><div class="hkl-tablewrap"><table class="hkl-table small"><tbody>${s.summary.rows.slice(0, PREVIEW_ROWS).map((r) => `<tr class="${r.action === 'error' ? 'err' : ''}"><td>${escapeHTML(r.line)}</td><td>${escapeHTML(r.title || r.isbn || '')}</td><td>${escapeHTML(r.authors.join(', '))}</td><td>${escapeHTML(rowResult(r))}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
      ${s.summary.truncated ? `<p class="hkl-muted small" data-k="import-truncated">${escapeHTML(t('import.truncated'))}</p>` : ''}`
    : '';
  const file = s.fileName
    ? `<div class="hkl-file"><span>${escapeHTML(s.fileName)} · ${escapeHTML(tn('import.rows', s.rowCount))}</span>${button(escapeHTML(t('import.change_file')), 'import-pick', 'text', 'data-k="import-change"')}</div>`
    : `<div class="hkl-file empty"><span class="hkl-muted">${escapeHTML(t('import.file_hint'))}</span>${button(escapeHTML(t('import.choose_file')), 'import-pick', 'tonal', 'data-k="import-pick"')}</div>`;
  const total = counts.rows ?? s.rowCount;
  const go = s.done
    ? button(escapeHTML(t('action.close')), 'import-close', 'primary', 'data-k="import-done"')
    : `<button class="hkl-btn primary" data-act="import-run" data-k="import-run"${!s.summary || s.busy ? ' disabled' : ''}>${escapeHTML(tn('import.import_rows', total))}</button>`;
  return `<div class="hkl-scrim" data-act="import-close-scrim">
    <section class="hkl-dialog wide" role="dialog" aria-modal="true" aria-labelledby="hkl-import-title">
      <div class="hkl-dlg-head"><h2 id="hkl-import-title">${escapeHTML(t('import.title'))}</h2><button class="hkl-iconbtn" data-act="import-close" data-k="import-x" aria-label="${escapeHTML(t('action.close'))}">${ICONS.close}</button></div>
      <div class="hkl-fields">
        <label class="hkl-field">${escapeHTML(t('import.source'))}<select data-chg="import" data-key="source" data-k="im-source">${options(sources, s.source)}</select></label>
        <label class="hkl-field">${escapeHTML(t('common.person'))}<select data-chg="import" data-key="personId" data-k="im-person">${personOptions(ctx.lib, person)}</select></label>
        <label class="hkl-field">${escapeHTML(t('import.shelf'))}<select data-chg="import" data-key="shelfId" data-k="im-shelf">${shelfOptions(ctx.lib, s.shelfId)}</select></label>
      </div>
      ${file}
      <input type="file" accept=".csv,text/csv" data-chg="import-file" data-k="im-file" hidden />
      ${s.busy ? `<div class="hkl-muted">${escapeHTML(t('import.working'))}</div>` : ''}
      ${s.error ? `<div class="hkl-error" role="alert">${escapeHTML(s.error)}</div>` : ''}
      ${preview}
      <label class="hkl-check"><input type="checkbox" data-chg="import" data-key="importNotes" data-k="im-notes"${s.importNotes ? ' checked' : ''} />${escapeHTML(t('import.notes'))}</label>
      <label class="hkl-check"><input type="checkbox" data-chg="import" data-key="replaceReading" data-k="im-replace"${s.replaceReading ? ' checked' : ''} />${escapeHTML(t('import.replace', { name: personName }))}</label>
      <div class="hkl-dlg-actions">${button(escapeHTML(t('action.cancel')), 'import-close', 'text', 'data-k="import-cancel"')}${go}</div>
    </section>
  </div>`;
}
