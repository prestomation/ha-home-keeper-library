import { library } from '../ha-ws';
import { adminState, bookByTitle, expect, openTab, test } from './helpers';

/**
 * The Wishlist view: the rows, the Buy box that sends the book to the to-do list
 * of the person, and the add dialog. Each test puts the seed back.
 */
const BUY_TITLE = 'The Obelisk Gate';
const NEW_TITLE = 'Spinning Silver';

test.describe('Wishlist', { tag: '@responsive' }, () => {
  test.afterEach(async () => {
    const obelisk = await bookByTitle(BUY_TITLE);
    await library('update_wishlist', { book_id: obelisk.id, buy: false });
    const spinning = await bookByTitle(NEW_TITLE);
    if (spinning.wishlist) await library('remove_from_wishlist', { book_id: spinning.id });
  });

  test('lists the wishlist and Buy adds the book to the list of the person', async ({ page }) => {
    const tab = await openTab(page, '/wishlist');
    const state = await adminState();
    const wished = state.books.filter((b: { wishlist: unknown }) => b.wishlist);
    await expect(tab.locator('.hkl-listrow')).toHaveCount(wished.length);
    await expect(tab.locator('.hkl-todo').first()).toContainText('Alex books');

    const book = await bookByTitle(BUY_TITLE);
    const box = tab.locator(`[data-k="buy-${book.id}"]`);
    await expect(box).not.toBeChecked();
    await box.check();
    await expect.poll(async () => (await bookByTitle(BUY_TITLE)).wishlist.todo_uid, { timeout: 30_000 }).toBeTruthy();
    await expect(box).toBeChecked();
  });

  test('adds a book from the library to the wishlist', async ({ page }) => {
    const book = await bookByTitle(NEW_TITLE);
    const tab = await openTab(page, `/books/${book.id}`);
    await tab.locator('[data-k="wish-this"]').click();
    const dialog = tab.locator('.hkl-dialog');
    await dialog.locator('[data-k="d-submit"]').click();
    await expect(tab.locator('.hkl-banner')).toContainText('On the wishlist of Alex');
    expect((await bookByTitle(NEW_TITLE)).wishlist).toMatchObject({ person_id: 'alex', buy: false });
  });
});
