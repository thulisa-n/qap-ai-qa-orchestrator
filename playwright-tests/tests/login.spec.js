const { test, expect } = require('@playwright/test');

test.describe('Login Functionality', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.BASE_URL, 'BASE_URL is not set');
    await page.goto('/login');
  });

  test('should allow a user to log in successfully', async ({ page }) => {
    test.skip(!process.env.TEST_USER || !process.env.TEST_PASS, 'TEST_USER/TEST_PASS not set');

    await page.fill('#username', process.env.TEST_USER);
    await page.fill('#password', process.env.TEST_PASS);
    await page.click('button[type="submit"]');

    await expect(page.locator('#flash')).toContainText('You logged into a secure area!');
  });

  test('should display an error message for invalid password', async ({ page }) => {
    await page.fill('#username', 'tomsmith');
    await page.fill('#password', 'WrongPassword123');
    await page.click('button[type="submit"]');

    // Password should never appear in URL
    await expect(page).not.toHaveURL(/WrongPassword123/);

    await expect(page.locator('#flash')).toContainText('Your password is invalid!');
  });

  test('should not expose sensitive info in URL after failed login', async ({ page }) => {
    const badPassword = 'WrongPassword123';

    await page.fill('#username', 'wronguser');
    await page.fill('#password', badPassword);
    await page.click('button[type="submit"]');

    // Ensure password is NOT in URL
    await expect(page).not.toHaveURL(new RegExp(badPassword));

    await expect(page.locator('#flash')).toContainText('Your username is invalid!');
  });
});

