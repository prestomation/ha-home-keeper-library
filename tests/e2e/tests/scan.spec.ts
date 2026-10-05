import { library } from '../ha-ws';
import { adminState, bookByTitle, expect, openTab, test } from './helpers';

/**
 * The Scan flow with Enter ISBN, against the Open Library fixture server
 * (tests/e2e/seed/openlibrary). The new book is deleted after the test.
 */
const NEW_ISBN = '9780553418606';
const NEW_TITLE = 'The Library at Mount Char';
const SEEDED_ISBN = '9780441478125';

async function shelfId(room: string, bookcase: string, shelf: string): Promise<string> {
  const state = await adminState();
  const r = state.rooms.find((x: { name: string }) => x.name === room);
  const c = state.bookcases.find((x: { name: string; room_id: string }) => x.name === bookcase && x.room_id === r.id);
  return state.shelves.find((x: { name: string; bookcase_id: string }) => x.name === shelf && x.bookcase_id === c.id).id;
}

async function deleteNewBook(): Promise<void> {
  const state = await adminState();
  for (const book of state.books.filter((b: { isbn13: string }) => b.isbn13 === NEW_ISBN)) {
    await library('delete_book', { book_id: book.id });
  }
}

test.describe('Scan', { tag: '@responsive' }, () => {
  test.beforeEach(deleteNewBook);
  test.afterEach(deleteNewBook);

  test('Enter ISBN adds a book from Open Library to the shelf', async ({ page }) => {
    const shelf = await shelfId('Office', 'Tall bookcase', 'Shelf 3');
    const tab = await openTab(page, `/scan;shelf=${shelf}`);
    await tab.locator('[data-k="m-manual"]').check();
    await expect(tab.locator('[data-k="m-manual"]')).toBeChecked();
    await tab.locator('[data-k="scan-start"]').click();
    await expect(page).toHaveURL(/step=camera/);
    await tab.locator('[data-k="isbn-input"]').fill('978-0-553-41860-6');
    await tab.locator('[data-k="isbn-add"]').click();
    const row = tab.locator('.hkl-result').filter({ hasText: NEW_TITLE });
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.locator('.hkl-pill.ok')).toHaveText('Added');
    await expect(row).toContainText('Scott Hawkins');
    await expect(tab.locator('.hkl-tray-head')).toContainText('Added to this shelf: 1');

    const state = await adminState();
    const book = state.books.find((b: { isbn13: string }) => b.isbn13 === NEW_ISBN);
    expect(book).toMatchObject({ title: NEW_TITLE, authors: ['Scott Hawkins'], needs_details: false, owned: true });
    expect(state.copies.filter((c: { book_id: string }) => c.book_id === book.id).map((c: { shelf_id: string }) => c.shelf_id)).toEqual([shelf]);

    await tab.locator('[data-k="scan-done"]').click();
    await expect(tab.locator('.hkl-scan-head')).toContainText('Scan summary');
    await expect(tab.locator('.hkl-stat b').first()).toHaveText('1');
  });

  test('a duplicate shows its actions and Skip changes nothing', async ({ page }) => {
    const seeded = await bookByTitle('The Left Hand of Darkness');
    expect(seeded.isbn13).toBe(SEEDED_ISBN);
    const before = (await adminState()).copies.filter((c: { book_id: string }) => c.book_id === seeded.id);
    const shelf = await shelfId('Office', 'Tall bookcase', 'Shelf 3');
    const tab = await openTab(page, `/scan;shelf=${shelf};step=camera`);
    await tab.locator('[data-k="m-manual"]').check().catch(() => undefined);
    const input = tab.locator('[data-k="isbn-input"]');
    if (!(await input.isVisible())) await tab.locator('[data-k="scan-manual"]').click();
    await input.fill(SEEDED_ISBN);
    await tab.locator('[data-k="isbn-add"]').click();
    const row = tab.locator('.hkl-result.dup');
    await expect(row).toContainText('Already in Office › Tall bookcase › Shelf 1, Living room › Bookcase A › Shelf 2');
    await expect(row.getByRole('button', { name: 'Move here' })).toBeVisible();
    await expect(row.getByRole('button', { name: 'Add 2nd copy' })).toBeVisible();
    await row.getByRole('button', { name: 'Skip' }).click();
    await expect(tab.locator('.hkl-result').filter({ hasText: seeded.title }).locator('.hkl-pill')).toHaveText('Skipped');
    const after = (await adminState()).copies.filter((c: { book_id: string }) => c.book_id === seeded.id);
    expect(after).toEqual(before);
  });
});
