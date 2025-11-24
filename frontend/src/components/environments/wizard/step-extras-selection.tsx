import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { MOCK_EXTRAS } from './mock-data';

export function StepExtrasSelection() {
  const { t } = useTranslation();
  const { config, updateConfig } = useWizardStore();

  const toggleExtra = (extraId: string) => {
    const currentExtras = config.extras;
    if (currentExtras.includes(extraId)) {
      updateConfig({ extras: currentExtras.filter((id) => id !== extraId) });
    } else {
      updateConfig({ extras: [...currentExtras, extraId] });
    }
  };

  // Group extras by category
  const extrasByCategory = MOCK_EXTRAS.reduce(
    (acc, extra) => {
      if (!acc[extra.category]) {
        acc[extra.category] = [];
      }
      acc[extra.category].push(extra);
      return acc;
    },
    {} as Record<string, typeof MOCK_EXTRAS>,
  );

  const categoryTitles: Record<string, string> = {
    robots: t('wizard.extrasSelection.categories.robots'),
    simulation: t('wizard.extrasSelection.categories.simulation'),
    other: t('wizard.extrasSelection.categories.other'),
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.extrasSelection.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.extrasSelection.subtitle')}
        </p>
      </div>

      <div className="space-y-6">
        {Object.entries(extrasByCategory).map(([category, extras]) => (
          <div key={category} className="space-y-3">
            <h4 className="text-content-secondary text-xs font-medium tracking-wider uppercase">
              {categoryTitles[category] || category}
            </h4>
            <div className="grid gap-3">
              {extras.map((extra) => (
                <div
                  key={extra.id}
                  onClick={() => toggleExtra(extra.id)}
                  onKeyDown={(e) => e.key === 'Enter' && toggleExtra(extra.id)}
                  role="button"
                  tabIndex={0}
                  className={cn(
                    'relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all',
                    config.extras.includes(extra.id)
                      ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
                      : 'border-border-default bg-surface-secondary hover:border-border-subtle',
                  )}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-content-primary font-medium">
                        {extra.name}
                      </span>
                    </div>
                    <p className="text-content-tertiary mt-1 text-sm">
                      {extra.description}
                    </p>
                  </div>
                  {config.extras.includes(extra.id) && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
                      <Check className="h-3 w-3" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
