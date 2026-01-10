import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SettingsPage } from '../../src/pages/settings';
import { ThemeProvider } from '../../src/contexts/theme-context';
import { BrowserRouter } from 'react-router-dom';
import { ReactNode } from 'react';

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
      changeLanguage: vi.fn(),
    },
  }),
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Save: () => <div>Save Icon</div>,
  RotateCcw: () => <div>Reset Icon</div>,
  AlertCircle: () => <div>Alert Icon</div>,
  CheckCircle2: () => <div>Check Icon</div>,
  Trash2: () => <div>Trash Icon</div>,
  Plus: () => <div>Plus Icon</div>,
  Sun: () => <div>Sun Icon</div>,
  Moon: () => <div>Moon Icon</div>,
  Monitor: () => <div>Monitor Icon</div>,
  Download: () => <div>Download Icon</div>,
  RefreshCw: () => <div>Refresh Icon</div>,
  Loader2: () => <div>Loader Icon</div>,
  Globe: () => <div>Globe Icon</div>,
  Server: () => <div>Server Icon</div>,
  X: () => <div>X Icon</div>,
}));

const mockConfig = {
  server: { port: 8000, host: 'localhost', auto_open_browser: true },
  ui: { theme: 'light' as const, preferred_language: 'en' as const },
  paths: {
    data_dir: '/tmp/data',
    repos_dir: '/tmp/repos',
    environments_dir: '/tmp/envs',
    logs_dir: '/tmp/logs',
    cache_dir: '/tmp/cache',
  },
  tools: {
    git: { type: 'bundled' as const, custom_path: null },
    uv: { type: 'bundled' as const, custom_path: null },
  },
  repositories: {
    lerobot_sources: [
      {
        name: 'Official',
        url: 'https://github.com/huggingface/lerobot',
        is_default: true,
      },
    ],
    default_branch: 'main',
    default_version: 'latest',
  },
  pypi: { mirrors: [] },
  huggingface: { token: '', cache_dir: '' },
  advanced: { installation_timeout: 600, log_level: 'INFO' as const },
};

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <BrowserRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </BrowserRouter>
  );
}

describe('SettingsPage', () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Mock matchMedia
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    mockFetch = vi.fn();
    global.fetch = mockFetch;

    // Default successful responses
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/app-config') {
        return Promise.resolve({
          ok: true,
          json: async () => mockConfig,
        } as Response);
      }
      if (url === '/api/environments/has-environments') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ has_environments: false }),
        } as Response);
      }
      if (url === '/api/tools/git/bundled/status') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ is_installed: true, version: '2.40.0' }),
        } as Response);
      }
      if (url.match(/\/api\/repositories\/.*\/status/)) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            is_downloaded: true,
            last_updated: null,
            has_updates: false,
          }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading and Initialization', () => {
    it('should show loading state initially', () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      expect(screen.getByText('Loading settings...')).toBeInTheDocument();
    });

    it('should load config on mount', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/app-config');
      });

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });
    });

    it('should show error state when config loading fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === '/api/app-config') {
          return Promise.reject(new Error('Network error'));
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: false }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText(/Error loading settings/)).toBeInTheDocument();
      });
    });

    it('should check for existing environments on mount', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/environments/has-environments',
          expect.any(Object),
        );
      });
    });
  });

  describe('Theme Selection', () => {
    it('should display theme selection buttons', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      expect(screen.getByText('settings.appearance.system')).toBeInTheDocument();
      expect(screen.getByText('settings.appearance.light')).toBeInTheDocument();
      expect(screen.getByText('settings.appearance.dark')).toBeInTheDocument();
    });

    it('should show active theme from config', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const lightButton = screen
        .getByText('settings.appearance.light')
        .closest('button');
      expect(lightButton).toHaveClass('border-primary');
    });
  });

  describe('Language Selection', () => {
    it('should display language select dropdown', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const selects = screen.getAllByRole('combobox');
      expect(selects.length).toBeGreaterThan(0);
      expect(selects[0]).toBeInTheDocument();
    });

    it('should show current language from config', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      // Get the language select (first combobox on the page)
      const selects = screen.getAllByRole('combobox');
      const languageSelect = selects[0] as HTMLSelectElement;
      expect(languageSelect.value).toBe('en');
    });
  });

  describe('Save Configuration', () => {
    it('should call save API when save button is clicked', async () => {
      mockFetch.mockImplementation((url: string, options?: RequestInit) => {
        if (url === '/api/app-config' && options?.method === 'PUT') {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/app-config' && !options?.method) {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: false }),
          } as Response);
        }
        if (url === '/api/tools/git/bundled/status') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ is_installed: true, version: '2.40.0' }),
          } as Response);
        }
        if (url.match(/\/api\/repositories\/.*\/status/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              is_downloaded: true,
              last_updated: null,
              has_updates: false,
            }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      // Change a setting to enable the save button
      const darkThemeButton = screen
        .getByText('settings.appearance.dark')
        .closest('button');
      if (darkThemeButton) {
        fireEvent.click(darkThemeButton);
      }

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/app-config',
          expect.objectContaining({
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      });
    });

    it('should show success message after successful save', async () => {
      mockFetch.mockImplementation((url: string, options?: RequestInit) => {
        if (url === '/api/app-config' && options?.method === 'PUT') {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/app-config' && !options?.method) {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: false }),
          } as Response);
        }
        if (url === '/api/tools/git/bundled/status') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ is_installed: true, version: '2.40.0' }),
          } as Response);
        }
        if (url.match(/\/api\/repositories\/.*\/status/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              is_downloaded: true,
              last_updated: null,
              has_updates: false,
            }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      // Change a setting to enable the save button
      const darkThemeButton = screen
        .getByText('settings.appearance.dark')
        .closest('button');
      if (darkThemeButton) {
        fireEvent.click(darkThemeButton);
      }

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('settings.messages.saveSuccess')).toBeInTheDocument();
      });
    });

    it('should show error message when save fails', async () => {
      mockFetch.mockImplementation((url: string, options?: RequestInit) => {
        if (url === '/api/app-config' && options?.method === 'PUT') {
          return Promise.resolve({
            ok: false,
            json: async () => ({ detail: 'Save failed' }),
          } as Response);
        }
        if (url === '/api/app-config' && !options?.method) {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: false }),
          } as Response);
        }
        if (url === '/api/tools/git/bundled/status') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ is_installed: true, version: '2.40.0' }),
          } as Response);
        }
        if (url.match(/\/api\/repositories\/.*\/status/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              is_downloaded: true,
              last_updated: null,
              has_updates: false,
            }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      // Change a setting to enable the save button
      const darkThemeButton = screen
        .getByText('settings.appearance.dark')
        .closest('button');
      if (darkThemeButton) {
        fireEvent.click(darkThemeButton);
      }

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Save failed')).toBeInTheDocument();
      });
    });
  });

  describe('Reset Configuration', () => {
    it('should call reset API when reset is confirmed', async () => {
      mockFetch.mockImplementation((url: string, options?: RequestInit) => {
        if (url === '/api/app-config/reset' && options?.method === 'POST') {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/app-config') {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: false }),
          } as Response);
        }
        if (url === '/api/tools/git/bundled/status') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ is_installed: true, version: '2.40.0' }),
          } as Response);
        }
        if (url.match(/\/api\/repositories\/.*\/status/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              is_downloaded: true,
              last_updated: null,
              has_updates: false,
            }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const resetButton = screen.getByRole('button', { name: /reset/i });
      fireEvent.click(resetButton);

      // Confirm dialog should appear; click confirm
      const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/app-config/reset', {
          method: 'POST',
        });
      });
    });

    it('should not call reset API when reset is cancelled', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const resetButton = screen.getByRole('button', { name: /reset/i });
      fireEvent.click(resetButton);

      // Find cancel button in the confirm dialog and click it
      const cancelBtn = await screen.findByRole('button', { name: /cancel/i });
      fireEvent.click(cancelBtn);

      expect(mockFetch).not.toHaveBeenCalledWith('/api/app-config/reset', {
        method: 'POST',
      });
    });
  });

  describe('Data Directory Locking', () => {
    it('should disable data directory input when environments exist', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === '/api/app-config') {
          return Promise.resolve({
            ok: true,
            json: async () => mockConfig,
          } as Response);
        }
        if (url === '/api/environments/has-environments') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ has_environments: true }),
          } as Response);
        }
        if (url === '/api/tools/git/bundled/status') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ is_installed: true, version: '2.40.0' }),
          } as Response);
        }
        if (url.match(/\/api\/repositories\/.*\/status/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              is_downloaded: true,
              last_updated: null,
              has_updates: false,
            }),
          } as Response);
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const dataDirInput = screen.getByDisplayValue('/tmp/data');
      expect(dataDirInput).toBeDisabled();
    });

    it('should enable data directory input when no environments exist', async () => {
      render(
        <Wrapper>
          <SettingsPage />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText('settings.title')).toBeInTheDocument();
      });

      const dataDirInput = screen.getByDisplayValue('/tmp/data');
      expect(dataDirInput).not.toBeDisabled();
    });
  });
});
