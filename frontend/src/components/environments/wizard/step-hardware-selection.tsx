import { Zap, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';

export function StepHardwareSelection() {
  const { t } = useTranslation();
  const { config, updateConfig } = useWizardStore();

  // Mock detection result
  const detectedHardware = {
    gpu: 'NVIDIA GeForce RTX 4090',
    driver: '535.183.01',
    cuda: '12.2',
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.hardwareSelection.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.hardwareSelection.subtitle')}
        </p>
      </div>

      {/* Detected Hardware Info */}
      <div className="bg-surface-tertiary flex items-center gap-4 rounded-lg p-4">
        <div className="bg-surface-secondary flex h-10 w-10 items-center justify-center rounded-full">
          <Zap className="text-content-primary h-5 w-5" />
        </div>
        <div>
          <p className="text-content-secondary text-xs font-medium uppercase">
            {t('wizard.hardwareSelection.detected')}
          </p>
          <p className="text-content-primary font-medium">{detectedHardware.gpu}</p>
          <p className="text-content-tertiary text-xs">
            {t('wizard.hardwareSelection.driver')}: {detectedHardware.driver} • CUDA:{' '}
            {detectedHardware.cuda}
          </p>
        </div>
      </div>

      <div className="grid gap-4">
        {/* Auto Detect Option */}
        <div
          onClick={() => updateConfig({ cudaVersion: 'auto' })}
          onKeyDown={(e) => e.key === 'Enter' && updateConfig({ cudaVersion: 'auto' })}
          role="button"
          tabIndex={0}
          className={cn(
            'relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all',
            config.cudaVersion === 'auto'
              ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
              : 'border-border-default bg-surface-secondary hover:border-border-subtle',
          )}
        >
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-content-primary font-medium">
                {t('wizard.hardwareSelection.auto')}
              </span>
              <span className="bg-success-surface text-success-content rounded px-1.5 py-0.5 text-[10px] font-medium uppercase">
                {t('wizard.hardwareSelection.best')}
              </span>
            </div>
            <p className="text-content-tertiary mt-1 text-sm">
              {t('wizard.hardware.compatibilityNote')}
            </p>
          </div>
          {config.cudaVersion === 'auto' && (
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
              <Check className="h-3 w-3" />
            </div>
          )}
        </div>

        {/* CPU Only Option */}
        <div
          onClick={() => updateConfig({ cudaVersion: 'cpu' })}
          onKeyDown={(e) => e.key === 'Enter' && updateConfig({ cudaVersion: 'cpu' })}
          role="button"
          tabIndex={0}
          className={cn(
            'relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all',
            config.cudaVersion === 'cpu'
              ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
              : 'border-border-default bg-surface-secondary hover:border-border-subtle',
          )}
        >
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-content-primary font-medium">
                {t('wizard.hardwareSelection.cpu')}
              </span>
            </div>
            <p className="text-content-tertiary mt-1 text-sm">
              Running on CPU will be significantly slower for training and inference.
            </p>
          </div>
          {config.cudaVersion === 'cpu' && (
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
              <Check className="h-3 w-3" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
