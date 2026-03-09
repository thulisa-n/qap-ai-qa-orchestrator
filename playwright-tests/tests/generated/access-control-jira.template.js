import { test, expect } from '@playwright/test';

// Generated template from Jira-triggered flow. Refine selectors/routes for your app.
// Not intended as a demo-site runnable spec.
async function login(page, username, password) {
  await page.goto('/login');
  await expect(page).toHaveURL(/.*\/login/);
  await page.fill('data-testid=username-input', username);
  await page.fill('data-testid=password-input', password);
  await page.click('data-testid=login-button');
  await page.waitForURL('/');
  await expect(page).toHaveURL(/.*\/$/);
}

test.describe('Access Control for /admin/billing (Generated Template)', () => {
  test('Admin users can access /admin/billing', async ({ page }) => {
    test.skip(
      !process.env.TEST_ADMIN_USER || !process.env.TEST_ADMIN_PASS,
      'TEST_ADMIN_USER and TEST_ADMIN_PASS must be set for admin tests'
    );

    await test.step('Login as Admin', async () => {
      await login(page, process.env.TEST_ADMIN_USER, process.env.TEST_ADMIN_PASS);
    });

    await test.step('Navigate to /admin/billing and verify access', async () => {
      await page.goto('/admin/billing');
      await expect(page).toHaveURL(/.*\/admin\/billing/);
      await expect(page.locator('data-testid=billing-dashboard')).toBeVisible();
      await expect(page.locator('data-testid=billing-dashboard-title')).toHaveText(
        'Billing Dashboard'
      );
    });
  });

  test('Standard users receive 403 on /admin/billing', async ({ page, request }) => {
    test.skip(
      !process.env.TEST_USER || !process.env.TEST_PASS,
      'TEST_USER and TEST_PASS must be set for standard user tests'
    );

    await test.step('Login as Standard User', async () => {
      await login(page, process.env.TEST_USER, process.env.TEST_PASS);
    });

    await test.step('Attempt to access /admin/billing and verify 403', async () => {
      const response = await request.get('/admin/billing');
      expect(response.status()).toBe(403);
    });
  });

  test('Unauthenticated users are redirected to /login for billing routes', async ({ page }) => {
    await test.step('Attempt to access /admin/billing while unauthenticated', async () => {
      await page.goto('/admin/billing');
      await expect(page).toHaveURL(/.*\/login/);
      await expect(page.locator('data-testid=login-form')).toBeVisible();
      await expect(page.locator('data-testid=username-input')).toBeVisible();
    });
  });
});
