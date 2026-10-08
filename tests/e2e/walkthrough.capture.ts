/**
 * The video walkthrough of the Library tab, for the PR comment (not committed).
 *
 *   KEEP_UP=1 NO_TESTS=1 bash ci/e2e-up.sh
 *   bash ci/capture-video.sh        # writes docs/videos/walkthrough.{webm,mp4,gif}
 *
 * The tour: open the Library tab in Home Keeper, browse the grid, search, open a
 * book, set the reading status, scan a book by ISBN into a shelf, lend a book with
 * a Home Keeper task, see the loan, and open the card on a dashboard. `BEAT` pauses
 * let each step read in the video. The tour puts the seed back at the end.
 *
 * The recording needs its own context: `recordVideo` is set when a context is made.
 */
import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { library } from './ha-ws';
import { adminState, bookByTitle, noServiceWorker, openCard, openTab, restoreReading } from './tests/helpers';
import { DESKTOP } from './viewports';

const OUT = process.env.VIDEO_DIR || '/tmp/home-keeper-library-video';
const BEAT = 900;
const NEW_ISBN = '9780553418606';
const LEND_TITLE = 'Station Eleven';
const PARTY = 'Robin';
const STATUS_TITLE = 'The Lathe of Heaven';

async function beat(page: Page, n = 1): Promise<void> {
  await page.waitForTimeout(BEAT * n);
}

async function cleanUp(): Promise<void> {
  const state = await adminState();
  for (const book of state.books.filter((b: { isbn13: string }) => b.isbn13 === NEW_ISBN)) {
    await library('delete_book', { book_id: book.id });
  }
  const lent = state.books.find((b: { title: string }) => b.title === LEND_TITLE);
  for (const loan of state.loans.filter((l: { book_id: string; party: string }) => l.book_id === lent.id && l.party === PARTY)) {
    await library('delete_loan', { loan_id: loan.id });
  }
}

test('record the Library walkthrough', async ({ browser }) => {
  await cleanUp();
  const status = await bookByTitle(STATUS_TITLE);
  const seedRow = status.reading.alex;
  const context = await browser.newContext({
    storageState: './.auth/state.json',
    viewport: DESKTOP,
    recordVideo: { dir: OUT, size: DESKTOP },
  });
  await noServiceWorker(context);
  const page = await context.newPage();
  try {
    // 1. The Library tab in the Home Keeper panel, with the book grid.
    const tab = await openTab(page, '/books');
    await expect(tab.locator('.hkl-tile').first()).toBeVisible();
    await beat(page, 2);
    await tab.locator('.hkl-grid').evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    await beat(page);

    // 2. Search, then open a book.
    await tab.locator('[data-k="q"]').pressSequentially('lathe', { delay: 90 });
    await expect(tab.locator('.hkl-tile')).toHaveCount(1);
    await beat(page);
    await tab.locator(`[data-k="b-${status.id}"]`).click();
    await expect(tab.locator('h1')).toHaveText(STATUS_TITLE);
    await beat(page);

    // 3. Set the reading status and a rating.
    await tab.locator('[data-k="rs-reading"]').click();
    await expect(tab.locator('[data-k="rs-reading"]')).toHaveAttribute('aria-pressed', 'true');
    await beat(page);
    await tab.locator('[data-k="star-4"]').click();
    await expect(tab.locator('.hkl-star.on')).toHaveCount(4);
    await beat(page);

    // 4. Scan a book by ISBN into a shelf.
    const state = await adminState();
    const office = state.rooms.find((r: { name: string }) => r.name === 'Office');
    const tall = state.bookcases.find((c: { room_id: string }) => c.room_id === office.id);
    const shelf = state.shelves.find((s: { bookcase_id: string; name: string }) => s.bookcase_id === tall.id && s.name === 'Shelf 3');
    // The scan setup opens by its URL, with the shelf picked.
    await openTab(page, `/scan;shelf=${shelf.id}`);
    await expect(tab.locator('.hkl-scan-head')).toContainText('Scan books');
    await beat(page);
    await tab.locator('[data-k="m-manual"]').check();
    await expect(tab.locator('[data-k="m-manual"]')).toBeChecked();
    await beat(page);
    await tab.locator('[data-k="scan-start"]').click();
    await expect(tab.locator('[data-k="isbn-input"]')).toBeVisible();
    await beat(page);
    await tab.locator('[data-k="isbn-input"]').pressSequentially(NEW_ISBN, { delay: 60 });
    await tab.locator('[data-k="isbn-add"]').click();
    await expect(tab.locator('.hkl-result .hkl-pill.ok')).toHaveText('Added', { timeout: 30_000 });
    await beat(page, 2);
    await tab.locator('[data-k="scan-done"]').click();
    await expect(tab.locator('.hkl-scan-head')).toContainText('Scan summary');
    await beat(page, 2);
    // Done opens the room of the shelf, with the new spine on it.
    await tab.locator('[data-k="scan-finish"]').click();
    await expect(tab.locator('.hkl-room h1')).toHaveText('Office');
    await beat(page, 2);

    // 5. Lend a book. The loan has a due date, so Home Keeper gets a task.
    const lend = await bookByTitle(LEND_TITLE);
    await tab.locator('[data-k="nav-books"]').click();
    await tab.locator('[data-k="q"]').fill('');
    await tab.locator('[data-k="q"]').pressSequentially('station', { delay: 90 });
    await expect(tab.locator('.hkl-tile')).toHaveCount(1);
    await tab.locator(`[data-k="b-${lend.id}"]`).click();
    await expect(tab.locator('h1')).toHaveText(LEND_TITLE);
    await beat(page);
    await tab.locator('[data-k="lend"]').click();
    const dialog = tab.locator('.hkl-dialog');
    await dialog.locator('[name="party"]').pressSequentially(PARTY, { delay: 90 });
    await dialog.locator('[name="due"]').fill('2026-12-01');
    await beat(page);
    await dialog.locator('[data-k="d-submit"]').click();
    await expect(tab.locator('a.hkl-task')).toBeVisible({ timeout: 30_000 });
    await beat(page, 2);

    // 6. The Loans view, then the task in Home Keeper.
    await tab.locator('[data-k="nav-loans"]').click();
    await expect(tab.locator('.hkl-listrow').first()).toBeVisible();
    await beat(page, 2);
    await tab.locator('.hkl-listrow').filter({ hasText: LEND_TITLE }).locator('a.hkl-task').click();
    await expect(page).toHaveURL(/\/home-keeper\/tasks\//);
    // Home Keeper 0.30.0 loads a task that a companion added only on a page load.
    await page.reload();
    await expect(page.locator('home-keeper-panel')).toContainText(`Get ${LEND_TITLE} back from ${PARTY}`, { timeout: 30_000 });
    await beat(page, 2);

    // 7. The card on a dashboard.
    await openCard(page);
    await beat(page, 3);
  } finally {
    const video = page.video();
    await context.close();
    if (video) await video.saveAs(resolve(OUT, 'walkthrough.webm'));
    await cleanUp();
    await restoreReading(status.id, 'alex', seedRow);
  }
});
