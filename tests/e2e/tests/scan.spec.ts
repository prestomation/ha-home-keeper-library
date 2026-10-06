import { library } from '../ha-ws';
import type { Page } from '@playwright/test';
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

/**
 * A fake camera (a canvas stream) and a fake `BarcodeDetector`. The detector
 * reads `window.__hklCode` 1 time and then reads nothing. `window.__hklStream`
 * is the last stream that the page got.
 */
async function fakeCamera(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    w.__hklGum = 0;
    w.__hklCode = '';
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const g = canvas.getContext('2d')!;
    let n = 0;
    setInterval(() => {
      g.fillStyle = `hsl(${(n += 7) % 360} 60% 50%)`;
      g.fillRect(0, 0, 320, 240);
    }, 50);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          w.__hklGum = (w.__hklGum as number) + 1;
          w.__hklStream = canvas.captureStream(20);
          return w.__hklStream;
        },
      },
    });
    w.BarcodeDetector = class {
      static async getSupportedFormats(): Promise<string[]> {
        return ['ean_13'];
      }
      async detect(): Promise<Array<{ rawValue: string }>> {
        const code = w.__hklCode as string;
        w.__hklCode = '';
        return code ? [{ rawValue: code }] : [];
      }
    };
  });
}

function pageVar<T>(page: Page, name: string): Promise<T> {
  return page.evaluate((key) => (window as unknown as Record<string, T>)[key], name);
}

test.describe('Scan camera', { tag: '@responsive' }, () => {
  test.beforeEach(deleteNewBook);
  test.afterEach(deleteNewBook);

  test('the camera keeps its picture after a scan, and stops at the summary', async ({ page }) => {
    await fakeCamera(page);
    const shelf = await shelfId('Office', 'Tall bookcase', 'Shelf 3');
    const tab = await openTab(page, `/scan;shelf=${shelf}`);
    await tab.locator('[data-k="scan-start"]').click();
    const video = tab.locator('[data-slot="video"] video');
    const playing = () =>
      video.evaluate((v: HTMLVideoElement) => {
        const tracks = (v.srcObject as MediaStream | null)?.getVideoTracks() ?? [];
        return v.isConnected && !v.paused && tracks.length > 0 && tracks.every((tr) => tr.readyState === 'live');
      });
    await expect.poll(playing).toBe(true);

    // The scan changes the library, and Home Keeper redraws its panel.
    await page.evaluate((isbn) => ((window as unknown as Record<string, unknown>).__hklCode = isbn), NEW_ISBN);
    const row = tab.locator('.hkl-result').filter({ hasText: NEW_TITLE });
    await expect(row.locator('.hkl-pill.ok')).toHaveText('Added', { timeout: 30_000 });
    await expect.poll(playing).toBe(true);
    const t0 = await video.evaluate((v: HTMLVideoElement) => v.currentTime);
    await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(t0);
    expect(await pageVar<number>(page, '__hklGum')).toBe(1);

    await tab.locator('[data-k="scan-done"]').click();
    await expect(tab.locator('.hkl-scan-head')).toContainText('Scan summary');
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __hklStream: MediaStream }).__hklStream.getVideoTracks()[0].readyState))
      .toBe('ended');
  });
});

test.describe('Scan on a page that is not HTTPS', { tag: '@responsive' }, () => {
  test('the camera is blocked with the HTTPS message, and Enter ISBN still starts', async ({ page }) => {
    await page.addInitScript(() => Object.defineProperty(window, 'isSecureContext', { value: false }));
    const tab = await openTab(page, '/scan');
    await expect(tab.locator('[data-k="m-https"]')).toContainText('The camera needs HTTPS.');
    await expect(tab.locator('[data-k="scan-start"]')).toBeDisabled();
    await tab.locator('[data-k="m-manual"]').check();
    await expect(tab.locator('[data-k="m-https"]')).toHaveCount(0);
    await tab.locator('[data-k="scan-start"]').click();
    await expect(page).toHaveURL(/step=camera/);
    await expect(tab.locator('[data-k="isbn-input"]')).toBeVisible();
  });
});
