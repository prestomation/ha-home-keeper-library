import { library } from '../ha-ws';
import { adminState, bookByTitle, expect, openTab, test, userState } from './helpers';

/**
 * Send a book to Open Library: the account card in Settings, the "Not on Open
 * Library" list and the send from the book page. The fixture server of
 * tests/e2e/seed/openlibrary acts as Open Library: it takes the fixture S3 keys
 * and adds every book as the edition OL9000001M.
 *
 * The tests run in order, because the account is shared. The last step removes
 * the account and the book that the tests add.
 */
const ACCESS = 'E2E-ACCESS';
const SECRET = 'E2E-SECRET';
const NEW_TITLE = 'E2E Field Notes';
// A valid ISBN that the fixture server does not have, so the lookup finds nothing.
const NEW_ISBN = '9780000000996';
// The seed books that the lookup did not find, in the author order of the list. The
// last 2 have no author, so their rows ask for one and have no Send button.
const MISSING = ['Every Grain of Rice', 'Steering the Craft', '9780980123468', 'Untitled paperback'];

async function removeNewBook(): Promise<void> {
  const state = await adminState();
  const book = state.books.find((b: { title: string }) => b.title === NEW_TITLE);
  if (book) await library('delete_book', { book_id: book.id });
}

test.describe('Open Library list', { tag: '@responsive' }, () => {
  test('lists the seed books that Open Library does not have', async ({ page }) => {
    const tab = await openTab(page, '/books;status=not_on_ol');
    await expect(tab.locator('[data-k="st-not_on_ol"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(tab.locator('.hkl-olrow .hkl-row-title')).toHaveText(MISSING);
    await expect(tab.locator('[data-k="ol-list-hint"]')).toContainText(`(${MISSING.length})`);
    const untitled = tab.locator('.hkl-olrow').filter({ hasText: 'Untitled paperback' });
    await expect(untitled.locator('.hkl-row-hint')).toHaveText('Add an author before you send');
    await expect(untitled.locator('[data-act="send-ol"]')).toHaveCount(0);
    // Each row fits: the buttons wrap under the book on a phone, never off the screen.
    const width = await tab.locator('.hkl-olrow').first().evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(width).toBe(0);
  });

  test('only an admin gets the account state', async () => {
    expect(await userState()).not.toHaveProperty('catalog_accounts');
    expect((await adminState()).catalog_accounts).toEqual({ openlibrary: { connected: false, username: null } });
  });
});

test.describe.serial('Open Library send', () => {
  test.afterAll(async () => {
    await removeNewBook();
    await library('disconnect_catalog');
  });

  test('connects an account with the S3 keys', async ({ page }) => {
    const tab = await openTab(page, '/settings');
    const card = tab.locator('[data-k="ol-card"]');
    await card.locator('[data-k="ol-access"]').fill(ACCESS);
    await card.locator('[data-k="ol-secret"]').fill('wrong');
    await card.locator('[data-k="ol-connect-save"]').click();
    await expect(card.locator('[data-k="ol-error"]')).toHaveText('Open Library did not accept these keys.');
    await expect(card.locator('[data-k="ol-access"]')).toHaveValue(ACCESS);
    await card.locator('[data-k="ol-secret"]').fill(SECRET);
    await card.locator('[data-k="ol-connect-save"]').click();
    await expect(card.locator('[data-k="ol-connected"]')).toHaveText('Connected as e2e_reader');
    expect((await adminState()).catalog_accounts).toEqual({ openlibrary: { connected: true, username: 'e2e_reader' } });
  });

  test('sends a new book and links the new edition', async ({ page }) => {
    await removeNewBook();
    const added = await library<{ book: { id: string } }>('add_book', {
      title: NEW_TITLE,
      authors: ['Ada Fixture'],
      publisher: 'Fixture Press',
      published: '2026',
      isbn: NEW_ISBN,
    });
    const id = added.book.id;
    await expect.poll(async () => (await bookByTitle(NEW_TITLE)).catalog_status).toEqual({ openlibrary: 'missing' });
    const tab = await openTab(page, `/books/${id}`);
    await expect(tab.locator('[data-k="ol-banner"]')).toContainText('Open Library does not have this book');
    await tab.locator('[data-k="ol-banner-send"]').click();
    const dialog = tab.locator('.hkl-dialog');
    await expect(dialog).toContainText('You send as e2e_reader.');
    await expect(dialog.locator('[data-k="d-send-isbn"]')).toBeChecked();
    await dialog.locator('[data-k="d-submit"]').click();
    await expect(dialog.locator('[data-k="d-ol-added"]')).toContainText('OL9000001M');
    await expect(dialog.locator('[data-k="d-ol-edit"]')).toHaveAttribute('href', 'https://openlibrary.org/books/OL9000001M/edit');
    await dialog.locator('[data-k="d-submit"]').click();
    await expect(dialog).toHaveCount(0);
    await expect(tab.locator('[data-k="ol-banner"]')).toHaveCount(0);
    const linked = await bookByTitle(NEW_TITLE);
    expect(linked.catalogs.openlibrary.edition_key).toBe('OL9000001M');
    expect(linked.catalog_status).toEqual({});
    // The library keeps what the user typed. Open Library fills only the empty fields.
    expect(linked.publisher).toBe('Fixture Press');
  });

  test('Not now takes a book off the list, and the book can come back', async ({ page }) => {
    const book = await bookByTitle(MISSING[0]);
    const tab = await openTab(page, `/books/${book.id}`);
    await tab.locator('[data-k="ol-not-now"]').click();
    await expect(tab.locator('[data-k="ol-banner"]')).toHaveCount(0);
    await expect(tab.locator('[data-k="ol-send-later"]')).toBeVisible();
    expect((await bookByTitle(MISSING[0])).catalog_status).toEqual({ openlibrary: 'skipped' });
    await library('skip_catalog', { book_id: book.id, skip: false });
    await expect(tab.locator('[data-k="ol-banner"]')).toBeVisible();
  });
});
