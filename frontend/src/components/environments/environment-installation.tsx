import { useState, useMemo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckCircle2,
  Circle,
  Loader2,
  Terminal,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { cn } from '../../utils/cn';
import { CodeEditor, LogViewer } from '../code-editor';

export interface InstallStep {
  id: string;
  name: string;
  command?: string;
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

interface EnvironmentInstallationProps {
  envName: string;
  steps: InstallStep[];
  onComplete?: () => void;
  onError?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  onBack?: () => void;
  isCancelled?: boolean;
}

export function EnvironmentInstallation({
  envName,
  steps,
  onComplete,
  onCancel,
  onRetry,
  onBack,
  isCancelled = false,
}: EnvironmentInstallationProps) {
  const { t } = useTranslation();
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  // Compute which step should be auto-expanded
  const autoExpandedStep = useMemo(() => {
    const runningStep = steps.find((s) => s.status === 'running');
    return runningStep?.id || null;
  }, [steps]);

  // Auto-expand running step (defer setState to avoid lint error)
  useEffect(() => {
    if (autoExpandedStep && expandedStep !== autoExpandedStep) {
      queueMicrotask(() => {
        setExpandedStep(autoExpandedStep);
      });
    }
  }, [autoExpandedStep, expandedStep]);

  const progress = Math.round(
    (steps.filter((s) => s.status === 'success').length / steps.length) * 100,
  );
  const hasError = steps.some((s) => s.status === 'error');
  const isComplete = steps.length > 0 && steps.every((s) => s.status === 'success');

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <h1 className="text-content-primary text-2xl font-bold">
          {t('wizard.installation.title')}
        </h1>
        <p className="text-content-secondary">
          {t('wizard.installation.subtitle', { envName })}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-content-secondary">
            {t('wizard.installation.progress')}
          </span>
          <span className="text-content-primary font-medium">{progress}%</span>
        </div>
        <div className="bg-surface-tertiary h-2 w-full overflow-hidden rounded-full">
          <div
            className="h-full bg-blue-600 transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="space-y-4">
        {steps.map((step, index) => {
          const isExpanded = expandedStep === step.id;
          const isPending = step.status === 'pending';
          const isRunning = step.status === 'running';
          const isSuccess = step.status === 'success';
          const isError = step.status === 'error';

          return (
            <Card
              key={step.id}
              className={cn(
                'transition-all',
                isRunning && 'border-blue-500 ring-1 ring-blue-500',
              )}
            >
              <div className="border-border-default bg-surface-secondary/50 flex items-center justify-between border-b p-4">
                <div
                  className="flex cursor-pointer items-center gap-3"
                  onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                  onKeyDown={(e) =>
                    e.key === 'Enter' && setExpandedStep(isExpanded ? null : step.id)
                  }
                  role="button"
                  tabIndex={0}
                >
                  {isPending && <Circle className="text-content-tertiary h-5 w-5" />}
                  {isRunning && (
                    <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                  )}
                  {isSuccess && <CheckCircle2 className="text-success-icon h-5 w-5" />}
                  {isError && <XCircle className="text-error-icon h-5 w-5" />}

                  <span
                    className={cn(
                      'font-medium',
                      isPending && 'text-content-secondary',
                      isRunning && 'text-blue-600',
                      isSuccess && 'text-content-primary',
                      isError && 'text-error-content',
                    )}
                  >
                    {index + 1}.{' '}
                    {t(`wizard.installation.stepsList.${step.name}`) || step.name}
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
                    {/* Command View (Read Only) */}
                    <div className="p-4">
                      <div className="text-content-tertiary mb-2 flex items-center justify-between text-xs">
                        <span>{t('wizard.advanced.command')}</span>
                      </div>
                      <CodeEditor
                        value={step.command || ''}
                        language="shell"
                        readOnly={true}
                      />
                    </div>

                    {/* Logs */}
                    <div className="p-4">
                      <div className="text-content-tertiary mb-2 flex items-center gap-2 text-xs">
                        <Terminal className="h-3 w-3" />
                        <span>{t('wizard.installation.logs')}</span>
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

      {/* Actions */}
      <div className="flex justify-between gap-4">
        {isCancelled ? (
          <Button variant="ghost" onClick={onBack}>
            {t('wizard.buttons.back')}
          </Button>
        ) : (
          <div />
        )}

        <div className="flex gap-4">
          {hasError || isCancelled ? (
            <Button variant="danger" onClick={onRetry}>
              {isCancelled
                ? t('wizard.installation.reinstall')
                : t('wizard.installation.retry')}
            </Button>
          ) : isComplete ? (
            <Button
              onClick={onComplete}
              className="bg-success-surface text-success-content hover:bg-success-surface/90"
            >
              {t('wizard.buttons.done')}
            </Button>
          ) : (
            <>
              <Button variant="secondary" onClick={onCancel}>
                {t('wizard.buttons.cancel')}
              </Button>
              <Button variant="secondary" disabled>
                {t('wizard.installation.installing')}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
