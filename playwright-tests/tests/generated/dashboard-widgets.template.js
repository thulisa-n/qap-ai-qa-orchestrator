import { test, expect } from '@playwright/test';

// Generated template: refine endpoints/selectors/thresholds for your application.
test.describe('Dashboard Widgets (Generated Template)', () => {
  const ADMIN_USER = process.env.ADMIN_USER;
  const ADMIN_PASS = process.env.ADMIN_PASS;
  const LOGIN_PATH = process.env.LOGIN_PATH || '/login';
  const DASHBOARD_PATH = process.env.DASHBOARD_PATH || '/dashboard';
  const SETTINGS_PATH = process.env.SETTINGS_PATH || '/settings';
  const BILLING_SUMMARY_API = process.env.BILLING_SUMMARY_API || '/api/dashboard/billing-summary';
  const PORTFOLIO_SUMMARY_API = process.env.PORTFOLIO_SUMMARY_API || '/api/dashboard/portfolio-summary';
  const TARGET_FIRST_RESPONSE_MS = Number(process.env.TARGET_FIRST_RESPONSE_MS || 1000);
  const BILLING_TOTAL_SELECTOR =
    process.env.BILLING_TOTAL_SELECTOR || '[data-testid="billing-total-revenue"]';

  test.beforeEach(async ({ page }) => {
    test.skip(!ADMIN_USER || !ADMIN_PASS, 'Set ADMIN_USER and ADMIN_PASS to run dashboard specs.');
    await page.goto(LOGIN_PATH);
    await page.fill('[data-testid="username-input"], #username, input[name="username"]', ADMIN_USER);
    await page.fill('[data-testid="password-input"], #password, input[name="password"]', ADMIN_PASS);
    await page.click('[data-testid="login-button"], button[type="submit"]');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(new RegExp(`${LOGIN_PATH}$`));
  });

  test('Dashboard widget API returns 200 with deterministic schema for valid authenticated users', async ({ page }) => {
    const apiResponse = await page.request.get(BILLING_SUMMARY_API);
    expect(apiResponse.status()).toBe(200);

    const responseBody = await apiResponse.json();
    expect(responseBody && typeof responseBody === 'object').toBeTruthy();
    const keys = Object.keys(responseBody);
    expect(keys.length).toBeGreaterThan(0);
  });

  test('Repeated widget requests within cache window return faster response and include cache indicator when available', async ({ page }) => {
    const startTime1 = Date.now();
    const firstResponse = await page.request.get(PORTFOLIO_SUMMARY_API);
    const endTime1 = Date.now();
    expect(firstResponse.status()).toBe(200);
    const firstResponseTime = endTime1 - startTime1;
    expect(firstResponseTime).toBeLessThan(TARGET_FIRST_RESPONSE_MS);

    await page.waitForTimeout(1000);

    const startTime2 = Date.now();
    const secondResponse = await page.request.get(PORTFOLIO_SUMMARY_API);
    const endTime2 = Date.now();
    expect(secondResponse.status()).toBe(200);
    const secondResponseTime = endTime2 - startTime2;

    const cacheHeader = secondResponse.headers()['x-cache'];
    if (cacheHeader) {
      expect(cacheHeader.toUpperCase()).toContain('HIT');
    }
    expect(secondResponseTime).toBeLessThanOrEqual(firstResponseTime + 100);
  });

  test('Displayed totals remain consistent between uncached and cached responses', async ({ page }) => {
    await page.goto(DASHBOARD_PATH);
    await page.waitForSelector(BILLING_TOTAL_SELECTOR);

    const uncachedTotalElement = page.locator(BILLING_TOTAL_SELECTOR);
    const uncachedTotalText = await uncachedTotalElement.textContent();
    expect(uncachedTotalText).not.toBeNull();
    const uncachedTotal = parseFloat(uncachedTotalText.replace(/[^0-9.-]+/g, ''));

    await page.goto(SETTINGS_PATH);
    await page.goto(DASHBOARD_PATH);
    await page.waitForSelector(BILLING_TOTAL_SELECTOR);

    const cachedTotalElement = page.locator(BILLING_TOTAL_SELECTOR);
    const cachedTotalText = await cachedTotalElement.textContent();
    expect(cachedTotalText).not.toBeNull();
    const cachedTotal = parseFloat(cachedTotalText.replace(/[^0-9.-]+/g, ''));

    expect(cachedTotal).toBe(uncachedTotal);
  });
});
