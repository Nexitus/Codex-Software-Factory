import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const python = process.env.FACTORY_PYTHON || join(
  root,
  '.factory',
  'tools-venv',
  process.platform === 'win32' ? 'Scripts' : 'bin',
  process.platform === 'win32' ? 'python.exe' : 'python',
);
const database = join(mkdtempSync(join(tmpdir(), 'factory-console-e2e-')), 'demo.sqlite3');
const quote = (value: string) => process.platform === 'win32'
  ? `"${value.replaceAll('"', '""')}"`
  : `'${value.replaceAll("'", "'\\''")}'`;

export default defineConfig({
  testDir: './dashboard/e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  outputDir: '.factory/verification/playwright-results',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  projects: [
    { name: 'edge', use: { ...devices['Desktop Chrome'], channel: 'msedge' } },
  ],
  webServer: [
    {
      command: `${quote(python)} dashboard.py --demo --port 8765 --db ${quote(database)}`,
      cwd: root,
      url: 'http://127.0.0.1:8765/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: root,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
