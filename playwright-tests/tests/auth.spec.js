import { test, expect } from '@playwright/test';

test.describe('Authentication Tests', () => {
  const LOGIN_PATH = '/login';
  const SECURE_PATH = '/secure';

  test.beforeEach(async ({ page }) => {
    await page.goto(LOGIN_PATH);
    await expect(page).toHaveURL(new RegExp(`${LOGIN_PATH}$`));
  });

  test('should allow login with valid credentials and redirect to dashboard', async ({ page }) => {
    await test.step('Enter valid credentials', async () => {
      test.skip(!process.env.TEST_USER || !process.env.TEST_PASS, 'TEST_USER and TEST_PASS environment variables are required.');
      await page.fill('#username', process.env.TEST_USER);
      await page.fill('#password', process.env.TEST_PASS);
      await page.click('button[type="submit"]');
    });

    await test.step('Verify redirection to secure area', async () => {
      await expect(page).toHaveURL(new RegExp(`${SECURE_PATH}$`));
      await expect(page.locator('#flash')).toContainText('You logged into a secure area!');
    });
  });

  test('should show error message with invalid password', async ({ page }) => {
    await test.step('Enter username and an invalid password', async () => {
      const user = process.env.TEST_USER || 'tomsmith';
      await page.fill('#username', user);
      await page.fill('#password', 'invalid-password-123');
      await page.click('button[type="submit"]');
    });

    await test.step('Verify error message is displayed', async () => {
      const errorMessage = page.locator('#flash');
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText('Your password is invalid!');
      await expect(page).toHaveURL(new RegExp(`${LOGIN_PATH}$`));
    });
  });

  test('should prevent login for a locked account and display an error (security test)', async ({ page }) => {
    test.skip(true, 'the-internet.herokuapp.com does not provide a lockout-account fixture to validate this scenario.');
  });
});
