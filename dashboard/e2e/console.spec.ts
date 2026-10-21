import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const screenshots = join(process.cwd(), '.factory', 'verification');
const diagnostics = new WeakMap<Page, { consoleErrors: string[]; consoleWarnings: string[]; pageErrors: string[]; failedRequests: string[]; httpErrors: string[] }>();

async function assertNoViewportOverflow(page: Page) {
  const widths = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
  expect(widths.document, JSON.stringify(widths)).toBeLessThanOrEqual(widths.viewport);
  expect(widths.body, JSON.stringify(widths)).toBeLessThanOrEqual(widths.viewport);
}

async function emptyLaneContrast(page: Page) {
  return page.locator('.empty-lane').first().evaluate((node) => {
    const luminance = (color: string) => {
      const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? [0, 0, 0];
      const linear = channels.map((channel) => {
        const value = channel / 255;
        return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    };
    const column = node.closest('.board-column');
    if (!column) return 0;
    const foreground = luminance(getComputedStyle(node).color);
    const background = luminance(getComputedStyle(column).backgroundColor);
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
}

test.beforeAll(async () => {
  await mkdir(screenshots, { recursive: true });
});

test.beforeEach(async ({ page }) => {
  const counts = { consoleErrors: [] as string[], consoleWarnings: [] as string[], pageErrors: [] as string[], failedRequests: [] as string[], httpErrors: [] as string[] };
  diagnostics.set(page, counts);
  page.on('console', (message) => {
    if (message.type() === 'error') counts.consoleErrors.push(message.text().slice(0, 300));
    if (message.type() === 'warning') counts.consoleWarnings.push(message.text().slice(0, 300));
  });
  page.on('pageerror', (error) => { counts.pageErrors.push(error.message.slice(0, 300)); });
  page.on('requestfailed', (request) => {
    if (!request.failure()?.errorText.includes('ERR_ABORTED')) counts.failedRequests.push(new URL(request.url()).pathname + ': ' + (request.failure()?.errorText || 'failed'));
  });
  page.on('response', (response) => {
    if (response.status() >= 400) counts.httpErrors.push(new URL(response.url()).pathname + ': ' + response.status());
  });
});

test.afterEach(async ({ page }) => {
  const result = diagnostics.get(page);
  expect(result?.consoleErrors ?? [], 'browser console errors').toEqual([]);
  expect(result?.consoleWarnings ?? [], 'browser console warnings').toEqual([]);
  expect(result?.pageErrors ?? [], 'uncaught browser errors').toEqual([]);
  expect(result?.failedRequests ?? [], 'unexpected failed network requests').toEqual([]);
  expect(result?.httpErrors ?? [], 'unexpected HTTP error responses').toEqual([]);
});

test('worst-case board data stays readable, keyboard operable, and detail evidence is complete', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.context().route('**/api/runs/**/artifacts**', async (route) => {
    const requestUrl = new URL(route.request().url());
    const artifactPath = requestUrl.searchParams.get('path');
    const blockedReport = artifactPath === 'ERROR.json';
    expect(artifactPath).toBe(blockedReport ? 'ERROR.json' : 'dashboard/dist/artifacts/very-long-review-evidence-for-a-verified-factory-run-round-two.json');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ path: artifactPath, content: { status: blockedReport ? 'blocked' : 'verified_candidate', synthetic: true } }),
    });
  });
  await page.goto('/?data=worst');
  await expect(page.getByRole('heading', { name: 'Software factory' })).toBeVisible();
  await expect(page.getByText('Demo mode')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Blocked', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Interrupted — recovery required/ }).first()).toBeVisible();
  await expect(page.getByText('timed_out').first()).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Jump to run stage' }).getByRole('button', { name: 'Jump to Ready, 1 run' })).toBeVisible();
  await page.screenshot({ path: join(screenshots, 'dashboard-desktop.png'), fullPage: true });
  expect(await emptyLaneContrast(page)).toBeGreaterThanOrEqual(4.5);
  await page.getByRole('button', { name: 'Switch to light theme' }).click();
  expect(await emptyLaneContrast(page)).toBeGreaterThanOrEqual(4.5);
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();

  const board = page.getByRole('region', { name: /Run stages/ });
  await board.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => board.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);

  const blockedCard = page.getByRole('button', { name: /9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f/ });
  await blockedCard.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Requirement' })).toBeVisible();
  const requirement = dialog.locator('[aria-label="Requirement"] p');
  await expect.poll(() => requirement.evaluate((node) => node.textContent?.length)).toBe(20_000);
  await expect(dialog.getByText('Interrupted — recovery required').first()).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Design guidance' })).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Round and repair history' })).toBeVisible();
  await expect(dialog.getByText('recovery required', { exact: false }).first()).toBeVisible();
  const blockedReportLink = dialog.getByRole('link', { name: 'Open artifact ERROR.json' });
  const blockedReportPopupPromise = page.waitForEvent('popup');
  await blockedReportLink.click();
  const blockedReportPopup = await blockedReportPopupPromise;
  await expect(blockedReportPopup.locator('body')).toContainText('blocked');
  await blockedReportPopup.close();
  await dialog.screenshot({ path: join(screenshots, 'run-detail-worst-case.png') });
  await dialog.getByRole('heading', { name: 'Round and repair history' }).scrollIntoViewIfNeeded();
  await dialog.screenshot({ path: join(screenshots, 'run-history-worst-case.png') });

  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(blockedCard).toBeFocused();

  const verifiedCard = page.getByRole('button', { name: /04ac5544-6062-42ed-b610-bc8f4beec9ae/ });
  await verifiedCard.click();
  await expect(dialog.getByText('Verified candidate', { exact: true }).first()).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Design guidance' })).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Verification gates' })).toBeVisible();
  await dialog.screenshot({ path: join(screenshots, 'run-detail.png') });
  const artifactLink = dialog.getByRole('link', { name: /Open artifact/ });
  await expect(artifactLink).toHaveAttribute('target', '_blank');
  await expect(artifactLink).toHaveAttribute('rel', 'noopener noreferrer');
  const artifactPopupPromise = page.waitForEvent('popup');
  await artifactLink.click();
  const artifactPopup = await artifactPopupPromise;
  await expect(artifactPopup.locator('body')).toContainText('verified_candidate');
  await expect(artifactPopup.locator('body')).toContainText('synthetic');
  await artifactPopup.close();
  await dialog.getByRole('heading', { name: 'Round and repair history' }).scrollIntoViewIfNeeded();
  await expect(dialog.getByText('repair requested', { exact: false }).first()).toBeVisible();
  await dialog.screenshot({ path: join(screenshots, 'run-history.png') });
  await page.keyboard.press('Escape');
  await expect(verifiedCard).toBeFocused();
});

test('empty, one-row, large, and error fixtures announce their actual states', async ({ page }) => {
  await page.goto('/?data=empty');
  await expect(page.getByText('No runs in this stage').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Jump to Queue, 0 runs' })).toBeVisible();

  await page.goto('/?data=one');
  await expect(page.locator('[data-run-id]')).toHaveCount(1);
  await page.locator('[data-run-id]').first().click();
  await expect(page.getByText('Agent details are not reported.')).toBeVisible();
  await page.keyboard.press('Escape');

  await page.goto('/?data=many');
  await expect(page.getByRole('button', { name: 'Jump to Queue, 125 runs' })).toBeVisible();
  await expect(page.locator('[data-run-id]')).toHaveCount(1000);

  await page.goto('/?data=error');
  await expect(page.getByRole('alert').filter({ hasText: '503' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry loading runs' })).toBeVisible();
});

test('dev API proxy preserves missing Origin and rejects foreign Origin', async ({ page }) => {
  await page.goto('/');
  const payload = { requirement: 'Origin validation probe', project_id: 'not-used' };

  const foreignOrigin = await page.request.post('/api/runs', {
    headers: { Origin: 'http://attacker.invalid', 'Content-Type': 'application/json' },
    data: payload,
  });
  expect(foreignOrigin.status()).toBe(403);

  const missingOrigin = await page.request.post('/api/runs', {
    headers: { 'Content-Type': 'application/json' },
    data: payload,
  });
  expect(missingOrigin.status()).toBe(403);
});

test('elapsed time advances between silent events and freezes at terminal server duration', async ({ page }) => {
  await page.goto('/?data=worst');
  const runningRun = page.locator('[data-run-id="80f8e9b8-4147-4db1-bcd7-b18d0a287c6e"]');
  const runningElapsed = runningRun.getByTestId('elapsed-time');
  await expect(runningElapsed).toHaveText('1m 5s');
  const initialElapsed = await runningElapsed.innerText();
  await expect.poll(() => runningElapsed.innerText(), { timeout: 4_000 }).not.toBe(initialElapsed);
  await expect(runningRun).toContainText('Running');

  const terminalElapsed = page.locator('[data-run-id="04ac5544-6062-42ed-b610-bc8f4beec9ae"]').getByTestId('elapsed-time');
  const terminalDuration = await terminalElapsed.innerText();
  await page.waitForTimeout(1_500);
  await expect(terminalElapsed).toHaveText(terminalDuration);
});

test('mobile layouts keep the page in the viewport and the detail drawer usable at 320px and 390px', async ({ page }) => {
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/?data=worst');
    await expect(page.getByRole('heading', { name: 'Software factory' })).toBeVisible();
    await assertNoViewportOverflow(page);
    await page.screenshot({ path: join(screenshots, width === 390 ? 'dashboard-mobile.png' : 'dashboard-320.png'), fullPage: true });

    const card = page.getByRole('button', { name: /9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f/ });
    await card.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Requirement' })).toBeVisible();
    await assertNoViewportOverflow(page);
    await dialog.screenshot({ path: join(screenshots, width === 390 ? 'run-detail-mobile.png' : 'run-detail-320.png') });
    await page.keyboard.press('Escape');
  }
});

test('demo intake persists repair history and keeps blocked outcome red', async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');

  await page.getByRole('button', { name: 'New task' }).click();
  await page.getByLabel('Requirement').fill('Verify that the dashboard records a passing demo run after repair.');
  await page.getByLabel('Demo outcome').selectOption('ready');
  await page.getByRole('button', { name: 'Create task' }).click();

  let dialog = page.getByRole('dialog');
  await expect(dialog.getByText(/Verified candidate|Delivery report unavailable|Delivery report mismatch/).first()).toBeVisible({ timeout: 90_000 });
  await expect(dialog.getByText('repair requested', { exact: false }).first()).toBeVisible({ timeout: 90_000 });
  await expect(dialog.getByText('delivery verified', { exact: false }).first()).toBeVisible();
  await dialog.screenshot({ path: join(screenshots, 'integrated-ready-detail.png') });
  await dialog.getByRole('heading', { name: 'Round and repair history' }).scrollIntoViewIfNeeded();
  await dialog.screenshot({ path: join(screenshots, 'integrated-ready-history.png') });
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'New task' }).click();
  await page.getByLabel('Requirement').fill('Verify that a blocked demo run keeps the blocked state visible.');
  await page.getByLabel('Demo outcome').selectOption('blocked');
  await page.getByRole('button', { name: 'Create task' }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog.getByText('Blocked delivery', { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await expect(dialog.getByText('Verified candidate', { exact: true })).toHaveCount(0);
});
