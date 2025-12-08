import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import type { AppConfig } from '../types';

interface LanguageSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
  hasUnsavedChanges: boolean;
}

export function LanguageSection({
  config,
  setConfig,
  hasUnsavedChanges,
}: LanguageSectionProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <CardTitle>{t('settings.language.title')}</CardTitle>
            <p className="text-content-secondary text-sm">
              {t('settings.language.description')}
            </p>
          </div>
          {hasUnsavedChanges && (
            <span className="rounded border border-amber-900/50 bg-amber-900/20 px-2 py-1 text-xs font-medium text-amber-500">
              {t('settings.unsavedChanges')}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div>
          <label className="text-content-primary text-sm font-medium">
            {t('settings.language.preferredLanguage')}
          </label>
          <select
            className="border-border-default bg-surface-secondary text-content-primary mt-2 w-full rounded-md border px-3 py-2 focus:border-blue-500 focus:outline-none"
            value={config.ui.preferred_language}
            onChange={(e) => {
              setConfig({
                ...config,
                ui: {
                  ...config.ui,
                  preferred_language: e.target.value as 'en' | 'zh',
                },
              });
            }}
          >
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </div>
      </CardContent>
    </Card>
  );
}
