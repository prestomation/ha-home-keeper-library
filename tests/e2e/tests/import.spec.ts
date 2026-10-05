import { resolve } from 'node:path';
import { adminState, expect, openTab, test } from './helpers';

/**
 * The Import dialog with a small Goodreads export (tests/e2e/seed/goodreads_sample.csv).
 * The test runs only the dry run, so the library does not change.
 */
const CSV = resolve(__dirname, '../seed/goodreads_sample.csv');

test.describe('Import', { tag: '@responsive' }, () => {
  test('a dry run of a Goodreads file shows the preview and changes nothing', async ({ page }) => {
    const before = await adminState();
    const tab = await openTab(page, '/import');
    const dialog = tab.locator('.hkl-dialog');
    await expect(dialog.locator('#hkl-import-title')).toHaveText('Import books');
    await dialog.locator('[data-k="im-file"]').setInputFiles(CSV);
    await expect(dialog.locator('.hkl-file')).toContainText('goodreads_sample.csv · 6 rows');
    await expect(dialog.locator('.hkl-eyebrow').filter({ hasText: 'Preview' })).toBeVisible({ timeout: 30_000 });
    await expect(dialog.locator('.hkl-chips')).toContainText('Already in the library: 2');
    await expect(dialog.locator('.hkl-chips')).toContainText('New books: 4');
    await expect(dialog.locator('[data-k="import-run"]')).toHaveText('Import 6 rows');
    await dialog.locator('.hkl-details summary').click();
    await expect(dialog.locator('.hkl-details tr').filter({ hasText: 'Piranesi' })).toContainText('In the library');
    const after = await adminState();
    expect(after.books.length).toBe(before.books.length);
    await dialog.locator('[data-k="import-cancel"]').click();
    await expect(page).toHaveURL(/\/home-keeper\/library\/books$/);
  });
});
