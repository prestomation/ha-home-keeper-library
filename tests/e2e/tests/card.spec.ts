import { expect, openCard, test, userState } from './helpers';

/**
 * The card on a dashboard for Sam, a user who is not an admin. The card shows the
 * reading of Sam, the shared reading of the household, and nothing private: the
 * backend projection leaves out the prices, the values and the loan parties.
 */
test.describe('Card for a user who is not an admin', { tag: '@responsive' }, () => {
  test.use({ storageState: './.auth/sam.json' });

  test('shows only the data of that person and no price', async ({ page }) => {
    const card = await openCard(page);
    await expect(card.locator('.head h2')).toHaveText('Library: Sam');
    await expect(card).toContainText('The Left Hand of Darkness');
    await expect(card).toContainText('Page 112 of 304');
    await expect(card).toContainText('Tomorrow, and Tomorrow, and Tomorrow');
    // The reading of Alex shows only as household activity, never as Sam's.
    await expect(card.locator('.sec').filter({ hasText: 'Reading' }).first()).not.toContainText('Project Hail Mary');
    await expect(card).toContainText('Alex: read Piranesi');
    await expect(card).not.toContainText('€');

    const state = await userState();
    expect(state.me).toMatchObject({ person_id: 'sam', is_admin: false });
    for (const copy of state.copies) {
      expect(copy).not.toHaveProperty('price');
      expect(copy).not.toHaveProperty('value');
      expect(copy).not.toHaveProperty('acquired_from');
    }
    for (const loan of state.loans) expect(loan).not.toHaveProperty('party');
    for (const book of state.books) {
      for (const [pid, row] of Object.entries(book.reading as Record<string, Record<string, unknown>>)) {
        if (pid !== 'sam') expect(row).not.toHaveProperty('private_notes');
      }
    }
  });

  test('the Home Keeper panel is not open to the user', async ({ page }) => {
    await page.goto('/home-keeper/library', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('home-keeper-library-tab')).toHaveCount(0);
  });
});
