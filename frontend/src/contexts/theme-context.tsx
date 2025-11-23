import {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  ReactNode,
} from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  effectiveTheme: 'light' | 'dark';
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_STORAGE_KEY = 'leropilot-theme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    // Load from localStorage immediately during initialization
    const saved = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    return saved || 'system';
  });
  const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>('dark');
  const themeRef = useRef(theme);

  // Keep themeRef in sync with theme
  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);

  // Apply theme immediately on mount and whenever it changes
  useEffect(() => {
    const root = document.documentElement;

    const applyTheme = (resolvedTheme: 'light' | 'dark') => {
      setEffectiveTheme(resolvedTheme);
      root.classList.remove('light', 'dark');
      root.classList.add(resolvedTheme);
      root.setAttribute('data-theme', resolvedTheme);
    };

    // Save to localStorage
    localStorage.setItem(THEME_STORAGE_KEY, theme);

    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
        applyTheme(e.matches ? 'dark' : 'light');
      };

      // Initial application
      handleChange(mediaQuery);

      // Listen for changes
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    } else {
      applyTheme(theme);
    }
  }, [theme]);

  // Load theme from config (but don't block initial render)
  useEffect(() => {
    const loadConfigTheme = async () => {
      try {
        const response = await fetch('/api/config');
        if (response.ok) {
          const config = await response.json();
          const configTheme = config.ui.theme || 'system';
          // Only update if different from current theme
          // Note: We use a ref to avoid stale closure issues
          if (configTheme !== themeRef.current) {
            setTheme(configTheme);
          }
        }
      } catch (error) {
        console.error('Failed to load theme from config:', error);
      }
    };
    loadConfigTheme();
  }, []); // Only run once on mount - intentionally empty deps

  return (
    <ThemeContext.Provider value={{ theme, setTheme, effectiveTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
