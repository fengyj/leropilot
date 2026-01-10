import { useTranslation } from 'react-i18next';
import { camelCase } from 'lodash';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import type { AppConfig } from '../types';

interface PathsSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
  hasEnvironments: boolean;
}

export function PathsSection({
  config,
  setConfig,
  hasEnvironments,
}: PathsSectionProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <div className="space-y-1.5">
          <CardTitle>{t('settings.paths.title')}</CardTitle>
          <p className="text-content-secondary text-sm">
            {t('settings.paths.description')}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <section className="space-y-4">
          <div className="space-y-4">
            {/* Data Dir */}
            <div className="space-y-2">
              <label className="text-content-secondary text-sm font-medium">
                {t('settings.paths.dataDir')}
              </label>
              <div className="space-y-1">
                <input
                  type="text"
                  className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={config.paths.data_dir}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      paths: { ...config.paths, data_dir: e.target.value },
                    })
                  }
                  disabled={hasEnvironments}
                />
                <p className="text-content-tertiary text-xs">
                  {t('settings.paths.dataDirDescription')}
                </p>
                {hasEnvironments && (
                  <p className="text-warning-content text-xs">
                    {t('settings.paths.dataDirLocked')}
                  </p>
                )}
              </div>
            </div>

            {/* Read-only Paths */}
            {(['repos_dir', 'environments_dir', 'logs_dir', 'cache_dir'] as const).map(
              (pathKey) => (
                <div key={pathKey} className="space-y-2">
                  <label className="text-content-secondary text-sm font-medium">
                    {t(`settings.paths.${camelCase(pathKey)}` as string)}
                  </label>
                  <input
                    type="text"
                    className="border-border-default bg-surface-tertiary text-content-secondary w-full cursor-not-allowed rounded-md border px-3 py-2 text-sm focus:outline-none"
                    value={config.paths[pathKey] || ''}
                    readOnly
                  />
                </div>
              ),
            )}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}