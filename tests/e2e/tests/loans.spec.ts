import { library } from '../ha-ws';
import { adminState, bookByTitle, expect, homeKeeperTasks, openTab, test } from './helpers';

/**
 * Lend a book and see its task in the real Home Keeper. The loan is deleted after,
 * and the library deletes its task.
 */
const TITLE = 'Station Eleven';
const PARTY = 'Robin';

async function deleteLoans(): Promise<void> {
  const state = await adminState();
  const book = state.books.find((b: { title: string }) => b.title === TITLE);
  for (const loan of state.loans.filter((l: { book_id: string; party: string }) => l.book_id === book.id && l.party === PARTY)) {
    await library('delete_loan', { loan_id: loan.id });
  }
}

test.describe('Loans', { tag: '@responsive' }, () => {
  test.beforeEach(deleteLoans);
  test.afterEach(deleteLoans);

  test('a loan with a due date adds a Home Keeper task, and the link opens it', async ({ page }) => {
    const book = await bookByTitle(TITLE);
    const tab = await openTab(page, `/books/${book.id}`);
    await tab.locator('[data-k="lend"]').click();
    const dialog = tab.locator('.hkl-dialog');
    await expect(dialog.locator('h2')).toHaveText('Lend book');
    await dialog.locator('[name="party"]').fill(PARTY);
    await dialog.locator('[name="due"]').fill('2026-12-01');
    await expect(dialog.locator('[name="add_task"]')).toBeChecked();
    await dialog.locator('[data-k="d-submit"]').click();
    await expect(dialog).toHaveCount(0);

    const box = tab.locator('.hkl-box').filter({ has: page.locator('[data-act="return-loan"]') }).filter({ hasText: PARTY });
    await expect(box).toContainText(`${PARTY} · since`);
    const link = box.locator('a.hkl-task');
    await expect(link).toBeVisible({ timeout: 30_000 });

    const loan = (await adminState()).loans.find((l: { book_id: string; party: string }) => l.book_id === book.id && l.party === PARTY);
    expect(loan.hk_task_id).toMatch(/^[0-9a-f]{32}$|^[0-9a-f-]{36}$/);
    const task = (await homeKeeperTasks()).find((t) => t.id === loan.hk_task_id);
    expect(task).toMatchObject({ name: `Get ${TITLE} back from ${PARTY}` });
    await expect(link).toHaveAttribute('href', `/home-keeper/tasks/${loan.hk_task_id}`);

    await link.click();
    await expect(page).toHaveURL(new RegExp(`/home-keeper/tasks/${loan.hk_task_id}$`));
    // The Home Keeper panel (0.30.0) does not update its task list while a
    // companion tab is open, so a task that the library added shows only after a
    // load. Reported to Home Keeper; the reload keeps this test on the library side.
    await page.reload();
    await expect(page.locator('home-keeper-panel')).toContainText(`Get ${TITLE} back from ${PARTY}`, { timeout: 30_000 });
  });

  test('the Loans view lists the open loans and the borrowed books', async ({ page }) => {
    const tab = await openTab(page, '/loans');
    const state = await adminState();
    const out = state.loans.filter((l: { direction: string; returned: string | null }) => l.direction === 'out' && !l.returned);
    await expect(tab.locator('.hkl-listrow')).toHaveCount(out.length);
    await tab.locator('[data-k="lt-in"]').click();
    await expect(page).toHaveURL(/\/loans;tab=in$/);
    await expect(tab.locator('.hkl-listrow').filter({ hasText: 'Spinning Silver' })).toContainText('Seattle Public Library · Alex · Paperback · Reading');
  });
});
