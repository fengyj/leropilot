import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  EnvironmentInstallation,
  InstallStep,
} from '../components/environments/environment-installation';

import { useWizardStore } from '../stores/environment-wizard-store';

export function EnvironmentInstallationPage() {
  const { customSteps } = useWizardStore();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Initialize steps from customSteps or use default
  const initialSteps: InstallStep[] = useMemo(() => {
    if (customSteps && customSteps.length > 0) {
      return customSteps.map((step) => ({
        ...step,
        status: 'pending' as const,
        logs: [],
      }));
    }

    return [
      {
        id: 'git',
        name: 'git',
        command: 'git clone https://github.com/huggingface/lerobot && cd lerobot',
        status: 'pending',
        logs: [],
      },
      {
        id: 'venv',
        name: 'venv',
        command: 'python -m venv .venv && source .venv/bin/activate',
        status: 'pending',
        logs: [],
      },
      {
        id: 'torch',
        name: 'torch',
        command: 'pip install torch torchvision',
        status: 'pending',
        logs: [],
      },
      {
        id: 'lerobot',
        name: 'lerobot',
        command: 'pip install -e .',
        status: 'pending',
        logs: [],
      },
      {
        id: 'extras',
        name: 'extras',
        command: 'pip install -e .[dev]',
        status: 'pending',
        logs: [],
      },
    ];
  }, [customSteps]);

  const [steps, setSteps] = useState<InstallStep[]>(() => {
    const initial = [...initialSteps];
    initial[0].status = 'running';
    return initial;
  });

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isCancelled, setIsCancelled] = useState(false);

  // Simulate progress
  useEffect(() => {
    if (isCancelled) return;

    const timer = setInterval(() => {
      setSteps((prev) => {
        const newSteps = [...prev];
        const current = newSteps[currentStepIndex];

        if (current && current.status === 'running') {
          // Add logs
          current.logs = [
            ...current.logs,
            `[${new Date().toLocaleTimeString()}] Processing chunk ${Math.floor(Math.random() * 1000)}...`,
          ];

          // Randomly finish step
          if (Math.random() > 0.8) {
            current.status = 'success';
            current.logs.push('Step completed successfully.');

            // Start next step if available
            if (currentStepIndex < newSteps.length - 1) {
              setCurrentStepIndex((i) => i + 1);
              newSteps[currentStepIndex + 1].status = 'running';
            }
          }
        }

        return newSteps;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [currentStepIndex, isCancelled]);

  const handleComplete = () => {
    navigate('/environments');
  };

  const handleCancel = () => {
    if (window.confirm(t('wizard.installation.cancelConfirm'))) {
      setIsCancelled(true);
      // Mark current running step as error/cancelled
      setSteps((prev) =>
        prev.map((s) =>
          s.status === 'running'
            ? {
                ...s,
                status: 'error',
                logs: [...s.logs, 'Installation cancelled by user.'],
              }
            : s,
        ),
      );
    }
  };

  const handleRetry = () => {
    if (isCancelled) {
      // Reinstall: Clean up and start from beginning
      console.log('Cleaning up previous installation...');
      setIsCancelled(false);
      setSteps((prev) => prev.map((s) => ({ ...s, status: 'pending', logs: [] })));
      setCurrentStepIndex(0);

      // Trigger start
      setSteps((prev) => {
        const newSteps = [...prev];
        newSteps[0].status = 'running';
        return newSteps;
      });
    } else {
      // Retry: Resume from failed step
      setSteps((prev) => {
        const newSteps = [...prev];
        // Find first error step
        const errorIndex = newSteps.findIndex((s) => s.status === 'error');
        if (errorIndex !== -1) {
          newSteps[errorIndex].status = 'running';
          newSteps[errorIndex].logs = [];
          setCurrentStepIndex(errorIndex);
          // Reset subsequent steps
          for (let i = errorIndex + 1; i < newSteps.length; i++) {
            newSteps[i].status = 'pending';
            newSteps[i].logs = [];
          }
        }
        return newSteps;
      });
    }
  };

  const handleBack = () => {
    // Clean up if installation was started (cancelled or error)
    console.log('Cleaning up installation before navigating back...');
    navigate(-1);
  };

  return (
    <EnvironmentInstallation
      envName="lerobot-v0.4.1-cuda121"
      steps={steps}
      onComplete={handleComplete}
      onCancel={handleCancel}
      onRetry={handleRetry}
      onBack={handleBack}
      isCancelled={isCancelled}
    />
  );
}
