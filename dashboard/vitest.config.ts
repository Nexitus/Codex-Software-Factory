import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['dashboard/src/**/*.test.ts'],
  },
});
