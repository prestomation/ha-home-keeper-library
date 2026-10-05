/**
 * The 2 widths that the tab and the card are tested and shown at.
 *
 * A leaf module, as in Home Keeper: `playwright.config.ts` builds its projects
 * from it, the specs import it as `../viewports`, and the capture harnesses as
 * `./viewports`. It is the only place that writes a width.
 */
export type Viewport = { width: number; height: number };

/** A phone. Below the 700px breakpoint of the tab, the phone layout applies. */
export const PHONE: Viewport = { width: 390, height: 844 };

/** What `devices['Desktop Chrome']` gives the default project. */
export const DESKTOP: Viewport = { width: 1280, height: 720 };
