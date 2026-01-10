import { test, expect } from '@playwright/test';

test.describe('Settings - Theme and Language', () => {
  // Mock config response
  const mockConfig = {
    server: { port: 8000, host: 'localhost', auto_open_browser: true },
    ui: { theme: 'light', preferred_language: 'en' },
    paths: {
      data_dir: '/tmp/data',
      repos_dir: '/tmp/repos',
      environments_dir: '/tmp/envs',
      logs_dir: '/tmp/logs',
      cache_dir: '/tmp/cache',
    },
    tools: {
      git: { type: 'bundled', custom_path: null },
      uv: { type: 'bundled', custom_path: null },
    },
    repositories: {
      lerobot_sources: [],
      default_branch: 'main',
      default_version: 'latest',
    },
    pypi: { mirrors: [] },
    huggingface: { token: '', cache_dir: '' },
    advanced: { installation_timeout: 600, log_level: 'INFO' },
  };

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.clear());

    // Mock the config endpoint
    await page.route('**/api/config', async (route) => {
      const responseBody = JSON.parse(JSON.stringify(mockConfig));
      await route.fulfill({ json: responseBody });
    });

    // Mock check environments endpoint
    await page.route('**/api/config/has-environments', async (route) => {
      await route.fulfill({ json: { has_environments: false } });
    });
  });

  test('should initialize with default settings from backend', async ({ page }) => {
    await page.goto('/settings');
    const heading = page.getByRole('heading', { level: 1 });
    const html = page.locator('html');
    await expect(heading).toHaveText('Settings');
    await expect(html).toHaveAttribute('data-theme', 'light');

    // Check Theme "Light" is active
    // The button for "Light" theme should have the active class
    // We can find it by text "Light" (or "亮色" if it was Chinese, but default is en)
    const lightThemeBtn = page.getByRole('button', { name: 'Light' });
    await expect(lightThemeBtn).toHaveClass(/border-primary/);

    // Check Language "English" is selected
    const langSelect = page.locator('select').filter({ hasText: 'English' });
    await expect(langSelect).toHaveValue('en');
  });

  test('should preview theme changes immediately', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/settings');
    const html = page.locator('html');

    // Initial state is driven by backend-configured "light" theme
    await expect(html).toHaveAttribute('data-theme', 'light');

    // Click Dark theme and verify data attribute updates immediately
    await page.getByRole('button', { name: 'Dark' }).click();
    await expect(html).toHaveAttribute('data-theme', 'dark');

    // System theme should follow system preference (forced to light above)
    await page.getByRole('button', { name: 'System' }).click();
    await expect(html).toHaveAttribute('data-theme', 'light');
  });

  test('should preview language changes immediately', async ({ page }) => {
    await page.goto('/settings');
    const heading = page.getByRole('heading', { level: 1 });
    await expect(heading).toHaveText('Settings');

    // Change to Chinese
    const langSelect = page.locator('select').filter({ hasText: 'English' });
    await langSelect.selectOption('zh');

    // Verify title and sidebar translate immediately
    await expect(heading).toHaveText('设置');
    await expect(page.getByRole('link', { name: '环境' })).toBeVisible();
  });

  test('should revert changes when leaving without saving', async ({ page }) => {
    await page.goto('/settings');
    const heading = page.getByRole('heading', { level: 1 });
    const html = page.locator('html');
    await expect(heading).toHaveText('Settings');
    await expect(html).toHaveAttribute('data-theme', 'light');

    // Change Language to Chinese
    const langSelect = page.locator('select').filter({ hasText: 'English' });
    await langSelect.selectOption('zh');
    await expect(heading).toHaveText('设置');

    // Change Theme to Dark
    await page.getByRole('button', { name: /Dark|暗色/ }).click();
    await expect(html).toHaveAttribute('data-theme', 'dark');

    // Navigate away (e.g. click "环境" in sidebar - since language is currently Chinese)
    await page.getByRole('link', { name: '环境' }).click();

    // Wait for navigation
    await expect(page).toHaveURL(/\/environments/);
    await expect(heading).toHaveText('Environments');

    // Verify language reverted to English (Sidebar link should be "Environments")
    await expect(page.getByRole('link', { name: 'Environments' })).toBeVisible();

    // Verify theme reverted to Light
    await expect(html).toHaveAttribute('data-theme', 'light');
  });
});
