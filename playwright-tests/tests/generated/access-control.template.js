import { test, expect } from '@playwright/test';

// Generated template: refine routes/selectors/env vars for your application.
test.describe('Access Control (Generated Template)', () => {
  const ADMIN_USER = process.env.ADMIN_USER;
  const ADMIN_PASS = process.env.ADMIN_PASS;
  const STANDARD_USER = process.env.STANDARD_USER;
  const STANDARD_PASS = process.env.STANDARD_PASS;
  const LOGIN_PATH = process.env.LOGIN_PATH || '/login';
  const ADMIN_BILLING_PATH = process.env.ADMIN_BILLING_PATH || '/admin/billing';
  const ADMIN_BILLING_API = process.env.ADMIN_BILLING_API || '/api/admin/billing-data';

  async function login(page, username, password) {
    await page.goto(LOGIN_PATH);
    await page.fill('[data-testid="username-input"], #username, input[name="username"]', username);
    await page.fill('[data-testid="password-input"], #password, input[name="password"]', password);
    await page.click('[data-testid="login-button"], button[type="submit"]');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(new RegExp(`${LOGIN_PATH}$`));
  }

  test.beforeEach(async ({ page }) => {
    test.skip(
      !ADMIN_USER || !ADMIN_PASS || !STANDARD_USER || !STANDARD_PASS,
      'Set ADMIN_USER, ADMIN_PASS, STANDARD_USER, STANDARD_PASS to run access-control specs.'
    );
    await page.goto(LOGIN_PATH);
  });

  test('Admin users can access /admin/billing and see invoice controls', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);

    const response = await page.goto(ADMIN_BILLING_PATH);
    expect(response?.status()).toBeLessThan(400);
    await expect(page).toHaveURL(new RegExp(`${ADMIN_BILLING_PATH}$`));
    await expect(
      page.locator('[data-testid="invoice-controls"], [data-testid="billing-page-title"], h1:has-text("Billing")')
    ).toBeVisible();
  });

  test('Standard users receive 403 when accessing /admin/billing (UI)', async ({ page }) => {
    await login(page, STANDARD_USER, STANDARD_PASS);

    const response = await page.goto(ADMIN_BILLING_PATH);
    const blockedByStatus = response && [401, 403].includes(response.status());
    const blockedByUi = await page
      .locator('[data-testid="access-denied-message"], text=/access denied|forbidden/i')
      .isVisible()
      .catch(() => false);
    const redirectedAway = !new RegExp(`${ADMIN_BILLING_PATH}$`).test(page.url());

    expect(blockedByStatus || blockedByUi || redirectedAway).toBeTruthy();
  });

  test('Standard users receive 403 when accessing /admin/billing (API)', async ({ page }) => {
    await login(page, STANDARD_USER, STANDARD_PASS);
    const protectedApiResponse = await page.request.get(ADMIN_BILLING_API);
    expect([401, 403]).toContain(protectedApiResponse.status());
  });

  test('Unauthenticated users are redirected to /login when accessing protected billing routes', async ({ browser }) => {
    const unauthContext = await browser.newContext();
    const unauthPage = await unauthContext.newPage();
    const response = await unauthPage.goto(ADMIN_BILLING_PATH);
    const redirectedToLogin = new RegExp(`${LOGIN_PATH}$`).test(unauthPage.url());
    const blockedByStatus = response && [401, 403].includes(response.status());
    expect(redirectedToLogin || blockedByStatus).toBeTruthy();
    await unauthContext.close();
  });
});
