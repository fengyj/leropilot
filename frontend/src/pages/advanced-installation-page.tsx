import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Play,
  RotateCcw,
  Terminal,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Loader2,
  Circle,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { useWizardStore } from '../stores/environment-wizard-store';
import { cn } from '../utils/cn';

interface AdvancedStep {
  id: string;
  name: string;
  command: string;
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

import { CodeEditor, LogViewer } from '../components/code-editor';

export function AdvancedInstallationPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { config, setCustomSteps } = useWizardStore();

  // Generate initial steps from config
  const initialSteps: AdvancedStep[] = useMemo(
    () => [
      {
        id: 'git',
        name: `Clone Repository (${config.repositoryId})`,
        command: `git clone ${config.repositoryId === 'official' ? 'https://github.com/huggingface/lerobot' : '...'} lerobot\ncd lerobot && git checkout ${config.lerobotVersion}`,
        status: 'pending',
        logs: [],
      },
      {
        id: 'venv',
        name: `Create Virtual Environment (Python ${config.pythonVersion})`,
        command: `uv venv .venv --python ${config.pythonVersion}\nsource .venv/bin/activate`,
        status: 'pending',
        logs: [],
      },
      {
        id: 'torch',
        name: `Install PyTorch (${config.cudaVersion})`,
        command: `uv pip install torch torchvision --index-url https://download.pytorch.org/whl/${config.cudaVersion === 'auto' ? 'cu121' : config.cudaVersion}`,
        status: 'pending',
        logs: [],
      },
      {
        id: 'lerobot',
        name: 'Install LeRobot & Extras',
        command: `uv pip install -e .[${config.extras.join(',')}]`,
        status: 'pending',
        logs: [],
      },
    ],
    [
      config.repositoryId,
      config.lerobotVersion,
      config.pythonVersion,
      config.cudaVersion,
      config.extras,
    ],
  );

  const [steps, setSteps] = useState<AdvancedStep[]>(initialSteps);
  const [expandedStep, setExpandedStep] = useState<string | null>(
    initialSteps[0]?.id || null,
  );

  const handleCommandChange = (id: string, newCommand: string) => {
    setSteps(steps.map((s) => (s.id === id ? { ...s, command: newCommand } : s)));
  };

  const runStep = async (id: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: 'running', logs: [] } : s)),
    );
    setExpandedStep(id);

    // Simulate execution
    const step = steps.find((s) => s.id === id);
    if (!step) return;

    const lines = step.command.split('\n');
    for (const line of lines) {
      await new Promise((r) => setTimeout(r, 800));
      setSteps((prev) =>
        prev.map((s) => {
          if (s.id === id) {
            return { ...s, logs: [...s.logs, `> ${line}`, '... done'] };
          }
          return s;
        }),
      );
    }

    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: 'success' } : s)),
    );

    // Auto expand next
    const index = steps.findIndex((s) => s.id === id);
    if (index < steps.length - 1) {
      setExpandedStep(steps[index + 1].id);
    }
  };

  const resetStep = (id: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: 'pending', logs: [] } : s)),
    );
  };

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
                  {step.status === 'pending' && (
                    <Circle className="text-content-tertiary h-5 w-5" />
                  )}
                  {step.status === 'running' && (
                    <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                  )}
                  {step.status === 'success' && (
                    <CheckCircle2 className="text-success-icon h-5 w-5" />
                  )}
                  {step.status === 'error' && (
                    <XCircle className="text-error-icon h-5 w-5" />
                  )}

                  <span className="text-content-primary font-medium">
                    {index + 1}. {step.name}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {step.status !== 'running' && (
                    <>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => runStep(step.id)}
                        className="text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:hover:bg-blue-900/20"
                      >
                        <Play className="mr-1 h-3 w-3" />
                        {t('wizard.advanced.run')}
                      </Button>
                      {step.status !== 'pending' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => resetStep(step.id)}
                        >
                          <RotateCcw className="h-3 w-3" />
                        </Button>
                      )}
                    </>
                  )}
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
                    {/* Editor */}
                    <div className="p-4">
                      <div className="text-content-tertiary mb-2 flex items-center justify-between text-xs">
                        <span>{t('wizard.advanced.command')}</span>
                      </div>
                      <CodeEditor
                        value={step.command}
                        onChange={(value) => handleCommandChange(step.id, value)}
                        language="shell"
                        readOnly={step.status === 'running'}
                      />
                    </div>

                    {/* Logs */}
                    <div className="p-4">
                      <div className="text-content-tertiary mb-2 flex items-center gap-2 text-xs">
                        <Terminal className="h-3 w-3" />
                        <span>{t('wizard.advanced.output')}</span>
                      </div>
                      <LogViewer logs={step.logs} autoScroll={true} />
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
