import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import WebTerminal from '../components/WebTerminal';
import { type ShellEvent, SHELL_EVENT_TYPES } from '../components/ShellIntegration';
import { Button } from '../components/ui/button';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { cn } from '../utils/cn';

interface InstallStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'success' | 'error';
}

interface InstallState {
  isExecuting: boolean;
  currentStepId: string | null;
  currentCommandIndex: number;
  currentStepIndex: number;
  totalSteps: number;
  status: 'idle' | 'running' | 'success' | 'failed';
}

interface NextStep {
  step_id: string;
  step_index: number;
  total_steps: number;
  command_index: number;
  command: string;
  name: string;
}

export function EnvironmentInstallationPage() {
  const { envId } = useParams<{ envId: string }>();
  const navigate = useNavigate();

  const [ptySessionId, setPtySessionId] = useState<string>('');
  const [steps, setSteps] = useState<InstallStep[]>([]);
  const [installState, setInstallState] = useState<InstallState>({
    isExecuting: false,
    currentStepId: null,
    currentCommandIndex: 0,
    currentStepIndex: 0,
    totalSteps: 0,
    status: 'idle',
  });
  const [firstCommand, setFirstCommand] = useState<NextStep | null>(null);
  const [waitingForPrompt, setWaitingForPrompt] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1. Start installation
  useEffect(() => {
    if (!envId) {
      setError('No environment ID provided');
      setInstallState((prev) => ({ ...prev, status: 'failed' }));
      return;
    }

    const abortController = new AbortController();

    const startInstallation = async () => {
      try {
        console.log(`[Installation] Starting installation for env: ${envId}`);
        const response = await fetch(`/api/environments/${envId}/installation/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error('Failed to start installation');
        }

        const { session_id, plan } = await response.json();
        console.log(`[Installation] Received session_id: ${session_id}`);
        setPtySessionId(session_id);

        // Extract steps from plan
        const steps: InstallStep[] = plan.steps.map(
          (step: { id: string; name: string }, index: number) => ({
            id: step.id,
            name: step.name,
            status: index === 0 ? 'running' : 'pending',
          }),
        );
        setSteps(steps);

        // Get first command from first step
        const firstStep = plan.steps[0];
        const firstCommand = {
          step_id: firstStep.id,
          step_index: 0,
          total_steps: plan.steps.length,
          command_index: 0,
          command: firstStep.commands[0] || '',
          name: firstStep.name,
        };
        setFirstCommand(firstCommand);
        setWaitingForPrompt(true); // Wait for initial prompt to execute first command

        setInstallState({
          isExecuting: false,
          currentStepId: firstStep.id,
          currentCommandIndex: 0,
          currentStepIndex: 0,
          totalSteps: plan.steps.length,
          status: 'running',
        });
      } catch (err) {
        // Ignore AbortError - this is expected when component unmounts
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        setError(err instanceof Error ? err.message : 'Unknown error');
        setInstallState((prev) => ({ ...prev, status: 'failed' }));
      }
    };

    startInstallation();

    return () => {
      abortController.abort();
      // Don't reset ref here - let the check in startInstallation handle it
    };
  }, [envId]);

  // 2. Execute command
  const executeCommand = async (stepId: string, commandIndex: number) => {
    if (!envId) return;

    const executionId = `${envId}:${crypto.randomUUID()}`; // Include envId prefix for cache cleanup

    try {
      await fetch(`/api/environments/${envId}/installation/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          step_id: stepId,
          command_index: commandIndex,
          execution_id: executionId,
        }),
      });

      setInstallState((prev) => ({ ...prev, isExecuting: true }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute command');
    }
  };

  // 3. Handle shell events
  const handleShellEvent = async (event: ShellEvent) => {
    if (!envId) return;

    const exitCode =
      event.type === SHELL_EVENT_TYPES.COMMAND_FINISHED ? event.exitCode : undefined;
    console.log(
      '[Shell Event]',
      event.type,
      'exitCode:',
      exitCode,
      'waitingForPrompt:',
      waitingForPrompt,
      'isExecuting:',
      installState.isExecuting,
    );

    // Handle prompt_start - execute next command when shell is ready
    if (event.type === SHELL_EVENT_TYPES.PROMPT_START) {
      console.log(
        '[Shell Event] PROMPT_START received, waitingForPrompt:',
        waitingForPrompt,
        'firstCommand:',
        !!firstCommand,
      );
      if (waitingForPrompt) {
        setWaitingForPrompt(false);
        if (firstCommand) {
          console.log('[Shell Event] Executing first command:', firstCommand.step_id);
          executeCommand(firstCommand.step_id, firstCommand.command_index);
          setFirstCommand(null);
        }
      }
      return;
    }

    // Handle command_finished - report result and prepare for next command
    if (event.type === SHELL_EVENT_TYPES.COMMAND_FINISHED) {
      console.log(
        '[Shell Event] COMMAND_FINISHED, isExecuting:',
        installState.isExecuting,
        'exitCode:',
        event.exitCode,
      );
      if (!installState.isExecuting) {
        console.log('[Shell Event] Ignoring COMMAND_FINISHED - not executing');
        return;
      }

      setInstallState((prev) => ({ ...prev, isExecuting: false }));

      const executionId = `${envId}:${crypto.randomUUID()}`; // Generate unique execution ID for result reporting

      try {
        const response = await fetch(
          `/api/environments/${envId}/installation/execute`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              step_id: installState.currentStepId,
              command_index: installState.currentCommandIndex,
              exit_code: event.exitCode,
              execution_id: executionId,
            }),
          },
        );

        if (!response.ok) {
          throw new Error('Failed to report command result');
        }

        const result = await response.json();

        // Note: Duplicate requests now return the original cached response,
        // so we don't need special handling for "duplicate" status anymore

        if (result.status === 'already_executing') {
          // Command is already being executed, ignore this request
          console.debug('Command is already executing, ignoring duplicate request');
          return;
        }

        if (result.status === 'next') {
          const nextStep: NextStep = result.next_step;
          console.log(
            '[Installation] Got next step:',
            nextStep.name,
            'command_index:',
            nextStep.command_index,
          );

          // Update steps status when step changes
          if (nextStep.step_id !== installState.currentStepId) {
            setSteps((prevSteps) =>
              prevSteps.map((step, index) => {
                if (index === installState.currentStepIndex) {
                  return { ...step, status: 'success' as const };
                } else if (index === nextStep.step_index) {
                  return { ...step, status: 'running' as const };
                }
                return step;
              }),
            );
          }

          setInstallState((prev) => ({
            ...prev,
            currentStepId: nextStep.step_id,
            currentCommandIndex: nextStep.command_index,
            currentStepIndex: nextStep.step_index,
          }));

          // Execute next command immediately without waiting for PROMPT_START
          // The backend has already prepared the command, we should execute it
          console.log(
            '[Installation] Executing next command immediately:',
            nextStep.step_id,
            nextStep.command_index,
          );
          executeCommand(nextStep.step_id, nextStep.command_index);
        } else if (result.status === 'completed') {
          // Mark final step as success
          setSteps((prevSteps) =>
            prevSteps.map((step, index) =>
              index === installState.currentStepIndex
                ? { ...step, status: 'success' as const }
                : step,
            ),
          );
          setInstallState((prev) => ({ ...prev, status: 'success' }));
        } else if (result.status === 'failed') {
          // Mark current step as error
          setSteps((prevSteps) =>
            prevSteps.map((step, index) =>
              index === installState.currentStepIndex
                ? { ...step, status: 'error' as const }
                : step,
            ),
          );
          setError(result.error || 'Installation failed');
          setInstallState((prev) => ({ ...prev, status: 'failed' }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setInstallState((prev) => ({ ...prev, status: 'failed' }));
      }
    }
  };

  const handleBackToList = () => {
    navigate('/environments');
  };

  const handleRetry = () => {
    window.location.reload();
  };

  const runningStep = steps.find((s) => s.status === 'running');

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <h1 className="text-content-primary text-2xl font-bold">
          Environment Installation
        </h1>
        <p className="text-content-secondary">Installing environment: {envId}</p>
      </div>

      {/* Step Progress Indicator */}
      <div className="bg-surface-secondary border-border-default overflow-x-auto rounded-lg border p-6">
        {steps.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
              <span className="text-content-secondary">
                Preparing installation steps...
              </span>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2">
            {steps.map((step, index) => {
              const isPending = step.status === 'pending';
              const isRunning = step.status === 'running';
              const isSuccess = step.status === 'success';
              const isError = step.status === 'error';

              return (
                <div key={step.id} className="flex items-center">
                  {/* Step indicator */}
                  <div className="flex flex-col items-center gap-2">
                    <div
                      className={cn(
                        'flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all',
                        isPending && 'border-border-default bg-surface-primary',
                        isRunning && 'border-blue-600 bg-blue-50 dark:bg-blue-950',
                        isSuccess && 'border-green-600 bg-green-50 dark:bg-green-950',
                        isError && 'border-red-600 bg-red-50 dark:bg-red-950',
                      )}
                    >
                      {isPending && (
                        <Circle className="text-content-tertiary h-5 w-5" />
                      )}
                      {isRunning && (
                        <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                      )}
                      {isSuccess && (
                        <CheckCircle2 className="text-success-icon h-5 w-5" />
                      )}
                      {isError && <XCircle className="text-error-icon h-5 w-5" />}
                    </div>
                    <div className="text-center">
                      <div
                        className={cn(
                          'max-w-[120px] truncate text-xs font-medium',
                          isPending && 'text-content-tertiary',
                          isRunning && 'text-blue-600',
                          isSuccess && 'text-green-600',
                          isError && 'text-red-600',
                        )}
                        title={step.name}
                      >
                        {step.name}
                      </div>
                    </div>
                  </div>

                  {/* Connector line */}
                  {index < steps.length - 1 && (
                    <div
                      className={cn(
                        'mx-2 h-0.5 w-8 flex-shrink-0 transition-all lg:w-16',
                        isSuccess ? 'bg-green-600' : 'bg-border-default',
                      )}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Terminal Output */}
      <div className="bg-surface-secondary border-border-default overflow-hidden rounded-lg border">
        <div className="border-border-default bg-surface-secondary/50 flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <div className="h-3 w-3 rounded-full bg-yellow-500" />
              <div className="h-3 w-3 rounded-full bg-green-500" />
            </div>
            <span className="text-content-primary ml-2 text-sm font-medium">
              Terminal
            </span>
          </div>
          {runningStep && (
            <span className="text-content-secondary text-xs">
              Running: {runningStep.name}
            </span>
          )}
        </div>
        <div className="h-[500px] w-full bg-[#1e1e1e]">
          {ptySessionId ? (
            <WebTerminal sessionId={ptySessionId} onShellEvent={handleShellEvent} />
          ) : (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="border-t bg-red-50 px-6 py-4 dark:bg-red-950/20">
          <div className="flex items-start gap-3">
            <XCircle className="h-5 w-5 flex-shrink-0 text-red-600 dark:text-red-400" />
            <div className="flex-1">
              <h3 className="font-medium text-red-900 dark:text-red-100">
                Installation Error
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Footer Actions */}
      <div className="bg-card border-t px-6 py-4">
        <div className="flex justify-end gap-3">
          {installState.status === 'success' ? (
            <Button
              onClick={handleBackToList}
              className="bg-success-surface text-success-content hover:bg-success-surface/90"
            >
              Done
            </Button>
          ) : installState.status === 'failed' ? (
            <>
              <Button variant="secondary" onClick={handleBackToList}>
                Cancel
              </Button>
              <Button variant="danger" onClick={handleRetry}>
                Retry
              </Button>
            </>
          ) : (
            <Button variant="secondary" disabled>
              Installing...
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
