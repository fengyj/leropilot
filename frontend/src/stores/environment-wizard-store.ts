import { create } from 'zustand';

interface WizardState {
  step: number;
  config: {
    repoType: 'official' | 'custom';
    repoUrl: string;
    version: string;
    pythonVersion: string;
    torchVersion: string;
    selectedRobots: string[];
  };
  setStep: (step: number) => void;
  updateConfig: (updates: Partial<WizardState['config']>) => void;
  reset: () => void;
}

export const useWizardStore = create<WizardState>((set) => ({
  step: 1,
  config: {
    repoType: 'official',
    repoUrl: 'https://github.com/huggingface/lerobot',
    version: 'v2.0',
    pythonVersion: '3.10',
    torchVersion: '2.1.2+cu121',
    selectedRobots: [],
  },
  setStep: (step) => set({ step }),
  updateConfig: (updates) =>
    set((state) => ({ config: { ...state.config, ...updates } })),
  reset: () =>
    set({
      step: 1,
      config: {
        repoType: 'official',
        repoUrl: 'https://github.com/huggingface/lerobot',
        version: 'v2.0',
        pythonVersion: '3.10',
        torchVersion: '2.1.2+cu121',
        selectedRobots: [],
      },
    }),
}));
