import { defineConfig, devices } from '@playwright/test';
import { DESKTOP, PHONE } from './viewports';

/**
 * Playwright config for the Home Keeper Library browser tests.
 *
 * Drives a real Chromium against the Home Assistant Docker container with the real
 * Home Keeper (`bash ci/e2e-up.sh` starts it). global-setup completes onboarding as
 * Alex (an admin), adds Sam (a user who is not an admin) and Jo (a person with no
 * user), and writes a storage state for Alex and for Sam.
 *
 * ## 2 widths, 1 test body
 *
 * | tag           | runs in           |
 * | ------------- | ----------------- |
 * | *(none)*      | desktop only      |
 * | `@responsive` | desktop and phone |
 * | `@phone`      | phone only        |
 *
 * Every tag starts with `@`, because Playwright also matches `grep` against the
 * project name.
 */
const HA_URL = process.env.HA_URL || 'http://localhost:8123';

/**
 * The browser of every project. Not a phone device descriptor: those also set
 * `isMobile`, `hasTouch` and a scale factor, which `page.setViewportSize()` does
 * not change. The phone project sets the viewport only.
 */
const chromium = {
  ...devices['Desktop Chrome'],
  // The Playwright CDN is blocked in some sandboxes. CHROMIUM_EXEC points at a
  // Chromium that is installed already (unset in CI).
  ...(process.env.CHROMIUM_EXEC ? { launchOptions: { executablePath: process.env.CHROMIUM_EXEC } } : {}),
};

/** The desktop project, exported so the capture configs can pin it. */
export const DESKTOP_PROJECT = {
  name: 'desktop',
  use: { ...chromium, viewport: DESKTOP },
  grepInvert: /@phone/,
};

export default defineConfig({
  testDir: './tests',
  globalSetup: require.resolve('./global-setup'),
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: HA_URL,
    storageState: './.auth/state.json',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    DESKTOP_PROJECT,
    {
      name: 'phone',
      grep: /@responsive|@phone/,
      use: { ...chromium, viewport: PHONE },
    },
  ],
});
