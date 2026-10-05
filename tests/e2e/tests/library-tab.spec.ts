import { adminState, bookByTitle, expect, libraryTab, openTab, restoreReading, test, trackErrors } from './helpers';

/**
 * The Library tab in the real Home Keeper panel: the tab bar, the book grid, the
 * search, the covers and the book detail. The data is the committed seed
 * (tests/e2e/seed/build_seed.py). A test that changes a reading row puts the seed
 * row back after.
 */
test.describe('Library tab', { tag: '@responsive' }, () => {
  test('Home Keeper shows the Library tab at /home-keeper/library', async ({ page }) => {
    const errors = trackErrors(page);
    const tab = await openTab(page);
    const panel = page.locator('home-keeper-panel');
    await expect(panel.locator('#tab-x-library[active]:visible, #mtab-x-library[aria-current="page"]:visible').first()).toBeVisible();
    await expect(tab.locator('[data-k="nav-books"]')).toHaveAttribute('aria-current', 'page');
    const state = await adminState();
    const owned = state.books.filter((b: { owned: boolean }) => b.owned).length;
    await expect(tab.locator('.hkl-tile')).toHaveCount(owned);
    await expect(tab.locator('[data-k="st-all"]')).toContainText(String(owned));
    expect(errors, errors.join('\n')).toEqual([]);
  });

  test('the search narrows the grid and goes into the URL', async ({ page }) => {
    const tab = await openTab(page);
    await tab.locator('[data-k="q"]').fill('le guin');
    await expect(page).toHaveURL(/\/home-keeper\/library\/books;q=le%20guin$/);
    const state = await adminState();
    const leGuin = state.books.filter((b: { owned: boolean; authors: string[] }) => b.owned && b.authors.includes('Ursula K. Le Guin'));
    await expect(tab.locator('.hkl-tile')).toHaveCount(leGuin.length);
    await expect(tab.locator('.hkl-summary')).toContainText(`${leGuin.length} books`);
    await tab.locator('[data-k="clear"]').click();
    await expect(page).toHaveURL(/\/home-keeper\/library\/books$/);
  });

  test('a cover loads through a signed URL', async ({ page }) => {
    const book = await bookByTitle('Piranesi');
    expect(book.cover_url).toMatch(/^\/api\/home_keeper_library\/cover\//);
    const tab = await openTab(page);
    const img = tab.locator(`[data-k="b-${book.id}"] img`);
    await expect(img).toHaveAttribute('src', /authSig=/);
    await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
  });

  test('the shared notes render as Markdown', async ({ page }) => {
    const book = await bookByTitle('The Left Hand of Darkness');
    const tab = await openTab(page, `/books/${book.id}`);
    await expect(tab.locator('h1')).toHaveText(book.title);
    const md = tab.locator('ha-markdown.hkl-md');
    await expect(md.locator('strong')).toHaveText('Oct 2026');
    await expect(tab.locator('.hkl-md-plain')).toHaveCount(0);
  });
});

test.describe('Book detail', { tag: '@responsive' }, () => {
  const TITLE = 'The Lathe of Heaven';
  let seedRow: Record<string, unknown> | undefined;
  let bookId = '';

  test.beforeEach(async () => {
    const book = await bookByTitle(TITLE);
    bookId = book.id;
    seedRow = book.reading.alex;
  });

  test.afterEach(async () => {
    await restoreReading(bookId, 'alex', seedRow);
  });

  test('sets the reading status and the rating', async ({ page }) => {
    const tab = await openTab(page, `/books/${bookId}`);
    await expect(tab.locator('[data-k="rs-want"]')).toHaveAttribute('aria-pressed', 'true');
    await tab.locator('[data-k="rs-reading"]').click();
    await expect(tab.locator('[data-k="rs-reading"]')).toHaveAttribute('aria-pressed', 'true');
    await tab.locator('[data-k="star-4"]').click();
    await expect(tab.locator('.hkl-star.on')).toHaveCount(4);
    await expect
      .poll(async () => {
        const row = (await bookByTitle(TITLE)).reading.alex;
        return [row.status, row.rating, Boolean(row.started)];
      })
      .toEqual(['reading', 4, true]);
    // The card status on the grid follows.
    await libraryTab(page).locator('[data-k="back"]').click();
    await expect(page).toHaveURL(/\/home-keeper\/library\/books$/);
  });
});
