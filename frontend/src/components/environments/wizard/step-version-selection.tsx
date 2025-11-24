import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { MOCK_VERSIONS } from './mock-data';

export function StepVersionSelection() {
  const { t } = useTranslation();
  const { config, updateConfig } = useWizardStore();

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.versionSelection.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.versionSelection.subtitle')}
        </p>
      </div>

      <div className="grid gap-3">
        {MOCK_VERSIONS.map((version) => (
          <div
            key={version.id}
            onClick={() => updateConfig({ lerobotVersion: version.name })}
            onKeyDown={(e) =>
              e.key === 'Enter' && updateConfig({ lerobotVersion: version.name })
            }
            role="button"
            tabIndex={0}
            className={cn(
              'relative flex cursor-pointer items-center justify-between rounded-lg border p-4 transition-all',
              config.lerobotVersion === version.name
                ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
                : 'border-border-default bg-surface-secondary hover:border-border-subtle',
            )}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-content-primary font-medium">{version.name}</span>
                {version.type === 'stable' && (
                  <span className="bg-success-surface text-success-content rounded px-1.5 py-0.5 text-[10px] font-medium uppercase">
                    {t('wizard.versionSelection.stable')}
                  </span>
                )}
              </div>
              <p className="text-content-tertiary text-sm">
                {t('wizard.versionSelection.released')}:{' '}
                {new Date(version.date).toLocaleDateString()}
              </p>
            </div>

            {config.lerobotVersion === version.name && (
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
                <Check className="h-3 w-3" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
