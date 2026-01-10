import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import type { AppConfig } from '../types';

interface HuggingFaceSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
}

export function HuggingFaceSection({ config, setConfig }: HuggingFaceSectionProps) {
  const { t } = useTranslation();

  // If huggingface config is missing, initialize it
  if (!config.huggingface) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="space-y-1.5">
          <CardTitle>{t('settings.huggingface.title')}</CardTitle>
          <p className="text-content-secondary text-sm">
            {t('settings.huggingface.description')}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label
            htmlFor="hf-token"
            className="text-content-secondary text-xs font-medium uppercase"
          >
            {t('settings.huggingface.token')}
          </label>
          <input
            id="hf-token"
            type="password"
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={config.huggingface.token || ''}
            onChange={(e) =>
              setConfig({
                ...config,
                huggingface: {
                  ...config.huggingface!,
                  token: e.target.value,
                },
              })
            }
            placeholder={t('settings.huggingface.tokenPlaceholder')}
          />
          <p className="text-content-tertiary text-xs">
            {t('settings.huggingface.tokenHelp')}
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="hf-cache-dir"
            className="text-content-secondary text-xs font-medium uppercase"
          >
            {t('settings.huggingface.cacheDir')}
          </label>
          <input
            id="hf-cache-dir"
            type="text"
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={config.huggingface.cache_dir || ''}
            onChange={(e) =>
              setConfig({
                ...config,
                huggingface: {
                  ...config.huggingface!,
                  cache_dir: e.target.value,
                },
              })
            }
            placeholder={t('settings.huggingface.cacheDirPlaceholder')}
          />
        </div>
      </CardContent>
    </Card>
  );
}