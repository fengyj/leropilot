import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Loader2, X, Plus } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { CodeEditor } from '../components/code-editor';
import { useWizardStore } from '../stores/environment-wizard-store';
import { cn } from '../utils/cn';

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

        if (!stepsResponse.ok) throw new Error('Failed to generate steps');
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
        {steps.map((step, index) => {
          const isExpanded = expandedStep === step.id;

          return (
            <Card
              key={step.id}
              className={cn(
                'transition-all',
                step.status === 'running' && 'border-blue-500 ring-1 ring-blue-500',
              )}
            >
              <div
                onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                onKeyDown={(e) =>
                  e.key === 'Enter' && setExpandedStep(isExpanded ? null : step.id)
                }
                role="button"
                tabIndex={0}
                className="border-border-default bg-surface-secondary/50 hover:bg-surface-secondary flex cursor-pointer items-center justify-between border-b p-4 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-content-primary font-medium">
                    {index + 1}. {step.name}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              {isExpanded && (
                <CardContent className="p-0">
                  <div className="divide-border-default grid grid-cols-1 divide-y">
                    {/* Comment */}
                    {step.comment && (
                      <div className="bg-surface-tertiary/50 border-border-default border-b p-4">
                        <p className="text-content-secondary text-sm leading-relaxed">
                          {step.comment}
                        </p>
                      </div>
                    )}
                    {/* Commands Editor */}
                    <div className="space-y-3 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-content-tertiary text-xs font-medium">
                          {t('wizard.advanced.commands')}
                        </span>
                      </div>

                      {step.commands.map((command, cmdIndex) => (
                        <div key={cmdIndex} className="flex items-start gap-2">
                          <div className="min-w-0 flex-1 space-y-1">
                            <label className="text-content-secondary text-xs font-medium">
                              {t('wizard.advanced.commandLabel', {
                                number: cmdIndex + 1,
                              })}
                            </label>
                            <CodeEditor
                              value={command}
                              onChange={(value) =>
                                handleCommandUpdate(step.id, cmdIndex, value)
                              }
                              language="shell"
                              height="auto"
                              minHeight="40px"
                              maxHeight="200px"
                              placeholder={t('wizard.advanced.commandPlaceholder')}
                            />
                          </div>
                          <button
                            onClick={() => handleDeleteCommand(step.id, cmdIndex)}
                            className="mt-6 rounded p-1 text-red-600 transition-colors hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/20"
                            title={t('wizard.advanced.deleteCommand')}
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      ))}

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleAddCommand(step.id)}
                        className="mt-2 w-full"
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        {t('wizard.advanced.addCommand')}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
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
                alert('Failed to create environment. Please try again.');
              }
            }}
            className="bg-success-surface text-success-content hover:bg-success-surface/90"
          >
            {t('wizard.buttons.create')}
          </Button>
        </div>
      </div>
    </div>
  );
}
