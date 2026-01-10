import { useTranslation } from 'react-i18next';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { cn } from '../../../utils/cn';
import type { AppConfig } from '../types';

interface AppearanceSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
  hasUnsavedChanges: boolean;
}

export function AppearanceSection({
  config,
  setConfig,
  hasUnsavedChanges,
}: AppearanceSectionProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <CardTitle>{t('settings.appearance.title')}</CardTitle>
            <p className="text-content-secondary text-sm">
              {t('settings.appearance.description')}
            </p>
          </div>
          {hasUnsavedChanges && (
            <span className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/20 dark:border-amber-700 dark:text-amber-300">
              {t('settings.unsavedChanges')}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-content-primary text-sm font-medium">
            {t('settings.appearance.theme')}
          </label>
          <p className="text-content-secondary mb-3 text-xs">
            {t('settings.appearance.themeDescription')}
          </p>
          <div className="grid grid-cols-3 gap-3">
            {(['system', 'light', 'dark'] as const).map((theme) => {
              const Icon =
                theme === 'system' ? Monitor : theme === 'light' ? Sun : Moon;
              return (
                <button
                  key={theme}
                  onClick={() => setConfig({ ...config, ui: { ...config.ui, theme } })}
                  className={cn(
                    'flex flex-col items-center gap-2 rounded-lg border p-4 transition-all',
                    config.ui.theme === theme
                      ? 'border-blue-600 bg-blue-600/10 text-blue-500'
                      : 'border-border-default bg-surface-tertiary text-content-secondary hover:border-border-subtle',
                  )}
                >
                  <Icon className="h-5 w-5" />
                  <span className="text-sm font-medium">
                    {t(`settings.appearance.${theme}`)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}