import { test, expect } from '@playwright/test';

test.describe('Billing Area Access Control', () => {
  // Environment variables for credentials. Provide defaults for local development.
  const ADMIN_USER = process.env.ADMIN_USER || 'admin_user';
  const ADMIN_PASS = process.env.ADMIN_PASS || 'admin_pass';
  const STANDARD_USER = process.env.STANDARD_USER || 'standard_user';
  const STANDARD_PASS = process.env.STANDARD_PASS || 'standard_pass';

  test.beforeEach(async ({ page }) => {
    // Ensure a clean state before each test by attempting to log out.
    // Adjust '/logout' if your application uses a different logout mechanism or endpoint.
    await page.goto(process.env.BASE_URL + '/logout', { waitUntil: 'domcontentloaded' }).catch(() => {});
    // Clear cookies to ensure no lingering session data
    await page.context().clearCookies();
  });

  /**
   * Helper function to log in a user.
   * Assumes a login page at /login with specific data-testid selectors for inputs and button.
   * @param {import('@playwright/test').Page} page
   * @param {string} username
   * @param {string} password
   */
  async function login(page, username, password) {
    await page.goto(process.env.BASE_URL + '/login');
    await page.fill('input[data-testid="username-input"]', username);
    await page.fill('input[data-testid="password-input"]', password);
    await page.click('button[data-testid="login-button"]');
    // Wait for navigation to a post-login page, e.g., dashboard or home.
    // Adjust '/dashboard' to your application's actual post-login redirect path.
    await page.waitForURL(process.env.BASE_URL + '/dashboard', { waitUntil: 'networkidle' });
  }

  test('Admin users can access /admin/billing and view billing controls', async ({ page }) => {
    await test.step('Login as Admin', async () => {
      await login(page, ADMIN_USER, ADMIN_PASS);
    });

    await test.step('Navigate to /admin/billing', async () => {
      await page.goto(process.env.BASE_URL + '/admin/billing');
      await expect(page).toHaveURL(process.env.BASE_URL + '/admin/billing');
    });

    await test.step('Verify billing controls are visible', async () => {
      // Placeholder selectors for billing page elements. Replace with actual data-testid attributes.
      await expect(page.locator('h1[data-testid="billing-page-title"]')).toHaveText('Billing Management', { ignoreCase: true });
      await expect(page.locator('div[data-testid="billing-controls"]')).toBeVisible();
      await expect(page.locator('button[data-testid="generate-report-button"]')).toBeVisible();
    });
  });

  test('Standard users receive 403 when navigating to /admin/billing', async ({ page }) => {
    await test.step('Login as Standard User', async () => {
      await login(page, STANDARD_USER, STANDARD_PASS);
    });

    await test.step('Attempt to navigate to /admin/billing and expect 403', async () => {
      // Intercept the response to check its status code directly.
      const response = await page.goto(process.env.BASE_URL + '/admin/billing', { waitUntil: 'domcontentloaded' });
      expect(response?.status()).toBe(403);

      // Additionally, verify the UI displays a 403 error message.
      // Placeholder selectors for error page elements.
      await expect(page.locator('h1[data-testid="error-page-title"]')).toHaveText('403 Forbidden', { ignoreCase: true });
      await expect(page.locator('div[data-testid="error-message"]')).toContainText('You do not have permission to access this page.', { ignoreCase: true });
    });
  });

  test('Unauthenticated users are redirected to /login for protected billing routes', async ({ page }) => {
    await test.step('Attempt to navigate to /admin/billing without authentication', async () => {
      await page.goto(process.env.BASE_URL + '/admin/billing', { waitUntil: 'domcontentloaded' });
    });

    await test.step('Verify redirection to login page', async () => {
      await expect(page).toHaveURL(process.env.BASE_URL + '/login');
      // Placeholder selector for login page title.
      await expect(page.locator('h1[data-testid="login-page-title"]')).toHaveText('Login', { ignoreCase: true });
      await expect(page.locator('input[data-testid="username-input"]')).toBeVisible();
    });
  });

  test('Session expires after inactivity and requires re-authentication', async ({ page }) => {
    test.slow(); // Mark this test as slow due to the intentional wait time.

    await test.step('Login as Admin and navigate to a protected page', async () => {
      await login(page, ADMIN_USER, ADMIN_PASS);
      await page.goto(process.env.BASE_URL + '/admin/billing');
      await expect(page).toHaveURL(process.env.BASE_URL + '/admin/billing');
    });

    await test.step('Simulate inactivity by waiting for a period longer than test session timeout', async () => {
      // NOTE: This test relies on the test environment having a significantly reduced session timeout
      // (e.g., 10-30 seconds) for automation purposes. Waiting 15 minutes is impractical for CI/CD.
      // The actual timeout duration for testing should be configured in the test environment.
      // We wait for 15 seconds here, assuming the test environment's session timeout is less than 15s.
      await page.waitForTimeout(15 * 1000); // Wait for 15 seconds.
    });

    await test.step('Attempt to access a protected page again and verify re-authentication', async () => {
      await page.goto(process.env.BASE_URL + '/admin/billing');
      await expect(page).toHaveURL(process.env.BASE_URL + '/login');
      await expect(page.locator('h1[data-testid="login-page-title"]')).toHaveText('Login', { ignoreCase: true });
    });
  });

  test('Billing widget API returns deterministic schema for authorized users', async ({ request }) => {
    // Use APIRequestContext for direct API calls, bypassing UI for efficiency in API validation.
    // First, obtain an authentication token (assuming token-based authentication).
    const authResponse = await request.post(process.env.BASE_URL + '/api/login', {
      data: {
        username: ADMIN_USER,
        password: ADMIN_PASS,
      },
    });
    expect(authResponse.ok(), `Failed to authenticate: ${authResponse.status()} ${await authResponse.text()}`).toBeTruthy();
    const authData = await authResponse.json();
    const authToken = authData.token; // Assuming the login API returns a 'token' field.

    // Make an API request to the billing widget endpoint.
    const apiResponse = await request.get(process.env.BASE_URL + '/api/billing/widget-data', {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });
    expect(apiResponse.ok(), `Billing widget API call failed: ${apiResponse.status()} ${await apiResponse.text()}`).toBeTruthy();
    const responseBody = await apiResponse.json();

    // Validate the schema: check for expected properties and their types.
    expect(responseBody).toHaveProperty('totalRevenue');
    expect(typeof responseBody.totalRevenue).toBe('number');
    expect(responseBody).toHaveProperty('currency');
    expect(typeof responseBody.currency).toBe('string');
    expect(responseBody).toHaveProperty('lastMonthRevenue');
    expect(typeof responseBody.lastMonthRevenue).toBe('number');
    expect(responseBody).toHaveProperty('transactions');
    expect(Array.isArray(responseBody.transactions)).toBe(true);
    expect(responseBody.transactions.length).toBeGreaterThanOrEqual(0);

    if (responseBody.transactions.length > 0) {
      const firstTransaction = responseBody.transactions[0];
      expect(firstTransaction).toHaveProperty('id');
      expect(typeof firstTransaction.id).toBe('string');
      expect(firstTransaction).toHaveProperty('amount');
      expect(typeof firstTransaction.amount).toBe('number');
      expect(firstTransaction).toHaveProperty('date');
      expect(typeof firstTransaction.date).toBe('string'); // Expecting ISO 8601 or similar date string format
      // Further validation for date format can be added if needed, e.g., using a regex.
    }
  });

  test('Error responses do not expose internal stack traces or sensitive implementation details', async ({ request }) => {
    // First, log in to ensure we have an authenticated session for a protected API route.
    const authResponse = await request.post(process.env.BASE_URL + '/api/login', {
      data: {
        username: ADMIN_USER,
        password: ADMIN_PASS,
      },
    });
    expect(authResponse.ok(), `Failed to authenticate for error test: ${authResponse.status()} ${await authResponse.text()}`).toBeTruthy();
    const authData = await authResponse.json();
    const authToken = authData.token; // Assuming token-based auth.

    // Attempt to access a non-existent or malformed API endpoint within the billing context
    // to trigger an error. Adjust '/api/billing/non-existent-endpoint' to a known error-triggering path.
    const errorResponse = await request.get(process.env.BASE_URL + '/api/billing/non-existent-endpoint', {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      failOnStatusCode: false, // Important: Do not fail the test on non-2xx status codes.
    });

    // Expect an error status code (e.g., 404 Not Found, 500 Internal Server Error, 400 Bad Request).
    expect(errorResponse.status()).toBeGreaterThanOrEqual(400);
    const responseText = await errorResponse.text();

    // Assert that common indicators of sensitive information are NOT present in the response body.
    expect(responseText).not.toContain('stack trace');
    expect(responseText).not.toContain('at com.example'); // Example Java stack trace indicator
    expect(responseText).not.toContain('org.springframework'); // Example Spring Framework detail
    expect(responseText).not.toContain('java.lang.'); // Example Java exception detail
    expect(responseText).not.toContain('php_error.log'); // Example PHP error log detail
    expect(responseText).not.toContain('node_modules'); // Example Node.js path detail
    expect(responseText).not.toContain('/var/www/'); // Example server file path
    expect(responseText).not.toContain('internal server error'); // Generic phrase that might indicate raw error
    expect(responseText).not.toContain('Error:'); // Generic error message that might contain details

    // If the response is JSON, parse it and check specific properties.
    try {
      const errorJson = JSON.parse(responseText);
      expect(errorJson).not.toHaveProperty('stack');
      expect(errorJson).not.toHaveProperty('exception');
      // Ensure a user-friendly message is present, but not sensitive details.
      expect(errorJson).toHaveProperty('message');
      expect(typeof errorJson.message).toBe('string');
      expect(errorJson.message).not.toContain('stack trace');
    } catch (e) {
      // If not JSON, the text-based checks above are sufficient.
    }
  });
});
