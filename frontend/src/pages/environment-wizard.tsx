import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Check } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { useWizardStore } from '../stores/environment-wizard-store';
import { cn } from '../utils/cn';

// Step Components
import { StepRepoSelection } from '../components/environments/wizard/step-repo-selection';
import { StepVersionSelection } from '../components/environments/wizard/step-version-selection';
import { StepHardwareSelection } from '../components/environments/wizard/step-hardware-selection';
import { StepExtrasSelection } from '../components/environments/wizard/step-extras-selection';
import { StepNameConfig } from '../components/environments/wizard/step-name-config';
import { StepReview } from '../components/environments/wizard/step-review';

export function EnvironmentWizard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { step, setStep, reset } = useWizardStore();

  const STEPS = [
    { id: 1, title: t('wizard.steps.repo'), component: StepRepoSelection },
    { id: 2, title: t('wizard.steps.version'), component: StepVersionSelection },
    { id: 3, title: t('wizard.steps.hardware'), component: StepHardwareSelection },
    { id: 4, title: t('wizard.steps.extras'), component: StepExtrasSelection },
    { id: 5, title: t('wizard.steps.name'), component: StepNameConfig },
    { id: 6, title: t('wizard.steps.review'), component: StepReview },
  ];

  // Initialize step from URL on mount
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (stepParam) {
      const stepNum = parseInt(stepParam, 10);
      if (!isNaN(stepNum) && stepNum >= 1 && stepNum <= STEPS.length) {
        setStep(stepNum);
      } else {
        setSearchParams({ step: '1' }, { replace: true });
        setStep(1);
      }
    } else {
      setSearchParams({ step: String(step) }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update URL when step changes (from user interaction)
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (stepParam !== String(step)) {
      setSearchParams({ step: String(step) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const handleNext = () => {
    if (step < STEPS.length) {
      setStep(step + 1);
    } else {
      // Navigate to installation page
      // Note: reset() will be called when user returns to wizard or when installation completes
      navigate('/environments/install');
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    } else {
      navigate('/environments');
      reset();
    }
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
          <Button variant="ghost" onClick={handleBack}>
            {step === 1 ? t('wizard.buttons.cancel') : t('wizard.buttons.back')}
          </Button>
          <Button onClick={handleNext}>
            {step === STEPS.length
              ? t('wizard.buttons.create')
              : t('wizard.buttons.next')}
            {step < STEPS.length && <ChevronRight className="ml-2 h-4 w-4" />}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
