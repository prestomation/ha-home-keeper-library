import { defineConfig, mergeConfig } from 'vitest/config';

import baseConfig from './vitest.config.js';

// Vitest config used only by Stryker (see stryker.conf.json).
//
// It is the normal config minus 3 kinds of test file:
//
// - `*-parity.test.js` reads `src/*.ts` as text. Inside the Stryker sandbox it
//   reads mutated source, so a mutant that changes a string literal turns it red
//   and counts as killed by a test that did not run the behaviour.
// - `*-dom.test.js` mounts the whole tab or card. It runs a large part of
//   `utils.ts` for each mutant, which makes a run take hours, and the unit tests
//   are the stricter measure of the pure module.
// - `tests/frontend/` tests the scripts of the docs site, which no mutant changes.
//
// `ci/test-frontend.sh` still runs all 3 kinds on every PR.
export default mergeConfig(
  baseConfig,
  defineConfig({
    test: {
      exclude: ['**/node_modules/**', '**/*-parity.test.js', '**/*-dom.test.js', 'tests/frontend/**'],
    },
  }),
);
