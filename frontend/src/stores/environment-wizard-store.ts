import { create } from 'zustand';

interface WizardConfig {
  repositoryId: string;
  repositoryName: string;
  repositoryUrl: string;
  lerobotVersion: string;
  pythonVersion: string;
  torchVersion?: string;
  torchvisionVersion?: string;
  torchaudioVersion?: string;
  cudaVersion: string;
  rocmVersion?: string;
  extras: string[];
  envName: string;
  friendlyName: string;
  /** Tracks whether user has manually modified the name (to avoid overwriting user changes when regenerating defaults) */
  isNameUserModified: boolean;
  /** Stores the version key used when the name was last auto-generated */
  lastGeneratedVersionKey: string;
}

export interface AdvancedStep {
  id: string;
  name: string;
  comment: string | null;
  commands: string[];
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

export interface HardwareInfo {
  detected_gpu: string | null;
  detected_driver: string | null;
  detected_cuda: string | null;
  detected_rocm: string | null;
  has_nvidia_gpu: boolean;
  has_amd_gpu: boolean;
  is_apple_silicon: boolean;
}

interface WizardState {
  step: number;
  config: WizardConfig;
  customSteps: AdvancedStep[];
  detectedHardware: HardwareInfo | null;
  setStep: (step: number) => void;
  updateConfig: (updates: Partial<WizardConfig>) => void;
  setCustomSteps: (steps: AdvancedStep[]) => void;
  setDetectedHardware: (info: HardwareInfo) => void;
  reset: () => void;
}

const INITIAL_CONFIG: WizardConfig = {
  repositoryId: '',
  repositoryName: '',
  repositoryUrl: '',
  lerobotVersion: '',
  pythonVersion: '',
  cudaVersion: 'auto',
  rocmVersion: undefined,
  extras: [],
  envName: '',
  friendlyName: '',
  isNameUserModified: false,
  lastGeneratedVersionKey: '',
};

export const useWizardStore = create<WizardState>((set) => ({
  step: 1,
  config: INITIAL_CONFIG,
  customSteps: [],
  detectedHardware: null,
  setStep: (step) => set({ step }),
  updateConfig: (updates) =>
    set((state) => ({ config: { ...state.config, ...updates } })),
  setCustomSteps: (steps) => set({ customSteps: steps }),
  setDetectedHardware: (info) => set({ detectedHardware: info }),
  reset: () =>
    set({ step: 1, config: INITIAL_CONFIG, customSteps: [], detectedHardware: null }),
}));
