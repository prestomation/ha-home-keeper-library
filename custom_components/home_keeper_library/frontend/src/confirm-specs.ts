// The words of each confirm dialog. Each function names the item, says what goes with
// it with the real counts, and gives the button the name of the action. The functions
// are pure: they read the library and return text for `mountConfirm`.

import type { ConfirmContent } from './confirm-dialog';
import { t, tn } from './i18n';
import type { ImportState } from './tab-types';
import type { Book, Bookcase, Copy, Lib, Loan, Room, Shelf } from './types';
import type { Index } from './utils';

/** The text of a delete: the lines, then the line that says that nothing undoes it. */
const lines = (...parts: string[]): string => [...parts, t('confirm.cannot_undo')].join('\n');


export function deleteBook(lib: Lib, idx: Index, book: Book): ConfirmContent {
  const copies = idx.copiesByBook.get(book.id)?.length ?? 0;
  const loans = lib.loans.filter((l) => l.book_id === book.id).length;
  const readings = Object.keys(book.reading).length;
  return {
    title: t('confirm.delete_item', { name: book.title }),
    body: lines(t('confirm.goes_with'), t('confirm.n_copies', { n: copies }), t('confirm.n_loans', { n: loans }), t('confirm.n_readings', { n: readings })),
    confirmLabel: t('dialog.delete_book'),
  };
}

export function deleteCopy(idx: Index, copy: Copy): ConfirmContent {
  const title = idx.book.get(copy.book_id)?.title ?? '';
  return {
    title: t('dialog.delete_copy'),
    body: lines(t('confirm.copy', { format: t(`format.kind_${copy.format}`).toLowerCase(), title })),
    confirmLabel: t('action.delete_copy'),
  };
}

export function deleteLoan(idx: Index, loan: Loan): ConfirmContent {
  const title = idx.book.get(loan.book_id)?.title ?? '';
  return {
    title: t('dialog.delete_loan'),
    body: lines(t('confirm.loan', { title, party: loan.party ?? '' })),
    confirmLabel: t('dialog.delete_loan'),
  };
}

/** The copies on the shelves of *shelfIds*. They keep their book and lose their shelf. */
function copiesOn(idx: Index, shelfIds: string[]): number {
  return shelfIds.reduce((sum, id) => sum + (idx.copiesByShelf.get(id)?.length ?? 0), 0);
}

export function deleteRoom(lib: Lib, idx: Index, room: Room): ConfirmContent {
  const cases = lib.bookcases.filter((c) => c.room_id === room.id).map((c) => c.id);
  const shelves = lib.shelves.filter((s) => cases.includes(s.bookcase_id)).map((s) => s.id);
  return {
    title: t('confirm.delete_item', { name: room.name }),
    body: lines(t('confirm.goes_with'), t('confirm.n_bookcases', { n: cases.length }), t('confirm.n_shelves', { n: shelves.length }), '', t('confirm.n_unshelved', { n: copiesOn(idx, shelves) })),
    confirmLabel: t('dialog.delete_room'),
  };
}

export function deleteBookcase(lib: Lib, idx: Index, bookcase: Bookcase): ConfirmContent {
  const shelves = lib.shelves.filter((s) => s.bookcase_id === bookcase.id).map((s) => s.id);
  return {
    title: t('confirm.delete_item', { name: bookcase.name }),
    body: lines(t('confirm.goes_with'), t('confirm.n_shelves', { n: shelves.length }), '', t('confirm.n_unshelved', { n: copiesOn(idx, shelves) })),
    confirmLabel: t('dialog.delete_bookcase'),
  };
}

export function deleteShelf(idx: Index, shelf: Shelf): ConfirmContent {
  return {
    title: t('confirm.delete_item', { name: shelf.name }),
    body: lines(t('confirm.n_unshelved', { n: copiesOn(idx, [shelf.id]) })),
    confirmLabel: t('dialog.delete_shelf'),
  };
}

export function replaceCover(book: Book): ConfirmContent {
  return {
    title: t('confirm.cover_title'),
    body: lines(t('confirm.cover', { title: book.title })),
    confirmLabel: t('action.use_ol_cover'),
  };
}

export function removeWish(book: Book): ConfirmContent {
  return {
    title: t('confirm.wish_button'),
    body: lines(t('confirm.wish', { title: book.title })),
    confirmLabel: t('confirm.wish_button'),
  };
}

export function disconnectCatalog(): ConfirmContent {
  return { title: t('ol.disconnect_title'), body: t('ol.disconnect_text'), confirmLabel: t('ol.disconnect') };
}

export function removeScan(isbn: string): ConfirmContent {
  return { title: t('confirm.scan_title'), body: lines(t('confirm.scan_body', { isbn })), confirmLabel: t('scan.miss_remove') };
}

export function importRows(state: ImportState, personName: string): ConfirmContent {
  const counts = state.summary?.counts ?? {};
  const total = counts.rows ?? state.rowCount;
  const parts = (['existing', 'new', 'title_match'] as const).map((k) => t(`import.match_${k}`, { n: counts[k] ?? 0 }));
  if (state.replaceReading) parts.push('', t('confirm.import_replace', { name: personName }));
  return { title: tn('import.import_rows', total), body: lines(...parts), confirmLabel: tn('import.import_rows', total) };
}

