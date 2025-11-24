import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';

export function StepNameConfig() {
  const { t } = useTranslation();
  const { config, updateConfig } = useWizardStore();

  // Auto-generate ID from friendly name if ID is empty
  useEffect(() => {
    if (!config.friendlyName) return;

    // Generate environment ID from friendly name
    const id = config.friendlyName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');

    if (id !== config.envName) {
      updateConfig({ envName: id });
    }
  }, [config.friendlyName, config.envName, updateConfig]);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.nameConfig.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.nameConfig.subtitle')}
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <label className="text-content-primary text-sm font-medium">
            {t('wizard.nameConfig.friendlyName')}
          </label>
          <input
            type="text"
            value={config.friendlyName}
            onChange={(e) => updateConfig({ friendlyName: e.target.value })}
            placeholder="e.g. My LeRobot Project"
            className="border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 transition-colors outline-none focus:border-blue-600"
          />
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.friendlyNameHelp')}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-content-primary text-sm font-medium">
            {t('wizard.nameConfig.internalName')}
          </label>
          <div className="relative">
            <input
              type="text"
              value={config.envName}
              onChange={(e) => updateConfig({ envName: e.target.value })}
              placeholder="e.g. my-lerobot-project"
              className="border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 font-mono text-sm transition-colors outline-none focus:border-blue-600"
            />
          </div>
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.internalNameHelp')}
          </p>
        </div>
      </div>
    </div>
  );
}
