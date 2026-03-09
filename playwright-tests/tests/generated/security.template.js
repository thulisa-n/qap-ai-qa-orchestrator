import { test, expect } from '@playwright/test';

// Generated template: tune error endpoint and leak signatures to your stack.
test.describe('Security (Generated Template)', () => {
  const ADMIN_USER = process.env.ADMIN_USER;
  const ADMIN_PASS = process.env.ADMIN_PASS;
  const LOGIN_PATH = process.env.LOGIN_PATH || '/login';
  const ERROR_ENDPOINT = process.env.SECURITY_ERROR_ENDPOINT || '/api/non-existent-resource-12345';

  test.beforeEach(async ({ page }) => {
    test.skip(!ADMIN_USER || !ADMIN_PASS, 'Set ADMIN_USER and ADMIN_PASS to run security specs.');

    await page.goto(LOGIN_PATH);
    await page.fill('[data-testid="username-input"], #username, input[name="username"]', ADMIN_USER);
    await page.fill('[data-testid="password-input"], #password, input[name="password"]', ADMIN_PASS);
    await page.click('[data-testid="login-button"], button[type="submit"]');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(new RegExp(`${LOGIN_PATH}$`));
  });

  test('Error responses do not expose internal stack traces or sensitive fields', async ({ page }) => {
    const errorResponse = await page.request.get(ERROR_ENDPOINT);
    expect(errorResponse.status()).toBeGreaterThanOrEqual(400);

    const responseBody = await errorResponse.text();
    const bodyLower = responseBody.toLowerCase();

    const forbiddenMarkers = [
      'traceback (most recent call last)',
      'stack trace',
      'internaldetails',
      'db_connection_string',
      'api_key',
      'secret',
      'exception at',
    ];
    for (const marker of forbiddenMarkers) {
      expect(bodyLower).not.toContain(marker);
    }

    try {
      const jsonBody = JSON.parse(responseBody);
      expect(jsonBody).not.toHaveProperty('stackTrace');
      expect(jsonBody).not.toHaveProperty('internalDetails');
      expect(jsonBody).not.toHaveProperty('sensitiveData');
    } catch (_err) {
      // Plain text/HTML error body is acceptable if no sensitive markers are leaked.
    }
  });
});
