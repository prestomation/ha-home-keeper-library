import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const FRONTEND = 'custom_components/home_keeper_library/frontend';

export default defineConfig({
  resolve: {
    alias: {
      // Rollup makes `panel-version` a virtual module. The tests use a stub.
      'panel-version': fileURLToPath(new URL(`./${FRONTEND}/test/panel-version-stub.js`, import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: [`${FRONTEND}/test/**/*.test.js`],
  },
});
