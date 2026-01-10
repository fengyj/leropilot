import { Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { useEffect, useState } from 'react';

interface Extra {
  id: string;
  name: string;
  description: string;
  category: string;
  category_label: string;
}

export function StepExtrasSelection() {
  const { t, i18n } = useTranslation();
  const { config, updateConfig } = useWizardStore();
  const [extras, setExtras] = useState<Extra[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchExtras = async () => {
      if (!config.repositoryId) return;

      setLoading(true);
      try {
        // Pass current language to backend for localized metadata
        const lang = i18n.language.split('-')[0]; // e.g. 'zh-CN' -> 'zh'
        const ref = config.lerobotVersion || 'main';
        const response = await fetch(
          `/api/environments/extras?repo_id=${config.repositoryId}&ref=${ref}&lang=${lang}`,
        );
        if (response.ok) {
          const data = await response.json();
          setExtras(data);
        }
      } catch (error) {
        console.error('Failed to fetch extras:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchExtras();
  }, [config.repositoryId, config.lerobotVersion, i18n.language]);

  const toggleExtra = (extraId: string) => {
    if ((config.extras || []).includes('all')) return;

    const currentExtras = config.extras || [];
    if (currentExtras.includes(extraId)) {
      updateConfig({ extras: currentExtras.filter((id) => id !== extraId) });
    } else {
      updateConfig({ extras: [...currentExtras, extraId] });
    }
  };

  const toggleAll = () => {
    if ((config.extras || []).includes('all')) {
      updateConfig({ extras: [] });
    } else {
      updateConfig({ extras: ['all'] });
    }
  };

  // Filter out 'all' from the list as it's handled separately
  const displayExtras = extras.filter((e) => e.id !== 'all');
  const hasAllOption = extras.some((e) => e.id === 'all');

  // Group extras by category
  const extrasByCategory = displayExtras.reduce(
    (acc, extra) => {
      if (!acc[extra.category]) {
        acc[extra.category] = [];
      }
      acc[extra.category].push(extra);
      return acc;
    },
    {} as Record<string, Extra[]>,
  );

  const categoryTitles: Record<string, string> = {
    // Fallback titles if backend doesn't provide them (though it should)
    robots: t('wizard.extrasSelection.categories.robots'),
    simulation: t('wizard.extrasSelection.categories.simulation'),
    policies: t('wizard.extrasSelection.categories.policies'),
    features: t('wizard.extrasSelection.categories.features'),
    motors: t('wizard.extrasSelection.categories.motors'),
    other: t('wizard.extrasSelection.categories.other'),
  };

  const categoryOrder = [
    'robots',
    'simulation',
    'policies',
    'features',
    'motors',
    'other',
  ];

  const sortedCategories = Object.entries(extrasByCategory).sort(([a], [b]) => {
    // If category not in order list, put it before 'other' (which is last)
    // or just at the end if 'other' is not present.
    // Using 999 for unknown categories to put them at the end.
    const getIndex = (key: string) => {
      const idx = categoryOrder.indexOf(key);
      return idx === -1 ? 999 : idx;
    };
    return getIndex(a) - getIndex(b);
  });

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  const isAllSelected = (config.extras || []).includes('all');

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

      {hasAllOption && (
        <div
          onClick={toggleAll}
          onKeyDown={(e) => e.key === 'Enter' && toggleAll()}
          role="button"
          tabIndex={0}
          className={cn(
            'relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all',
            isAllSelected
              ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
              : 'border-border-default bg-surface-secondary hover:border-border-subtle',
          )}
        >
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-content-primary font-medium">
                {t('wizard.extrasSelection.all')}
              </span>
            </div>
            <p className="text-content-tertiary mt-1 text-sm">
              {t('wizard.extrasSelection.allDescription')}
            </p>
          </div>
          {isAllSelected && (
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
              <Check className="h-3 w-3" />
            </div>
          )}
        </div>
      )}

      <div className={cn('space-y-6', isAllSelected && 'opacity-50 grayscale')}>
        {sortedCategories.map(([category, categoryExtras]) => (
          <div key={category} className="space-y-3">
            <h4 className="text-content-secondary text-xs font-medium tracking-wider uppercase">
              {categoryExtras[0]?.category_label ||
                categoryTitles[category] ||
                category}
            </h4>
            <div className="grid gap-3">
              {categoryExtras.map((extra) => (
                <div
                  key={extra.id}
                  onClick={() => toggleExtra(extra.id)}
                  onKeyDown={(e) => e.key === 'Enter' && toggleExtra(extra.id)}
                  role="button"
                  tabIndex={0}
                  className={cn(
                    'relative flex items-start gap-4 rounded-lg border p-4 transition-all',
                    isAllSelected
                      ? 'border-border-default bg-surface-tertiary cursor-not-allowed'
                      : 'cursor-pointer',
                    !isAllSelected && (config.extras || []).includes(extra.id)
                      ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
                      : !isAllSelected &&
                          'border-border-default bg-surface-secondary hover:border-border-subtle',
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
                  {!isAllSelected && (config.extras || []).includes(extra.id) && (
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