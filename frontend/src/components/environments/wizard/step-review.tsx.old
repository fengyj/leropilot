import { AlertTriangle, Terminal } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';

export function StepReview() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { config, detectedHardware } = useWizardStore();

  const getHardwareDisplay = () => {
    if (config.cudaVersion === 'cpu') {
      return 'CPU';
    }

    if (config.rocmVersion) {
      return `ROCm ${config.rocmVersion}`;
    }

    if (config.cudaVersion && config.cudaVersion !== 'auto') {
      return `CUDA ${config.cudaVersion}`;
    }

    if (config.cudaVersion === 'auto') {
      if (!detectedHardware) return 'Auto';

      if (detectedHardware.has_nvidia_gpu) {
        return `CUDA ${detectedHardware.detected_cuda || 'Detected'}`;
      }
      if (detectedHardware.has_amd_gpu) {
        return `ROCm ${detectedHardware.detected_rocm || 'Detected'}`;
      }
      if (detectedHardware.is_apple_silicon) {
        return 'Metal (Apple Silicon)';
      }
      return 'CPU';
    }

    return `CUDA ${config.cudaVersion}`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.review.title')}
        </h3>
        <p className="text-content-secondary text-sm">{t('wizard.review.subtitle')}</p>
      </div>

      <div className="border-border-default bg-surface-tertiary space-y-4 rounded-lg border p-4">
        <h4 className="text-content-primary font-medium">
          {t('wizard.review.summary')}
        </h4>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="text-content-tertiary">
            {t('wizard.nameConfig.friendlyName')}
          </div>
          <div className="text-content-primary font-medium">{config.friendlyName}</div>

          <div className="text-content-tertiary">
            {t('wizard.nameConfig.internalName')}
          </div>
          <div className="text-content-primary font-mono text-xs">{config.envName}</div>

          <div className="text-content-tertiary">{t('wizard.review.repository')}</div>
          <div className="text-content-primary">
            {config.repositoryName} ({config.lerobotVersion})
          </div>

          <div className="text-content-tertiary">{t('wizard.review.hardware')}</div>
          <div className="text-content-primary">{getHardwareDisplay()}</div>

          <div className="text-content-tertiary">{t('wizard.review.python')}</div>
          <div className="text-content-primary">{config.pythonVersion}</div>

          <div className="text-content-tertiary">{t('wizard.review.extras')}</div>
          <div className="text-content-primary">
            {config.extras.length > 0
              ? config.extras.join(', ')
              : t('wizard.review.none')}
          </div>
        </div>
      </div>

      <div className="border-warning-border bg-warning-surface flex gap-3 rounded-lg border p-4">
        <AlertTriangle className="text-warning-icon h-5 w-5 shrink-0" />
        <p className="text-warning-content text-sm">
          {t('wizard.review.internetWarning')}
        </p>
      </div>

      {/* Advanced Mode Link */}
      <div className="border-border-default rounded-lg border">
        <button
          onClick={() => navigate('/environments/advanced-install')}
          className="hover:bg-surface-secondary flex w-full items-center justify-between p-4 text-left transition-colors"
        >
          <div className="flex items-center gap-2">
            <Terminal className="text-content-secondary h-4 w-4" />
            <span className="text-content-primary text-sm font-medium">
              {t('wizard.review.advancedMode')}
            </span>
          </div>
          <div className="text-sm font-medium text-blue-600">
            {t('wizard.review.customize')} &gt;
          </div>
        </button>
      </div>
    </div>
  );
}
