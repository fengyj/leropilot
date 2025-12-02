import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
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

import { CodeEditor } from '../components/code-editor';

export function AdvancedInstallationPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { config, setCustomSteps } = useWizardStore();
  const [steps, setSteps] = useState<AdvancedStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    const fetchSteps = async () => {
      setLoading(true);
      try {
        // Construct EnvironmentConfig using stored repository URL
        const envConfig = {
          id: config.envName || 'new-env',
          name: config.envName || 'lerobot-env',
          display_name: config.friendlyName || 'LeRobot Environment',
          repo_id: config.repositoryId,
          repo_url: config.repositoryUrl,
          ref: config.lerobotVersion,
          python_version: config.pythonVersion,
          torch_version: '2.4.0', // Default placeholder, backend handles actual version
          cuda_version: config.cudaVersion === 'auto' ? null : config.cudaVersion,
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

  const handleCommandChange = (id: string, newCommand: string) => {
    setSteps(
      steps.map((s) => (s.id === id ? { ...s, commands: newCommand.split('\n') } : s)),
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
                    {/* Editor */}
                    <div className="p-4">
                      <div className="text-content-tertiary mb-2 flex items-center justify-between text-xs">
                        <span>{t('wizard.advanced.command')}</span>
                      </div>
                      <CodeEditor
                        value={step.commands.join('\n')}
                        onChange={(value) => handleCommandChange(step.id, value)}
                        language="shell"
                        readOnly={false}
                      />
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      <div className="flex justify-between gap-4 pt-4">
        <Button variant="ghost" onClick={() => navigate('/environments/new')}>
          {t('wizard.buttons.back')}
        </Button>
        <div className="flex gap-4">
          <Button variant="secondary" onClick={() => navigate('/environments')}>
            {t('wizard.buttons.cancel')}
          </Button>
          <Button
            onClick={() => {
              setCustomSteps(steps);
              navigate('/environments/install');
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
