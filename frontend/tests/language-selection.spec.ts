import { test, expect } from '@playwright/test';

test.describe('Language Selection', () => {
  test('should change language from English to Chinese', async ({ page }) => {
    // Navigate to settings page
    await page.goto('/settings');

    // Wait for the page to load
    await page.waitForSelector('h1');

    // Find the language select dropdown
    // We look for the select that contains language options
    const languageSelect = page
      .locator('select')
      .filter({ hasText: 'English' })
      .first();

    // Ensure we start in English for this test
    await languageSelect.selectOption('en');
    await expect(page.locator('h1')).toHaveText('Settings');

    // Switch to Chinese
    await languageSelect.selectOption('zh');

    // Verify the title changes to Chinese
    await expect(page.locator('h1')).toHaveText('设置');
  });

  test('should persist language selection', async ({ page }) => {
    // Navigate to settings page
    await page.goto('/settings');

    // Change language to Chinese
    const languageSelect = page
      .locator('select')
      .filter({ hasText: 'English' })
      .first();
    await languageSelect.selectOption('zh');

    // Verify change
    await expect(page.locator('h1')).toHaveText('设置');

    // Refresh the page
    await page.reload();

    // Check if language is still Chinese
    await expect(page.locator('h1')).toHaveText('设置');
  });
});
