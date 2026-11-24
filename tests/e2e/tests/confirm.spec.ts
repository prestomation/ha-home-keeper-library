import { resolve } from 'node:path';
import type { Locator, Page } from '@playwright/test';
import { library } from '../ha-ws';
import { adminState, bookByTitle, expect, libraryTab, openTab, test } from './helpers';

/**
 * Every delete, remove and import of the tab asks first, in 1 dialog, and the safe answer
 * is the default. For each dialog this spec checks that Cancel holds the keyboard, and that
 * Cancel, Escape and a tap outside each leave the data alone. Then it confirms and checks
 * the data. Each test makes what it deletes and removes the rest after. It never confirms
 * a delete of a seeded record.
 */
const PREFIX = 'E2E confirm';
const CSV = resolve(__dirname, '../seed/goodreads_sample.csv');

const scrim = (page: Page) => libraryTab(page).locator('.hkl-confirm-scrim');
const cancel = (page: Page) => scrim(page).locator('[data-k="confirm-cancel"]');
const ok = (page: Page) => scrim(page).locator('[data-k="confirm-ok"]');

/** True while the control with *key* holds the keyboard, inside the shadow root of the tab. */
async function holds(page: Page, key: string): Promise<boolean> {
  return libraryTab(page).evaluate((el, k) => (el.shadowRoot?.activeElement as HTMLElement | null)?.dataset.k === k, key);
}

/** Open the dialog 3 times and close it by Cancel, Escape and a tap outside. */
async function safeByDefault(page: Page, open: () => Promise<void>, unchanged: () => Promise<void>): Promise<void> {
  await open();
  await expect(scrim(page)).toBeVisible();
  await expect(scrim(page).locator('[role="alertdialog"]')).toHaveAttribute('aria-modal', 'true');
  await expect.poll(() => holds(page, 'confirm-cancel')).toBe(true);

  await cancel(page).click();
  await expect(scrim(page)).toHaveCount(0);
  await unchanged();

  await open();
  await expect(scrim(page)).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(scrim(page)).toHaveCount(0);
  await unchanged();

  await open();
  await expect(scrim(page)).toBeVisible();
  await scrim(page).click({ position: { x: 4, y: 4 } });
  await expect(scrim(page)).toHaveCount(0);
  await unchanged();
}

async function makeBook(title: string): Promise<Record<string, any>> {
  await library('add_book', { title, lookup: false });
  return bookByTitle(title);
}

async function cleanup(): Promise<void> {
  const state = await adminState();
  for (const book of state.books.filter((b: { title: string }) => b.title.startsWith(PREFIX))) {
    for (const loan of state.loans.filter((l: { book_id: string }) => l.book_id === book.id)) {
      await library('delete_loan', { loan_id: loan.id });
    }
    await library('delete_book', { book_id: book.id });
  }
  for (const room of state.rooms.filter((r: { name: string }) => r.name.startsWith(PREFIX))) {
    await library('delete_room', { room_id: room.id, force: true });
  }
}

/** The ids that a test has not changed: the data of *get_state* for 1 list. */
async function count(list: string, match: (r: any) => boolean): Promise<number> {
  return (await adminState())[list].filter(match).length;
}

test.describe('Every delete asks first', { tag: '@responsive' }, () => {
  test.beforeEach(cleanup);
  test.afterEach(cleanup);

  test('deleting a book names it and counts what goes with it', async ({ page }) => {
    const book = await makeBook(`${PREFIX} book`);
    await library('add_copy', { book_id: book.id, format: 'paperback' });
    await library('add_copy', { book_id: book.id, format: 'hardcover' });
    const tab = await openTab(page, `/books/${book.id}`);
    const exists = async () => expect(await count('books', (b) => b.id === book.id)).toBe(1);

    await safeByDefault(page, () => tab.locator('[data-k="delete-book"]').click(), exists);
    await tab.locator('[data-k="delete-book"]').click();
    await expect(scrim(page).locator('h2')).toHaveText(`Delete "${PREFIX} book"?`);
    await expect(scrim(page).locator('p')).toContainText('These go with it:');
    await expect(scrim(page).locator('p')).toContainText('Copies: 2');
    await expect(scrim(page).locator('p')).toContainText('You cannot undo this.');
    await expect(ok(page)).toHaveText('Delete book');
    await ok(page).click();
    await expect(page).toHaveURL(/\/home-keeper\/library\/books$/);
    await expect.poll(() => count('books', (b) => b.id === book.id)).toBe(0);
  });

  test('deleting a copy names the book, and the book stays', async ({ page }) => {
    const book = await makeBook(`${PREFIX} copy`);
    await library('add_copy', { book_id: book.id, format: 'paperback' });
    const tab = await openTab(page, `/books/${book.id}`);
    const copies = () => count('copies', (c) => c.book_id === book.id);

    await safeByDefault(page, () => tab.locator('[data-act="delete-copy"]').first().click(), async () => expect(await copies()).toBe(1));
    await tab.locator('[data-act="delete-copy"]').first().click();
    await expect(scrim(page).locator('p')).toContainText(`copy of "${PREFIX} copy"`);
    await ok(page).click();
    await expect.poll(copies).toBe(0);
    expect(await count('books', (b) => b.id === book.id)).toBe(1);
  });

  test('deleting a loan names the book and the party', async ({ page }) => {
    const book = await makeBook(`${PREFIX} loan`);
    const copy = await library<{ copy: { id: string } }>('add_copy', { book_id: book.id, format: 'paperback' });
    const lent = await library<{ loan: { id: string } }>('lend_book', { copy_id: copy.copy.id, party: 'Robin', add_task: false });
    await library('return_loan', { loan_id: lent.loan.id });
    const tab = await openTab(page, '/loans;tab=returned');
    const row = tab.locator('.hkl-listrow').filter({ hasText: `${PREFIX} loan` });
    const exists = async () => expect(await count('loans', (l) => l.id === lent.loan.id)).toBe(1);

    await safeByDefault(page, () => row.locator('[data-act="delete-loan"]').click(), exists);
    await row.locator('[data-act="delete-loan"]').click();
    await expect(scrim(page).locator('p')).toContainText(`loan of "${PREFIX} loan" with Robin`);
    await ok(page).click();
    await expect.poll(() => count('loans', (l) => l.id === lent.loan.id)).toBe(0);
  });

  test('deleting a room counts its bookcases and shelves, and a shelf counts its copies', async ({ page }) => {
    const room = (await library<{ room: { id: string } }>('add_room', { name: `${PREFIX} room` })).room;
    const bookcase = (await library<{ bookcase: { id: string } }>('add_bookcase', { room_id: room.id, name: `${PREFIX} case` })).bookcase;
    const shelf = (await library<{ shelf: { id: string } }>('add_shelf', { bookcase_id: bookcase.id, name: `${PREFIX} shelf` })).shelf;
    const book = await makeBook(`${PREFIX} shelved`);
    await library('add_copy', { book_id: book.id, shelf_id: shelf.id, format: 'paperback' });
    const tab = await openTab(page, '/shelves');
    await tab.locator(`[data-k="room-${room.id}"], [data-id="${room.id}"]`).first().click().catch(() => undefined);
    const exists = (list: string, id: string) => async () => expect(await count(list, (r) => r.id === id)).toBe(1);

    await safeByDefault(page, () => tab.locator(`[data-k="ds-${shelf.id}"]`).click(), exists('shelves', shelf.id));
    await tab.locator(`[data-k="ds-${shelf.id}"]`).click();
    await expect(scrim(page).locator('h2')).toHaveText(`Delete "${PREFIX} shelf"?`);
    await expect(scrim(page).locator('p')).toContainText('Copies that then have no shelf: 1');
    await expect(ok(page)).toHaveText('Delete shelf');
    await cancel(page).click();

    await safeByDefault(page, () => tab.locator(`[data-k="db-${bookcase.id}"]`).click(), exists('bookcases', bookcase.id));
    await tab.locator(`[data-k="db-${bookcase.id}"]`).click();
    await expect(scrim(page).locator('p')).toContainText('Shelves: 1');
    await cancel(page).click();

    await safeByDefault(page, () => tab.locator(`[data-k="dr-${room.id}"]`).click(), exists('rooms', room.id));
    await tab.locator(`[data-k="dr-${room.id}"]`).click();
    await expect(scrim(page).locator('p')).toContainText('Bookcases: 1');
    await expect(scrim(page).locator('p')).toContainText('Shelves: 1');
    await expect(scrim(page).locator('p')).toContainText('Copies that then have no shelf: 1');
    await expect(ok(page)).toHaveText('Delete room');
    await ok(page).click();
    await expect.poll(() => count('rooms', (r) => r.id === room.id)).toBe(0);
    // The copy keeps its book and has no shelf.
    expect(await count('copies', (c) => c.book_id === book.id && !c.shelf_id)).toBe(1);
  });

  test('removing a book from the wishlist asks first', async ({ page }) => {
    const book = await makeBook(`${PREFIX} wish`);
    await library('add_to_wishlist', { book_id: book.id, person_id: 'alex', buy: false });
    const tab = await openTab(page, '/wishlist');
    const wished = async () => expect((await bookByTitle(`${PREFIX} wish`)).wishlist).toBeTruthy();

    await safeByDefault(page, () => tab.locator(`[data-k="wr-${book.id}"]`).click(), wished);
    await tab.locator(`[data-k="wr-${book.id}"]`).click();
    await expect(scrim(page).locator('h2')).toHaveText('Remove from wishlist');
    await expect(scrim(page).locator('p')).toContainText(`"${PREFIX} wish"`);
    await ok(page).click();
    await expect.poll(async () => (await bookByTitle(`${PREFIX} wish`)).wishlist).toBeFalsy();
  });

  test('the import asks first with the counts of the preview, and Escape keeps the import open', async ({ page }) => {
    const before = await adminState();
    const tab = await openTab(page, '/import');
    const dialog = tab.locator('.hkl-dialog');
    await dialog.locator('[data-k="im-file"]').setInputFiles(CSV);
    await expect(dialog.locator('[data-k="import-run"]')).toHaveText('Import 6 rows', { timeout: 30_000 });

    await safeByDefault(page, () => dialog.locator('[data-k="import-run"]').click(), async () => {
      await expect(dialog).toBeVisible();
      expect((await adminState()).books.length).toBe(before.books.length);
    });
    await dialog.locator('[data-k="import-run"]').click();
    await expect(scrim(page).locator('h2')).toHaveText('Import 6 rows');
    await expect(scrim(page).locator('p')).toContainText('Already in the library: 2');
    await expect(scrim(page).locator('p')).toContainText('New books: 4');
    await expect(ok(page)).toHaveText('Import 6 rows');
    await cancel(page).click();
    await dialog.locator('[data-k="import-cancel"]').click();
    await expect(page).toHaveURL(/\/home-keeper\/library\/books$/);
  });

  test('the card has no delete', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto('/home-keeper-library-e2e/library', { waitUntil: 'domcontentloaded' });
    const card: Locator = page.locator('home-keeper-library-card');
    await expect(card.locator('.head h2')).toBeVisible({ timeout: 45_000 });
    await expect(card.locator('[data-act*="delete"], [data-act*="remove"]')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
});
