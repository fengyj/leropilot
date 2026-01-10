import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Check } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardFooter } from '../../components/ui/card';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { useWizardStore } from '../../stores/environment-wizard-store';
import { cn } from '../../utils/cn';

// Step Components
import { StepRepoSelection } from './components/step-repo-selection';
import { StepVersionSelection } from './components/step-version-selection';
import { StepHardwareSelection } from './components/step-hardware-selection';
import { StepExtrasSelection } from './components/step-extras-selection';
import { StepNameConfig } from './components/step-name-config';
import { StepReview } from './components/step-review';

export function EnvironmentWizard() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { step, setStep, reset, config } = useWizardStore();
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  const STEPS = [
    { id: 1, title: t('wizard.steps.repo'), component: StepRepoSelection },
    { id: 2, title: t('wizard.steps.version'), component: StepVersionSelection },
    { id: 3, title: t('wizard.steps.hardware'), component: StepHardwareSelection },
    { id: 4, title: t('wizard.steps.extras'), component: StepExtrasSelection },
    { id: 5, title: t('wizard.steps.name'), component: StepNameConfig },
    { id: 6, title: t('wizard.steps.review'), component: StepReview },
  ];

  // Reset wizard state on mount to ensure fresh start (unless navigating to specific step)
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (!stepParam) {
      reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Warn user before leaving page (browser refresh/close)
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Validation logic for each step
  const isStepValid = () => {
    switch (step) {
      case 1: // Repo
        return !!config.repositoryId;
      case 2: // Version
        return !!config.lerobotVersion;
      case 3: // Compute
        return (
          !!config.torchVersion && !!config.cudaVersion && config.cudaVersion !== 'auto'
        );
      case 4: // Extras
        return true;
      case 5: // Name
        // Check for empty and valid format (lowercase alphanumeric, dot, dash, underscore)
        return (
          !!config.friendlyName &&
          !!config.envName &&
          /^[a-z0-9._-]+$/.test(config.envName)
        );
      default:
        return true;
    }
  };

  // Initialize step from URL on mount and handle browser navigation
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (stepParam) {
      const stepNum = parseInt(stepParam, 10);
      if (!isNaN(stepNum) && stepNum >= 1 && stepNum <= STEPS.length) {
        if (stepNum !== step) {
          setStep(stepNum);
        }
      } else {
        setSearchParams({ step: '1' }, { replace: true });
        setStep(1);
      }
    } else {
      setSearchParams({ step: String(step) }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Update URL when step changes (from user interaction)
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (stepParam !== String(step)) {
      setSearchParams({ step: String(step) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const handleNext = async () => {
    if (step < STEPS.length) {
      setStep(step + 1);
    } else {
      // Create environment and navigate to installation page
      try {
        // Resolve hardware accelerator version
        let resolvedCudaVersion: string | undefined =
          config.cudaVersion === 'auto' ? undefined : config.cudaVersion;
        let resolvedRocmVersion: string | undefined = config.rocmVersion;

        // If CPU selected explicitly
        if (config.cudaVersion === 'cpu') {
          resolvedCudaVersion = undefined;
          resolvedRocmVersion = undefined;
        }

        const newEnvId = crypto.randomUUID();

        const envConfig = {
          id: newEnvId,
          name: config.envName,
          display_name: config.friendlyName,
          repo_id: config.repositoryId,
          repo_url: config.repositoryUrl,
          ref: config.lerobotVersion,
          python_version: config.pythonVersion,
          torch_version: config.torchVersion || '',
          torchvision_version: config.torchvisionVersion,
          torchaudio_version: config.torchaudioVersion,
          cuda_version: resolvedCudaVersion,
          rocm_version: resolvedRocmVersion,
          extras: config.extras,
          status: 'pending',
        };

        const currentLang = i18n.language.split('-')[0]; // e.g., 'zh-CN' -> 'zh'

        // Generate idempotency key to prevent duplicate creation
        const idempotencyKey = crypto.randomUUID();

        // Create environment
        const response = await fetch(`/api/environments/create?lang=${currentLang}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotencyKey,
          },
          body: JSON.stringify({
            env_config: envConfig,
            custom_steps: null, // No custom steps from wizard
          }),
        });

        if (!response.ok) throw new Error('Failed to create environment');

        // Navigate to v2 installation page with the new envId
        navigate(`/environments/${newEnvId}/install`);
      } catch (error) {
        console.error('Failed to create environment:', error);
        alert('Failed to create environment. Please try again.');
      }
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  const handleCancel = () => {
    setShowCancelDialog(true);
  };

  const handleConfirmCancel = () => {
    setShowCancelDialog(false);
    reset();
    navigate('/environments');
  };

  const handleCancelDialog = () => {
    setShowCancelDialog(false);
  };

  const CurrentStepComponent = STEPS[step - 1].component;

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-8">
      {/* Header */}
      <div>
        <h1 className="text-content-primary text-2xl font-bold">{t('wizard.title')}</h1>
        <p className="text-content-secondary">{t('wizard.subtitle')}</p>
      </div>

      {/* Progress Steps */}
      <div className="relative flex justify-between px-2">
        <div className="bg-border-default absolute top-1/2 left-0 -z-10 h-0.5 w-full -translate-y-1/2" />
        {STEPS.map((s) => (
          <div
            key={s.id}
            className="bg-surface-primary flex flex-col items-center gap-2 px-2"
          >
            <div
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors',
                step >= s.id
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-border-default bg-surface-secondary text-content-tertiary',
              )}
            >
              {step > s.id ? <Check className="h-4 w-4" /> : s.id}
            </div>
            <span
              className={cn(
                'hidden text-xs font-medium sm:block',
                step >= s.id
                  ? 'text-blue-600 dark:text-blue-500'
                  : 'text-content-tertiary',
              )}
            >
              {s.title}
            </span>
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card className="flex min-h-[400px] flex-col">
        <CardContent className="flex-1 pt-6">
          <CurrentStepComponent />
        </CardContent>
        <CardFooter className="border-border-default flex justify-between border-t p-6">
          {/* Left: Cancel button */}
          <Button variant="secondary" onClick={handleCancel}>
            {t('wizard.buttons.cancel')}
          </Button>

          {/* Right: Navigation buttons */}
          <div className="flex gap-3">
            {step > 1 && (
              <Button variant="ghost" onClick={handleBack}>
                {t('wizard.buttons.back')}
              </Button>
            )}
            <Button onClick={handleNext} disabled={!isStepValid()}>
              {step === STEPS.length
                ? t('wizard.buttons.create')
                : t('wizard.buttons.next')}
              {step < STEPS.length && <ChevronRight className="ml-2 h-4 w-4" />}
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Cancel Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showCancelDialog}
        title={t('wizard.cancelDialog.title')}
        message={t('wizard.cancelDialog.message')}
        confirmText={t('wizard.cancelDialog.confirm')}
        cancelText={t('wizard.cancelDialog.stay')}
        onConfirm={handleConfirmCancel}
        onCancel={handleCancelDialog}
        variant="danger"
      />
    </div>
  );
}
