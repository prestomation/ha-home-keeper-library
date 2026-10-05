import type { PlaywrightTestConfig } from '@playwright/test';
import baseConfig, { DESKTOP_PROJECT } from './playwright.config';

/**
 * The config of a capture harness: 1 project (desktop). A spread of the base config
 * would pick up the phone project too, and both would write the same PNG paths. A
 * capture that wants the phone width sets it with `page.setViewportSize(PHONE)`.
 */
export function captureConfig(testMatch: string, extra: Partial<PlaywrightTestConfig> = {}): PlaywrightTestConfig {
  return {
    ...baseConfig,
    testDir: '.',
    testMatch,
    retries: 0,
    projects: [{ name: DESKTOP_PROJECT.name, use: DESKTOP_PROJECT.use }],
    ...extra,
    use: { ...baseConfig.use, ...extra.use },
  };
}
