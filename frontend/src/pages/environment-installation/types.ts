export interface InstallStep {
    id: string;
    name: string;
    status: 'pending' | 'running' | 'success' | 'error';
}

export interface InstallState {
    isExecuting: boolean;
    currentStepId: string | null;
    currentCommandIndex: number;
    currentStepIndex: number;
    totalSteps: number;
    status: 'idle' | 'running' | 'success' | 'failed';
}

export interface NextStep {
    step_id: string;
    step_index: number;
    total_steps: number;
    command_index: number;
    command: string;
    name: string;
}
