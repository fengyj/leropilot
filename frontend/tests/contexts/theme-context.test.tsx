import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { ThemeProvider, useTheme } from '../../src/contexts/theme-context';
import { ReactNode } from 'react';

const createMediaQueryList = (query: string, prefersDark: boolean): MediaQueryList => {
  const matchesDarkQuery = query === '(prefers-color-scheme: dark)';
  return {
    matches: matchesDarkQuery ? prefersDark : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  };
};

describe('ThemeContext', () => {
  let mockMatchMedia: vi.MockedFunction<typeof window.matchMedia>;
  let mockLocalStorage: Record<string, string>;

  beforeEach(() => {
    // Mock localStorage
    mockLocalStorage = {};
    Storage.prototype.getItem = vi.fn((key: string) => mockLocalStorage[key] || null);
    Storage.prototype.setItem = vi.fn((key: string, value: string) => {
      mockLocalStorage[key] = value;
    });
    Storage.prototype.removeItem = vi.fn((key: string) => {
      delete mockLocalStorage[key];
    });

    // Mock matchMedia
    mockMatchMedia = vi
      .fn((query: string) => createMediaQueryList(query, true))
      .mockName('matchMedia');
    window.matchMedia = mockMatchMedia;

    // Mock fetch for config API
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
    mockLocalStorage = {};
  });

  describe('ThemeProvider', () => {
    it('should initialize with system theme by default', () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      expect(result.current.theme).toBe('system');
    });

    it('should initialize with theme from localStorage if available', () => {
      mockLocalStorage['leropilot-theme'] = 'dark';

      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      expect(result.current.theme).toBe('dark');
    });

    it('should apply light theme when theme is set to light', () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(result.current.theme).toBe('light');
      expect(result.current.effectiveTheme).toBe('light');
      expect(document.documentElement.getAttribute('data-theme')).toBe('light');
      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(mockLocalStorage['leropilot-theme']).toBe('light');
    });

    it('should apply dark theme when theme is set to dark', () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('dark');
      });

      expect(result.current.theme).toBe('dark');
      expect(result.current.effectiveTheme).toBe('dark');
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
      expect(mockLocalStorage['leropilot-theme']).toBe('dark');
    });

    it('should follow system preference when theme is set to system', () => {
      // Mock system prefers dark mode
      mockMatchMedia.mockImplementation((query: string) =>
        createMediaQueryList(query, true),
      );

      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('system');
      });

      expect(result.current.theme).toBe('system');
      expect(result.current.effectiveTheme).toBe('dark');
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    });

    it('should persist theme changes to localStorage', () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(mockLocalStorage['leropilot-theme']).toBe('light');

      act(() => {
        result.current.setTheme('dark');
      });

      expect(mockLocalStorage['leropilot-theme']).toBe('dark');
    });

    it('should load theme from config API', async () => {
      const mockConfig = {
        ui: { theme: 'dark', preferred_language: 'en' },
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig,
      } as Response);

      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      // Wait for config to load
      await waitFor(() => {
        expect(result.current.theme).toBe('dark');
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/config');
    });

    it('should handle config API errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error('Network error'),
      );

      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      // Should still have default theme
      expect(result.current.theme).toBe('system');

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });

    it('should not update theme if config theme matches current theme', async () => {
      mockLocalStorage['leropilot-theme'] = 'light';

      const mockConfig = {
        ui: { theme: 'light', preferred_language: 'en' },
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig,
      } as Response);

      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      // Initial theme should be from localStorage
      expect(result.current.theme).toBe('light');

      // Wait a bit to ensure config is loaded
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Theme should still be light (no unnecessary update)
      expect(result.current.theme).toBe('light');
    });
  });

  describe('useTheme hook', () => {
    it('should throw error when used outside ThemeProvider', () => {
      // Suppress console.error for this test
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useTheme());
      }).toThrow('useTheme must be used within a ThemeProvider');

      consoleErrorSpy.mockRestore();
    });

    it('should provide theme context values', () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <ThemeProvider>{children}</ThemeProvider>
      );

      const { result } = renderHook(() => useTheme(), { wrapper });

      expect(result.current).toHaveProperty('theme');
      expect(result.current).toHaveProperty('setTheme');
      expect(result.current).toHaveProperty('effectiveTheme');
      expect(typeof result.current.setTheme).toBe('function');
    });
  });
});
