import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { useWizardStore } from '../../stores/environment-wizard-store';
import { AdvancedStepCard } from './components/AdvancedStepCard';

interface AdvancedStep {
  id: string;
  name: string;
  comment: string | null;
  commands: string[];
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

export function AdvancedInstallationPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { config } = useWizardStore();
  const [steps, setSteps] = useState<AdvancedStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [envId, setEnvId] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorDialog, setErrorDialog] = useState<{ isOpen: boolean; message: string }>({ isOpen: false, message: '' });

  useEffect(() => {
    const abortController = new AbortController();

    const fetchSteps = async () => {
      setLoading(true);
      try {
        // Generate and store environment ID for consistency
        const generatedEnvId = crypto.randomUUID();
        setEnvId(generatedEnvId);

        // Construct EnvironmentConfig using stored repository URL
        const envConfig = {
          id: generatedEnvId, // Use generated environment ID for consistency
          name: config.envName || 'lerobot-env',
          display_name: config.friendlyName || 'LeRobot Environment',
          repo_id: config.repositoryId,
          repo_url: config.repositoryUrl,
          ref: config.lerobotVersion,
          python_version: config.pythonVersion,
          torch_version: config.torchVersion || '2.4.0',
          torchvision_version: config.torchvisionVersion || '',
          torchaudio_version: config.torchaudioVersion || '',
          // cuda_version: null means CPU-only, 'auto' means auto-detect, otherwise it's the CUDA version
          cuda_version:
            config.cudaVersion === 'auto' || config.cudaVersion === 'cpu'
              ? null
              : config.cudaVersion,
          extras: config.extras,
          status: 'pending',
        };

        // 3. Generate steps from backend (with current language)
        const currentLang = i18n.language.split('-')[0]; // e.g., 'zh-CN' -> 'zh'
        const stepsResponse = await fetch(
          `/api/environments/generate-steps?lang=${encodeURIComponent(currentLang)}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ env_config: envConfig }),
            signal: abortController.signal,
          },
        );

        if (!stepsResponse.ok) {
          const body = await stepsResponse.text().catch(() => '');
          setError(body || 'wizard.advanced.failedToLoadSteps');
          setLoading(false);
          return;
        }

        const data = await stepsResponse.json();

        // Map backend steps to frontend model
        const mappedSteps: AdvancedStep[] = data.steps.map(
          (s: {
            id: string;
            name: string;
            comment: string | null;
            commands: string[];
          }) => ({
            id: s.id,
            name: s.name,
            comment: s.comment,
            commands: s.commands,
            status: 'pending',
            logs: [],
          }),
        );

        if (mappedSteps.length === 0) {
          // No steps generated for this configuration
          setSteps([]);
          setError('wizard.advanced.noSteps');
          setLoading(false);
          return;
        }

        setError(null);
        setSteps(mappedSteps);
        if (mappedSteps.length > 0) {
          setExpandedStep(mappedSteps[0].id);
        }
      } catch (error) {
        // Ignore AbortError - this is expected when component unmounts
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load installation steps:', error);
        setError('wizard.advanced.failedToLoadSteps');
      } finally {
        setLoading(false);
      }
    };

    fetchSteps();

    return () => {
      abortController.abort();
    };
  }, [config, i18n.language]);

  const handleCommandUpdate = (
    stepId: string,
    commandIndex: number,
    newValue: string,
  ) => {
    setSteps(
      steps.map((s) =>
        s.id === stepId
          ? {
              ...s,
              commands: s.commands.map((cmd, idx) =>
                idx === commandIndex ? newValue : cmd,
              ),
            }
          : s,
      ),
    );
  };

  const handleAddCommand = (stepId: string) => {
    setSteps(
      steps.map((s) => (s.id === stepId ? { ...s, commands: [...s.commands, ''] } : s)),
    );
  };

  const handleDeleteCommand = (stepId: string, commandIndex: number) => {
    setSteps(
      steps.map((s) =>
        s.id === stepId
          ? {
              ...s,
              commands: s.commands.filter((_, idx) => idx !== commandIndex),
            }
          : s,
      ),
    );
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-content-primary text-2xl font-bold">
            {t('wizard.advanced.title')}
          </h1>
          <p className="text-content-secondary">{t('wizard.advanced.subtitle')}</p>
        </div>
      </div>

      <div className="space-y-4">
        {error ? (
          <div className="rounded-md border border-error-border bg-error-surface px-4 py-3 text-sm text-error-content">
            {error.startsWith('wizard.') ? t(error as any) : error}
          </div>
        ) : (
          steps.map((step, index) => {
            const isExpanded = expandedStep === step.id;

            return (
              <AdvancedStepCard
                key={step.id}
                step={step}
                index={index}
                isExpanded={isExpanded}
                onToggle={() => setExpandedStep(isExpanded ? null : step.id)}
                onCommandUpdate={handleCommandUpdate}
                onAddCommand={handleAddCommand}
                onDeleteCommand={handleDeleteCommand}
              />
            );
          })
        )}
      </div>

      <div className="flex justify-between gap-4 pt-4">
        <Button variant="secondary" onClick={() => navigate('/environments')}>
          {t('wizard.buttons.cancel')}
        </Button>
        <div className="flex gap-4">
          <Button variant="ghost" onClick={() => navigate('/environments/new?step=6')}>
            {t('wizard.buttons.back')}
          </Button>
          <Button
            onClick={async () => {
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

                // Construct environment config
                const envConfig = {
                  id: envId,
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

                const currentLang = i18n.language.split('-')[0];

                // Generate idempotency key
                const idempotencyKey = crypto.randomUUID();

                // Filter out empty commands from steps
                const cleanedSteps = steps
                  .map((step) => ({
                    ...step,
                    commands: step.commands.filter((cmd) => cmd.trim() !== ''),
                  }))
                  .filter((step) => step.commands.length > 0);

                // Create environment with custom steps
                const response = await fetch(
                  `/api/environments/create?lang=${currentLang}`,
                  {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'Idempotency-Key': idempotencyKey,
                    },
                    body: JSON.stringify({
                      env_config: envConfig,
                      custom_steps: cleanedSteps, // Pass cleaned custom steps
                    }),
                  },
                );

                if (!response.ok) throw new Error('Failed to create environment');

                // Navigate to installation page with the new envId
                navigate(`/environments/${envId}/install`);
              } catch (error) {
                console.error('Failed to create environment:', error);
                setErrorDialog({ isOpen: true, message: t('environments.createError') });
              }
            }}
            className="bg-success-surface text-success-content hover:bg-success-surface/90"
          >
            {t('wizard.buttons.create')}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={errorDialog.isOpen}
        title={t('common.error')}
        message={errorDialog.message}
        confirmText={t('common.ok')}
        onConfirm={() => setErrorDialog({ isOpen: false, message: '' })}
        onCancel={() => setErrorDialog({ isOpen: false, message: '' })}
      />
    </div>
  );
}