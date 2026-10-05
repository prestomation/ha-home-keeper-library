import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: [
      'custom_components/home_keeper_library/frontend/test/**/*.test.js',
    ],
  },
});
