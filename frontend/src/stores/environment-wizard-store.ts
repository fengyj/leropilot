import { create } from 'zustand';

interface WizardConfig {
  repositoryId: string;
  lerobotVersion: string;
  pythonVersion: string;
  cudaVersion: string;
  extras: string[];
  envName: string;
  friendlyName: string;
}

export interface AdvancedStep {
  id: string;
  name: string;
  command: string;
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

interface WizardState {
  step: number;
  config: WizardConfig;
  customSteps: AdvancedStep[];
  setStep: (step: number) => void;
  updateConfig: (updates: Partial<WizardConfig>) => void;
  setCustomSteps: (steps: AdvancedStep[]) => void;
  reset: () => void;
}

const INITIAL_CONFIG: WizardConfig = {
  repositoryId: 'official',
  lerobotVersion: 'v0.4.1',
  pythonVersion: '3.10',
  cudaVersion: 'auto',
  extras: [],
  envName: '',
  friendlyName: '',
};

export const useWizardStore = create<WizardState>((set) => ({
  step: 1,
  config: INITIAL_CONFIG,
  customSteps: [],
  setStep: (step) => set({ step }),
  updateConfig: (updates) =>
    set((state) => ({ config: { ...state.config, ...updates } })),
  setCustomSteps: (steps) => set({ customSteps: steps }),
  reset: () => set({ step: 1, config: INITIAL_CONFIG, customSteps: [] }),
}));
