
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ShellEvent, SHELL_EVENT_TYPES } from '../../../components/shell-integration';
import { InstallStep, InstallState, NextStep } from '../types';

export function useInstallation(envId: string | undefined) {
    const { t } = useTranslation();

    const [ptySessionId, setPtySessionId] = useState<string>('');
    const [envName, setEnvName] = useState<string>('');
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

    // React Strict Mode protection: prevent double initialization
    const hasStartedRef = useRef(false);

    // Timeout ref for "Wait for Prompt" safety fallback
    const promptTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Refs to access latest values in callbacks
    const waitingForPromptRef = useRef(waitingForPrompt);
    const firstCommandRef = useRef(firstCommand);

    // Pending result to be reported when prompt appears
    const pendingResultRef = useRef<{
        stepId: string;
        commandIndex: number;
        exitCode: number;
    } | null>(null);

    // Keep refs in sync with state
    useEffect(() => {
        waitingForPromptRef.current = waitingForPrompt;
    }, [waitingForPrompt]);

    useEffect(() => {
        firstCommandRef.current = firstCommand;
    }, [firstCommand]);

    // 1. Start installation
    useEffect(() => {
        if (!envId) {
            setError(t('wizard.installation.noEnvIdError'));
            setInstallState((prev) => ({ ...prev, status: 'failed' }));
            return;
        }

        // React Strict Mode protection: skip if already started
        if (hasStartedRef.current) {
            console.log(
                `[Installation] Already started for env: ${envId}, skipping duplicate`,
            );
            return;
        }
        hasStartedRef.current = true;

        const startInstallation = async () => {
            try {
                console.log(`[Installation] Starting installation for env: ${envId}`);
                const response = await fetch(`/api/environments/${envId}/installation/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });

                if (!response.ok) {
                    throw new Error('Failed to start installation');
                }

                const { session_id, plan, env_name } = await response.json();
                console.log(`[Installation] Received session_id: ${session_id}`);

                // Extract steps from plan
                const steps: InstallStep[] = plan.steps.map(
                    (step: { id: string; name: string }, index: number) => ({
                        id: step.id,
                        name: step.name,
                        status: index === 0 ? 'running' : 'pending',
                    }),
                );

                // Get first command from first step
                const firstStep = plan.steps[0];
                const firstCommandData = {
                    step_id: firstStep.id,
                    step_index: 0,
                    total_steps: plan.steps.length,
                    command_index: 0,
                    command: firstStep.commands[0] || '',
                    name: firstStep.name,
                };

                // IMPORTANT: Update refs BEFORE setting ptySessionId
                // because setPtySessionId triggers re-render and WebTerminal mount
                firstCommandRef.current = firstCommandData;
                waitingForPromptRef.current = true;
                console.log(
                    `[Installation] Refs set: waitingForPrompt=true, firstCommand=${firstCommandData.step_id}`,
                );

                // Now set all states - React may batch these
                setEnvName(env_name || envId || '');
                setSteps(steps);
                setFirstCommand(firstCommandData);
                setWaitingForPrompt(true);
                setInstallState({
                    isExecuting: false,
                    currentStepId: firstStep.id,
                    currentCommandIndex: 0,
                    currentStepIndex: 0,
                    totalSteps: plan.steps.length,
                    status: 'running',
                });

                // Set ptySessionId LAST - this triggers WebTerminal to mount
                setPtySessionId(session_id);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Unknown error');
                setInstallState((prev) => ({ ...prev, status: 'failed' }));
            }
        };

        startInstallation();

        // No cleanup needed - we use hasStartedRef to prevent duplicate calls
    }, [envId, t]);

    // 2. Execute command
    const executeCommand = async (stepId: string, commandIndex: number) => {
        if (!envId) return;

        const executionId = `${envId}:${crypto.randomUUID()}`; // Include envId prefix for cache cleanup

        try {
            console.log(
                `[Installation] Executing command: step=${stepId}, commandIndex=${commandIndex}, executionId=${executionId}`,
            );
            const response = await fetch(`/api/environments/${envId}/installation/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    step_id: stepId,
                    command_index: commandIndex,
                    execution_id: executionId,
                }),
            });

            if (!response.ok) {
                throw new Error(
                    `Execute command failed: ${response.status} ${response.statusText}`,
                );
            }

            const result = await response.json();
            console.log(`[Installation] Execute command response:`, result);

            setInstallState((prev) => ({ ...prev, isExecuting: true }));
        } catch (err) {
            console.error('[Installation] Execute command error:', err);
            setError(err instanceof Error ? err.message : 'Failed to execute command');
        }
    };

    // Helper to report execution result and handle next step
    const reportExecutionResult = async (
        stepId: string,
        commandIndex: number,
        exitCode: number,
    ) => {
        if (!envId) return;

        const executionId = `${envId}:${crypto.randomUUID()}`;

        try {
            const response = await fetch(`/api/environments/${envId}/installation/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    step_id: stepId,
                    command_index: commandIndex,
                    exit_code: exitCode,
                    execution_id: executionId,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to report command result');
            }

            const result = await response.json();

            if (result.status === 'already_executing') {
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

                // Execute next command immediately since we are at PROMPT_START
                console.log(
                    '[Installation] Executing next command:',
                    nextStep.step_id,
                    nextStep.command_index,
                );
                executeCommand(nextStep.step_id, nextStep.command_index);
            } else if (result.status === 'completed') {
                setSteps((prevSteps) =>
                    prevSteps.map((step, index) =>
                        index === installState.currentStepIndex
                            ? { ...step, status: 'success' as const }
                            : step,
                    ),
                );
                setInstallState((prev) => ({ ...prev, status: 'success' }));
            } else if (result.status === 'failed') {
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

        // Handle prompt_start - execute pending command or first command
        if (event.type === SHELL_EVENT_TYPES.PROMPT_START) {
            // Clear any pending safety timeout since prompt arrived
            if (promptTimeoutRef.current) {
                clearTimeout(promptTimeoutRef.current);
                promptTimeoutRef.current = null;
            }

            // Check if we have a pending result to report
            if (pendingResultRef.current) {
                console.log('[Shell Event] PROMPT_START: Reporting pending result');
                const { stepId, commandIndex, exitCode } = pendingResultRef.current;
                pendingResultRef.current = null;

                // Add stabilization delay based on OS
                // Windows needs explicit delay (~200ms) to ensure input pipe is ready.
                // Linux also needs delay (>100ms based on testing) to avoid swallowed commands.
                // We use 1000ms for all platforms to be extremely safe as per user request.
                const delay = 1000;

                setTimeout(async () => {
                    console.log(`[Shell Event] Reporting after prompt delay (${delay}ms)...`);
                    await reportExecutionResult(stepId, commandIndex, exitCode);
                }, delay);
                return;
            }

            // Check if we are waiting for prompt to start execution (First Load)
            if (waitingForPrompt) {
                console.log('[Shell Event] PROMPT_START received, executing first command');
                waitingForPromptRef.current = false;
                firstCommandRef.current = null;
                setWaitingForPrompt(false);
                if (firstCommand) {
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

            // Store result to report later (when PROMPT_START arrives OR Timeout fires)
            if (installState.currentStepId) {
                pendingResultRef.current = {
                    stepId: installState.currentStepId,
                    commandIndex: installState.currentCommandIndex,
                    exitCode: event.exitCode,
                };
                console.log('[Shell Event] Result stored, waiting for PROMPT_START...');

                // Set a safety timeout (e.g. 2000ms)
                // If PROMPT_START never arrives (e.g. Linux Starship issue), we force report
                if (promptTimeoutRef.current) clearTimeout(promptTimeoutRef.current);

                promptTimeoutRef.current = setTimeout(async () => {
                    console.log('[Shell Event] PROMPT_START Timeout! Forcing report.');
                    promptTimeoutRef.current = null;

                    if (pendingResultRef.current) {
                        const { stepId, commandIndex, exitCode } = pendingResultRef.current;
                        pendingResultRef.current = null;
                        await reportExecutionResult(stepId, commandIndex, exitCode);
                    }
                }, 2000);
            }
        }
    };

    return {
        ptySessionId,
        envName,
        steps,
        installState,
        error,
        handleShellEvent,
    };
}
