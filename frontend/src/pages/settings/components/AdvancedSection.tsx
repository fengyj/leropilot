import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import type { AppConfig } from '../types';

interface AdvancedSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
}

export function AdvancedSection({ config, setConfig }: AdvancedSectionProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <div className="space-y-1.5">
          <CardTitle>{t('settings.advanced.title')}</CardTitle>
          <p className="text-content-secondary text-sm">
            {t('settings.advanced.description')}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-content-secondary text-xs font-medium uppercase">
            {t('settings.advanced.installationTimeout')}
          </label>
          <input
            type="number"
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={config.advanced.installation_timeout}
            onChange={(e) =>
              setConfig({
                ...config,
                advanced: {
                  ...config.advanced,
                  installation_timeout: parseInt(e.target.value) || 3600,
                },
              })
            }
          />
          <p className="text-content-tertiary text-xs">
            {t('settings.advanced.installationTimeoutDescription')}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-content-secondary text-xs font-medium uppercase">
            {t('settings.advanced.logLevel')}
          </label>
          <select
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={config.advanced.log_level}
            onChange={(e) =>
              setConfig({
                ...config,
                advanced: {
                  ...config.advanced,
                  log_level: e.target.value as 'INFO' | 'DEBUG' | 'TRACE',
                },
              })
            }
          >
            <option value="INFO">{t('settings.advanced.logLevelInfo')}</option>
            <option value="DEBUG">{t('settings.advanced.logLevelDebug')}</option>
            <option value="TRACE">{t('settings.advanced.logLevelTrace')}</option>
          </select>
          <p className="text-content-tertiary text-xs">
            {t('settings.advanced.logLevelDescription')}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}