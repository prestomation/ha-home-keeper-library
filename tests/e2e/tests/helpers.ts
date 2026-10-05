import { test as base, expect, type BrowserContext, type Locator, type Page } from '@playwright/test';
import { library, withWs } from '../ha-ws';

/**
 * Keep Home Assistant from installing its service worker.
 *
 * In a new browser context the worker takes control about 14 s after the first
 * load, and Home Assistant then reloads the page. A reload in the middle of a test
 * resets the tab. Playwright's `serviceWorkers: 'block'` removes
 * `navigator.serviceWorker`, which breaks the start of the Home Assistant frontend,
 * so the init script only makes `register` wait forever.
 */
export async function noServiceWorker(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    const sw = navigator.serviceWorker;
    if (sw) Object.defineProperty(sw, 'register', { value: () => new Promise(() => undefined) });
  });
}

/** The Playwright `test` with no Home Assistant service worker in each context. */
export const test = base.extend({
  context: async ({ context }, use) => {
    await noServiceWorker(context);
    await use(context);
  },
});

export { expect };

/** The panel URL of the Library tab in Home Keeper. */
export const TAB_URL = '/home-keeper/library';

/** The seeded dashboard with the card (tests/integration/ha_config). */
export const DASHBOARD_URL = '/home-keeper-library-e2e/library';

/** The tab element inside the Home Keeper panel. */
export function libraryTab(page: Page): Locator {
  return page.locator('home-keeper-panel home-keeper-library-tab');
}

/** Open a tab path (after `/home-keeper/library`) and wait for the library data. */
export async function openTab(page: Page, path = ''): Promise<Locator> {
  await page.goto(`${TAB_URL}${path}`, { waitUntil: 'domcontentloaded' });
  const tab = libraryTab(page);
  // `data-view` is set once the library data is there (the scan view has no nav row).
  await expect(tab.locator('#main[data-view]')).toBeVisible({ timeout: 45_000 });
  return tab;
}

/** Open the seeded dashboard and wait for the card to show its data. */
export async function openCard(page: Page): Promise<Locator> {
  await page.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded' });
  const card = page.locator('home-keeper-library-card');
  await expect(card.locator('.head h2')).toBeVisible({ timeout: 45_000 });
  return card;
}

/** The book with *title* in the library of Alex. */
export async function bookByTitle(title: string): Promise<Record<string, any>> {
  const state = await library<{ books: Array<Record<string, any>> }>('get_state');
  const book = state.books.find((b) => b.title === title);
  if (!book) throw new Error(`no book "${title}" in the seed`);
  return book;
}

/** The whole `get_state` reply as Alex. */
export function adminState(): Promise<Record<string, any>> {
  return library('get_state');
}

/** The whole `get_state` reply as Sam, who is not an admin. */
export function userState(): Promise<Record<string, any>> {
  return withWs('user', (ws) => ws.call({ type: 'home_keeper_library/get_state' }));
}

/** The Home Keeper tasks, as the library reads them. */
export async function homeKeeperTasks(): Promise<Array<Record<string, any>>> {
  return withWs('admin', async (ws) => {
    const res = await ws.call<{ response: { tasks: Array<Record<string, any>> } }>({
      type: 'call_service',
      domain: 'home_keeper',
      service: 'list_tasks',
      service_data: {},
      return_response: true,
    });
    return res.response.tasks;
  });
}

/** Set the reading row of a person back to what the seed had. */
export async function restoreReading(bookId: string, personId: string, row: Record<string, any> | undefined): Promise<void> {
  const fields = row
    ? {
        status: row.status,
        rating: row.rating,
        page: row.page,
        started: row.started,
        finished: row.finished,
        read_count: row.read_count,
      }
    : { status: 'want' };
  await library('set_reading', { book_id: bookId, person_id: personId, ...fields });
}

/** Collect the uncaught page errors and the console errors of the library code. */
export function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error' && /home[-_]keeper[-_]library|hkl-/i.test(msg.text())) errors.push(msg.text());
  });
  return errors;
}
