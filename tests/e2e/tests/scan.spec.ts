import { library } from '../ha-ws';
import type { Locator, Page } from '@playwright/test';
import { resolve } from 'node:path';
import { adminState, bookByTitle, expect, fakeCamera, openTab, test } from './helpers';

/**
 * The Scan flow with Enter ISBN, against the Open Library fixture server
 * (tests/e2e/seed/openlibrary). The new book is deleted after the test.
 */
const NEW_ISBN = '9780553418606';
const NEW_TITLE = 'The Library at Mount Char';
const SEEDED_ISBN = '9780441478125';
/** The fixture Open Library does not have this ISBN. */
const MISS_ISBN = '9781402894626';
const MISS_TITLE = 'Field Notes on Moss';
const COVER = resolve(__dirname, '../seed/covers/13be6b0e5c354e1981a89fe2766196e0-552257a9.jpg');

async function shelfId(room: string, bookcase: string, shelf: string): Promise<string> {
  const state = await adminState();
  const r = state.rooms.find((x: { name: string }) => x.name === room);
  const c = state.bookcases.find((x: { name: string; room_id: string }) => x.name === bookcase && x.room_id === r.id);
  return state.shelves.find((x: { name: string; bookcase_id: string }) => x.name === shelf && x.bookcase_id === c.id).id;
}

async function deleteNewBook(): Promise<void> {
  const state = await adminState();
  for (const book of state.books.filter((b: { isbn13: string }) => b.isbn13 === NEW_ISBN || b.isbn13 === MISS_ISBN)) {
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

  test('a book with no match asks for its title before the next scan', async ({ page }) => {
    const shelf = await shelfId('Office', 'Tall bookcase', 'Shelf 3');
    const tab = await openTab(page, `/scan;shelf=${shelf}`);
    await tab.locator('[data-k="m-manual"]').check();
    await tab.locator('[data-k="scan-start"]').click();
    await tab.locator('[data-k="isbn-input"]').fill(MISS_ISBN);
    await tab.locator('[data-k="isbn-add"]').click();

    const sheet = tab.locator('.hkl-dialog.sheet');
    await expect(sheet).toBeVisible({ timeout: 30_000 });
    await expect(sheet.locator('h2')).toHaveText('No match in Open Library');
    await expect(sheet.locator('[data-k="d-isbn"]')).toHaveText(`ISBN ${MISS_ISBN}`);
    await expect(sheet.locator('[name="title"]')).toBeFocused();
    const submit = sheet.locator('[data-k="d-submit"]');
    await expect(submit).toBeDisabled();
    await expect(sheet.locator('[name="authors"]')).toBeHidden();
    await page.keyboard.press('Escape');
    await expect(sheet).toBeVisible();

    await sheet.locator('[name="title"]').fill(MISS_TITLE);
    await expect(submit).toBeEnabled();
    await sheet.locator('[data-k="d-more-toggle"]').click();
    await sheet.locator('[name="authors"]').fill('A. Hollins');
    await sheet.locator('[name="format"]').selectOption('hardcover');
    await sheet.locator('[data-k="d-cover"]').setInputFiles(COVER);
    await expect(sheet.locator('[data-k="d-cover-name"]')).toHaveText('13be6b0e5c354e1981a89fe2766196e0-552257a9.jpg');
    await submit.click();
    await expect(sheet).toHaveCount(0);
    await expect(tab.locator('.hkl-result').filter({ hasText: MISS_TITLE })).toContainText('No match in Open Library');

    const state = await adminState();
    const book = state.books.find((b: { isbn13: string }) => b.isbn13 === MISS_ISBN);
    expect(book).toMatchObject({ title: MISS_TITLE, authors: ['A. Hollins'], needs_details: true });
    expect(book.cover.kind).toBe('custom');
    const copies = state.copies.filter((c: { book_id: string }) => c.book_id === book.id);
    expect(copies.map((c: { shelf_id: string; format: string }) => [c.shelf_id, c.format])).toEqual([[shelf, 'hardcover']]);
  });

  test('Remove this scan deletes the book with no match', async ({ page }) => {
    const tab = await openTab(page, '/scan');
    await tab.locator('[data-k="m-manual"]').check();
    await tab.locator('[data-k="scan-start"]').click();
    await tab.locator('[data-k="isbn-input"]').fill(MISS_ISBN);
    await tab.locator('[data-k="isbn-add"]').click();
    const sheet = tab.locator('.hkl-dialog.sheet');
    await expect(sheet).toBeVisible({ timeout: 30_000 });
    await sheet.locator('[data-k="d-remove"]').click();
    await expect(sheet).toHaveCount(0);
    await expect(tab.locator('[data-k^="removed-"]')).toHaveText('Removed');
    const state = await adminState();
    expect(state.books.filter((b: { isbn13: string }) => b.isbn13 === MISS_ISBN)).toEqual([]);
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

function pageVar<T>(page: Page, name: string): Promise<T> {
  return page.evaluate((key) => (window as unknown as Record<string, T>)[key], name);
}

/** True when the video is in the page, plays, and has a live camera track. */
function playing(video: Locator): Promise<boolean> {
  return video.evaluate((v: HTMLVideoElement) => {
    const tracks = (v.srcObject as MediaStream | null)?.getVideoTracks() ?? [];
    return v.isConnected && !v.paused && tracks.length > 0 && tracks.every((tr) => tr.readyState === 'live');
  });
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
    await expect.poll(() => playing(video)).toBe(true);
    // Count the pauses. A video that leaves the page pauses, and a phone app can refuse to play it again.
    await video.evaluate((v: HTMLVideoElement) => {
      const w = window as unknown as Record<string, number>;
      w.__hklPauses = 0;
      v.addEventListener('pause', () => w.__hklPauses++);
    });

    // The scan changes the library, and Home Keeper redraws its panel.
    await page.evaluate((isbn) => ((window as unknown as Record<string, unknown>).__hklCode = isbn), NEW_ISBN);
    const row = tab.locator('.hkl-result').filter({ hasText: NEW_TITLE });
    await expect(row.locator('.hkl-pill.ok')).toHaveText('Added', { timeout: 30_000 });
    await expect.poll(() => playing(video)).toBe(true);
    expect(await pageVar<number>(page, '__hklPauses')).toBe(0);
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

test.describe('Scan camera with no match', { tag: '@responsive' }, () => {
  test.beforeEach(deleteNewBook);
  test.afterEach(deleteNewBook);

  test('the camera shows Scan paused and reads no code until the title is saved', async ({ page }) => {
    await fakeCamera(page);
    const tab = await openTab(page, '/scan');
    await tab.locator('[data-k="scan-start"]').click();
    const video = tab.locator('[data-slot="video"] video');
    await expect.poll(() => playing(video)).toBe(true);
    await page.evaluate((isbn) => ((window as unknown as Record<string, unknown>).__hklCode = isbn), MISS_ISBN);
    const sheet = tab.locator('.hkl-dialog.sheet');
    await expect(sheet).toBeVisible({ timeout: 30_000 });
    await expect(tab.locator('[data-k="cam-paused"]')).toHaveText('Scan paused');

    // A code read now adds no book.
    await page.evaluate((isbn) => ((window as unknown as Record<string, unknown>).__hklCode = isbn), NEW_ISBN);
    await expect.poll(() => page.evaluate(() => (window as unknown as Record<string, string>).__hklCode)).toBe('');
    await expect(tab.locator('.hkl-result')).toHaveCount(1);

    await sheet.locator('[name="title"]').fill(MISS_TITLE);
    await sheet.locator('[data-k="d-submit"]').click();
    await expect(sheet).toHaveCount(0);
    await expect(tab.locator('[data-k="cam-paused"]')).toHaveCount(0);
    expect(await playing(video)).toBe(true);
    const state = await adminState();
    expect(state.books.filter((b: { isbn13: string }) => b.isbn13 === NEW_ISBN)).toEqual([]);
  });
});

test.describe('Scan camera recovery', { tag: '@responsive' }, () => {
  test('a refused play() shows the restart button, and a tap starts the picture again', async ({ page }) => {
    await fakeCamera(page);
    const tab = await openTab(page, '/scan');
    await tab.locator('[data-k="scan-start"]').click();
    const video = tab.locator('[data-slot="video"] video');
    await expect.poll(() => playing(video)).toBe(true);
    await video.evaluate((v: HTMLVideoElement) => v.setAttribute('data-first', ''));

    await page.evaluate(() => ((window as unknown as Record<string, unknown>).__hklRefusePlay = true));
    await video.evaluate((v: HTMLVideoElement) => v.pause());
    const restart = tab.locator('[data-k="cam-restart"]');
    await expect(restart).toHaveText('The camera stopped. Tap to start it again.');

    await page.evaluate(() => ((window as unknown as Record<string, unknown>).__hklRefusePlay = false));
    await restart.click();
    await expect(restart).toHaveCount(0);
    await expect.poll(() => playing(video)).toBe(true);
    await expect(video).toHaveAttribute('data-first', '');
    expect(await pageVar<number>(page, '__hklGum')).toBe(1);
  });

  test('a tap opens a new camera when the camera track ended', async ({ page }) => {
    await fakeCamera(page);
    const tab = await openTab(page, '/scan');
    await tab.locator('[data-k="scan-start"]').click();
    const video = tab.locator('[data-slot="video"] video');
    await expect.poll(() => playing(video)).toBe(true);
    await page.evaluate(() => {
      const track = (window as unknown as { __hklStream: MediaStream }).__hklStream.getVideoTracks()[0];
      track.stop();
      track.dispatchEvent(new Event('ended'));
    });
    await tab.locator('[data-k="cam-restart"]').click();
    await expect(tab.locator('[data-k="cam-restart"]')).toHaveCount(0);
    await expect.poll(() => playing(video)).toBe(true);
    expect(await pageVar<number>(page, '__hklGum')).toBe(2);
  });

  test('the debug view shows the camera state and log', async ({ page }) => {
    await fakeCamera(page);
    const tab = await openTab(page, '/scan;debug=1');
    await tab.locator('[data-k="scan-start"]').click();
    await expect(page).toHaveURL(/step=camera;debug=1/);
    const debug = tab.locator('[data-k="cam-debug"]');
    await expect(debug).toContainText('video: paused=false');
    await expect(debug).toContainText('track: live');
    await expect(debug).toContainText('detector: native');
    await expect(debug).toContainText('getUserMedia ok');
    await expect(debug).toContainText(/tab \d+ of \d+: in page=true/);
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
