import { test, expect } from '@playwright/test';
import { addItem, openCard, openPanel, trackPanelErrors } from './helpers';

test.describe('Home Keeper Library panel — smoke', () => {
  test('panel renders with title, add button, and no errors', async ({ page }) => {
    const errors = trackPanelErrors(page);
    await openPanel(page);
    const panel = page.locator('home-keeper-library-panel').first();
    await expect(panel.locator('.hkl-toolbar-title')).toContainText('Home Keeper Library');
    await expect(panel.locator('#add-btn')).toBeVisible();
    expect(errors, `panel errors:\n${errors.join('\n')}`).toHaveLength(0);
  });

  test('adding an item shows it in the list', async ({ page }) => {
    await openPanel(page);
    await addItem(page, 'Garage shelf', 7);
    const panel = page.locator('home-keeper-library-panel').first();
    await expect(panel.locator('.hkl-row', { hasText: 'Garage shelf' })).toBeVisible();
  });
});

test.describe('Home Keeper Library panel — deep linking & Back', () => {
  test('opening an item reflects in the URL', async ({ page }) => {
    await openPanel(page);
    await addItem(page, 'Link target', 1);
    const panel = page.locator('home-keeper-library-panel').first();
    await panel.locator('.detail-open', { hasText: 'Link target' }).first().click();
    await expect(panel.locator('#back-btn')).toBeVisible();
    await expect(page).toHaveURL(/\/home-keeper-library\/items\/.+$/);
  });

  test('browser Back returns to the list, not out of the panel', async ({ page }) => {
    await openPanel(page);
    await addItem(page, 'Back target', 2);
    const panel = page.locator('home-keeper-library-panel').first();
    await panel.locator('.detail-open', { hasText: 'Back target' }).first().click();
    await expect(panel.locator('#back-btn')).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/\/home-keeper-library(\/)?$/);
    await expect(panel.locator('#add-btn')).toBeVisible();
  });
});

test.describe('Home Keeper Library — dashboard card', () => {
  test('the custom card renders on the dashboard', async ({ page }) => {
    const card = await openCard(page);
    await expect(card.locator('ha-card').first()).toBeVisible();
  });
});
