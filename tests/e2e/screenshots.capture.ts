/**
 * The screenshots of the Library tab and the card, for docs/images/ and the PR.
 *
 *   KEEP_UP=1 NO_TESTS=1 bash ci/e2e-up.sh
 *   cd tests/e2e && SHOT_DIR=../../docs/images npx playwright test --config=screenshots.config.ts
 *
 * Desktop shots are 1280 px wide and phone shots 390 px wide (`viewports.ts`). The
 * phone shots come last, in 1 `setViewportSize(PHONE)` block, and have `-mobile` in
 * the name. The capture puts the seed back: it deletes the books that the scan adds.
 * A spec under tests/ asserts on each surface here.
 */
import { expect, test, type Locator, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { library } from './ha-ws';
import { adminState, bookByTitle, libraryTab, noServiceWorker, openCard, openTab } from './tests/helpers';
import { PHONE } from './viewports';

const SHOT_DIR = resolve(__dirname, process.env.SHOT_DIR || '../../docs/images');
const DESKTOP_SHOT = { width: 1280, height: 900 };
const SCAN_ISBNS = ['9780553418606', '9780441478125', '9781250313188'];
/** The scanned books that are not in the seed. The 2nd ISBN is a seeded book. */
const NEW_ISBNS = [SCAN_ISBNS[0], SCAN_ISBNS[2]];

async function shot(page: Page, name: string): Promise<void> {
  // Let the covers and the fonts settle, and move the pointer out of the way.
  await page.mouse.move(0, 0);
  await page.waitForTimeout(600);
  await page.screenshot({ path: resolve(SHOT_DIR, `${name}.png`) });
}

/** A screenshot from the top of the page to a little below *el*. */
async function shotTo(page: Page, el: Locator, name: string): Promise<void> {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(600);
  const box = await el.boundingBox();
  const view = page.viewportSize();
  if (!box || !view) throw new Error(`no box for ${name}`);
  const height = Math.min(view.height, Math.ceil(box.y + box.height + 16));
  await page.screenshot({ path: resolve(SHOT_DIR, `${name}.png`), clip: { x: 0, y: 0, width: view.width, height } });
}

async function coversLoaded(page: Page): Promise<void> {
  const tab = libraryTab(page);
  await expect
    .poll(() =>
      tab.evaluate((el) =>
        [...(el.shadowRoot?.querySelectorAll<HTMLImageElement>('.hkl-cover img') ?? [])]
          // A lazy image below the fold does not load; only the ones on screen count.
          .filter((img) => {
            const box = img.getBoundingClientRect();
            return box.bottom > 0 && box.top < window.innerHeight;
          })
          .every((img) => img.complete && img.naturalWidth > 0),
      ),
    )
    .toBe(true);
}

async function deleteScanned(): Promise<void> {
  const state = await adminState();
  for (const book of state.books) {
    if (NEW_ISBNS.includes(book.isbn13)) {
      await library('delete_book', { book_id: book.id });
    }
  }
}

async function scanSession(page: Page): Promise<void> {
  const state = await adminState();
  const office = state.rooms.find((r: { name: string }) => r.name === 'Office');
  const tall = state.bookcases.find((c: { room_id: string }) => c.room_id === office.id);
  const shelf = state.shelves.find((s: { bookcase_id: string; name: string }) => s.bookcase_id === tall.id && s.name === 'Shelf 3');
  const tab = await openTab(page, `/scan;shelf=${shelf.id}`);
  await tab.locator('[data-k="m-manual"]').check();
  await expect(tab.locator('[data-k="m-manual"]')).toBeChecked();
  await tab.locator('[data-k="scan-start"]').click();
  for (const isbn of SCAN_ISBNS) {
    await tab.locator('[data-k="isbn-input"]').fill(isbn);
    await tab.locator('[data-k="isbn-add"]').click();
    // Each lookup reads Open Library 1 request a second, so wait for it to end.
    await expect(tab.locator('.hkl-result').filter({ hasText: 'Searching Open Library' })).toHaveCount(0, { timeout: 30_000 });
  }
  await expect(tab.locator('.hkl-result')).toHaveCount(3);
}

/** Open the Lend dialog of a book with a copy to lend, type a note, and submit with no borrower. */
async function openLendError(page: Page): Promise<void> {
  const state = await adminState();
  const lent = new Set(state.loans.filter((l: any) => !l.returned).map((l: any) => l.copy_id));
  const copy = state.copies.find((c: any) => !lent.has(c.id) && c.format !== 'ebook' && c.format !== 'audiobook');
  if (!copy) throw new Error('no copy to lend in the seed');
  const tab = await openTab(page, `/books/${copy.book_id}`);
  await coversLoaded(page);
  await tab.locator('[data-k="lend"]').click();
  const dialog = tab.locator('.hkl-dialog');
  await dialog.locator('[name="note"]').fill('Back by the trip');
  await dialog.locator('[data-k="d-submit"]').click();
  await expect(dialog.locator('.hkl-error')).toBeVisible();
}

test.describe.configure({ mode: 'serial' });

test('capture the Library screenshots', async ({ page, browser }) => {
  test.setTimeout(300_000);
  await noServiceWorker(page.context());
  await deleteScanned();
  await page.setViewportSize(DESKTOP_SHOT);

  // Books grid.
  await openTab(page, '/books');
  await coversLoaded(page);
  await shot(page, 'books-desktop');

  // Book detail: a custom cover, a loan with its task, shared notes in Markdown. The
  // window is tall enough to show the notes.
  await page.setViewportSize({ width: 1280, height: 1400 });
  const left = await bookByTitle('The Left Hand of Darkness');
  let tab = await openTab(page, `/books/${left.id}`);
  await expect(tab.locator('ha-markdown strong')).toHaveText('Oct 2026');
  await coversLoaded(page);
  await shot(page, 'book-detail-desktop');

  // The Lend dialog after an error: the error line shows and the typed text stays.
  await page.setViewportSize(DESKTOP_SHOT);
  await openLendError(page);
  await shot(page, 'dialog-error-desktop');

  // Rooms and shelves.
  await openTab(page, '/shelves');
  await shot(page, 'shelves-desktop');

  // Loans.
  tab = await openTab(page, '/loans');
  await expect(tab.locator('a.hkl-task').first()).toBeVisible({ timeout: 30_000 });
  await coversLoaded(page);
  await shot(page, 'loans-desktop');

  // Wishlist.
  tab = await openTab(page, '/wishlist');
  await expect(tab.locator('.hkl-todo').first()).toContainText('Alex books');
  await coversLoaded(page);
  await shot(page, 'wishlist-desktop');

  // Import, after the dry run of the sample Goodreads file.
  tab = await openTab(page, '/import');
  await tab.locator('[data-k="im-file"]').setInputFiles(resolve(__dirname, 'seed/goodreads_sample.csv'));
  await expect(tab.locator('.hkl-dialog .hkl-chips')).toContainText('New books', { timeout: 30_000 });
  await tab.locator('.hkl-details summary').click();
  await shot(page, 'import-desktop');

  // Settings.
  tab = await openTab(page, '/settings');
  await expect(tab.locator('[data-k="currency"]')).toHaveValue('EUR');
  await shot(page, 'settings-desktop');

  // The card on a dashboard, as Alex. The window is tall enough for the whole card.
  await page.setViewportSize({ width: 1280, height: 1500 });
  const card = await openCard(page);
  await expect(card.locator('.ring')).toBeVisible();
  await shotTo(page, card, 'card-desktop');

  // ── Phone ────────────────────────────────────────────────────────────────
  await page.setViewportSize(PHONE);
  await openTab(page, '/books');
  await coversLoaded(page);
  await shot(page, 'books-mobile');

  await openTab(page, `/books/${left.id}`);
  await coversLoaded(page);
  await shot(page, 'book-detail-mobile');

  await openLendError(page);
  await shot(page, 'dialog-error-mobile');

  await openTab(page, '/shelves');
  await shot(page, 'shelves-mobile');

  tab = await openTab(page, '/loans');
  await expect(tab.locator('a.hkl-task').first()).toBeVisible({ timeout: 30_000 });
  await shot(page, 'loans-mobile');

  await scanSession(page);
  await shot(page, 'scan-mobile');
  // Skip the duplicate, so the seed keeps its copies.
  await libraryTab(page).locator('.hkl-result.dup').getByRole('button', { name: 'Skip' }).click();
  await expect(libraryTab(page).locator('.hkl-result.dup')).toHaveCount(0);
  await libraryTab(page).locator('[data-k="scan-done"]').click();
  await expect(libraryTab(page).locator('.hkl-scan-head')).toContainText('Scan summary');
  await shot(page, 'scan-summary-mobile');
  await deleteScanned();

  // The setup step on a page that is not HTTPS: the camera is blocked.
  const http = await browser.newContext({ storageState: './.auth/state.json', viewport: PHONE });
  await noServiceWorker(http);
  await http.addInitScript(() => Object.defineProperty(window, 'isSecureContext', { value: false }));
  const httpPage = await http.newPage();
  const httpTab = await openTab(httpPage, '/scan');
  await expect(httpTab.locator('[data-k="m-https"]')).toBeVisible();
  await shot(httpPage, 'scan-https-mobile');
  await http.close();

  // The card on a phone, as Sam (a user who is not an admin).
  const sam = await browser.newContext({ storageState: './.auth/sam.json', viewport: { width: PHONE.width, height: 1250 } });
  await noServiceWorker(sam);
  const samPage = await sam.newPage();
  const samCard = await openCard(samPage);
  await expect(samCard.locator('.head h2')).toHaveText('Library: Sam');
  await shotTo(samPage, samCard, 'card-mobile');
  await sam.close();
});
