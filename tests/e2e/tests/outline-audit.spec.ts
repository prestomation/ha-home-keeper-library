import type { Page } from '@playwright/test';
import { auditOutlines } from '../outline-audit';
import { library } from '../ha-ws';
import { adminState, bookByTitle, DASHBOARD_URL, expect, libraryTab, openTab, test } from './helpers';

/**
 * Every outline is whole.
 *
 * A border, a ring or an outline of a control must show all of it, on every view, at the
 * desktop and the phone width. `outline-audit.ts` finds a control that an ancestor clips,
 * and a border with a gap. Each view below is opened by a URL and a few clicks, then
 * audited. A view that fails names the control and the box that cuts it.
 *
 * This spec and `outline-audit.ts` come from Home Keeper. Add the view to `VIEWS` when you
 * add a surface that has bordered controls, and each dialog that the tab shows. A control
 * that is cut on purpose carries `data-hkl-cut`.
 */
type View = {
  name: string;
  /** A tab path, or a page URL if it starts with `/home-keeper-library-e2e`. */
  url: string;
  /** Open a dialog or a state. */
  before?: (page: Page) => Promise<void>;
  /** Put back what `before` changed. */
  after?: (page: Page) => Promise<void>;
};

const tabOf = libraryTab;
const scrim = (page: Page) => tabOf(page).locator('.hkl-confirm-scrim');
/** Escape closes a confirmation and changes no data. */
const closeConfirm = async (page: Page): Promise<void> => {
  await page.keyboard.press('Escape');
  await expect(scrim(page)).toHaveCount(0);
};
const confirmOpen = async (page: Page): Promise<void> => {
  await expect(scrim(page)).toBeVisible();
  await expect(scrim(page).locator('[data-k="confirm-cancel"]')).toBeVisible();
};

async function seededBook(): Promise<string> {
  return (await bookByTitle('The Left Hand of Darkness')).id as string;
}

const VIEWS: View[] = [
  { name: 'Books', url: '/books' },
  { name: 'Shelves', url: '/shelves' },
  { name: 'Loans', url: '/loans' },
  { name: 'Loans, returned', url: '/loans;tab=returned' },
  { name: 'Wishlist', url: '/wishlist' },
  { name: 'Settings', url: '/settings' },
  { name: 'Scan', url: '/scan' },
  {
    name: 'Import',
    url: '/import',
    before: async (page) => {
      await expect(tabOf(page).locator('.hkl-dialog')).toBeVisible();
    },
  },
  {
    name: 'Book page',
    url: `/books/${'__BOOK__'}`,
    before: async (page) => {
      await expect(tabOf(page).locator('[data-k="delete-book"]')).toBeVisible();
    },
  },
  {
    name: 'Book page, delete confirmation',
    url: `/books/${'__BOOK__'}`,
    before: async (page) => {
      await tabOf(page).locator('[data-k="delete-book"]').click();
      await confirmOpen(page);
      await expect(scrim(page).locator('p')).toContainText('Copies: ');
    },
    after: closeConfirm,
  },
  {
    name: 'Book page, delete copy confirmation',
    url: `/books/${'__BOOK__'}`,
    before: async (page) => {
      await tabOf(page).locator('[data-act="delete-copy"]').first().click();
      await confirmOpen(page);
    },
    after: closeConfirm,
  },
  {
    name: 'Shelves, delete shelf confirmation',
    url: '/shelves',
    before: async (page) => {
      await tabOf(page).locator('[data-act="delete-shelf"]').first().click();
      await confirmOpen(page);
    },
    after: closeConfirm,
  },
  {
    name: 'Shelves, delete bookcase confirmation',
    url: '/shelves',
    before: async (page) => {
      await tabOf(page).locator('[data-act="delete-bookcase"]').first().click();
      await confirmOpen(page);
    },
    after: closeConfirm,
  },
  {
    name: 'Shelves, delete room confirmation',
    url: '/shelves',
    before: async (page) => {
      await tabOf(page).locator('[data-act="delete-room"]').first().click();
      await confirmOpen(page);
      await expect(scrim(page).locator('p')).toContainText('Bookcases: ');
    },
    after: closeConfirm,
  },
  {
    name: 'Loans, delete confirmation',
    url: '/loans;tab=returned',
    before: async (page) => {
      await tabOf(page).locator('[data-act="delete-loan"]').first().click();
      await confirmOpen(page);
    },
    after: closeConfirm,
  },
  {
    name: 'Wishlist, remove confirmation',
    url: '/wishlist',
    before: async (page) => {
      await tabOf(page).locator('[data-act="wish-remove"]').first().click();
      await confirmOpen(page);
    },
    after: closeConfirm,
  },
  {
    name: 'Add book dialog',
    url: '/books',
    before: async (page) => {
      await tabOf(page).locator('[data-act="add-book"]').first().click();
      await expect(tabOf(page).locator('.hkl-dialog')).toBeVisible();
    },
    after: async (page) => {
      await page.keyboard.press('Escape');
    },
  },
  { name: 'Card', url: `${DASHBOARD_URL}` },
];

test.describe('Library — outlines are whole', () => {
  for (const view of VIEWS) {
    test(`${view.name} @responsive`, async ({ page }) => {
      const url = view.url.replace('__BOOK__', await seededBook());
      if (url.startsWith('/home-keeper-library-e2e')) {
        await page.goto(url, { waitUntil: 'domcontentloaded' });
        await expect(page.locator('home-keeper-library-card .head h2')).toBeVisible({ timeout: 45_000 });
      } else {
        await openTab(page, url);
      }
      try {
        if (view.before) await view.before(page);
        expect(await auditOutlines(page), 'controls with a cut or open outline').toEqual([]);
      } finally {
        if (view.after) await view.after(page);
      }
    });
  }

  test('the seed has what the views open', async () => {
    const state = await adminState();
    expect(state.loans.some((l: { returned: string | null }) => l.returned)).toBe(true);
    expect(state.books.some((b: { wishlist: unknown }) => b.wishlist)).toBe(true);
    expect(await library('get_state')).toBeTruthy();
  });
});
