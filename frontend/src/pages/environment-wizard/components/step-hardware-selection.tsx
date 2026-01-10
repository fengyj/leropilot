import { Zap, Check, Loader2, Cpu } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore, HardwareInfo } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { useEffect, useState, useMemo, useCallback } from 'react';

interface CompatibilityEntry {
  torch: string;
  cuda: string[];
  rocm: string[];
  cpu: boolean;
  torchvision?: string;
  torchaudio?: string;
  is_recommended: boolean;
}

interface Version {
  tag: string;
  compatibility_matrix?: CompatibilityEntry[];
}

interface ComputeOption {
  id: string;
  label: string;
  torch: string;
  torchvision?: string;
  torchaudio?: string;
  cuda?: string;
  rocm?: string;
  isRecommended: boolean;
  type: 'cuda' | 'rocm' | 'cpu';
}

export function StepHardwareSelection() {
  const { t } = useTranslation();
  const { config, updateConfig, setDetectedHardware, detectedHardware } =
    useWizardStore();
  const [loading, setLoading] = useState(!detectedHardware);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(true);

  // Fetch hardware info
  useEffect(() => {
    if (detectedHardware) {
      setLoading(false);
      return;
    }

    const fetchHardware = async () => {
      try {
        const response = await fetch('/api/environments/hardware');
        if (response.ok) {
          const data: HardwareInfo = await response.json();
          setDetectedHardware(data);
        }
      } catch (error) {
        console.error('Failed to fetch hardware info:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchHardware();
  }, [detectedHardware, setDetectedHardware]);

  // Fetch versions to get compatibility matrix for current lerobot version
  useEffect(() => {
    const fetchVersions = async () => {
      if (!config.repositoryId) return;

      setVersionsLoading(true);
      try {
        const response = await fetch(
          `/api/repositories/${config.repositoryId}/versions`,
        );
        if (response.ok) {
          const data = await response.json();
          setVersions(data);
        }
      } catch (error) {
        console.error('Failed to fetch versions:', error);
      } finally {
        setVersionsLoading(false);
      }
    };
    fetchVersions();
  }, [config.repositoryId]);

  // Compute available options based on selected version and hardware
  const computeOptions = useMemo(() => {
    const ver = versions.find((v) => v.tag === config.lerobotVersion);
    if (!ver?.compatibility_matrix) return [];

    const options: ComputeOption[] = [];

    ver.compatibility_matrix.forEach((entry) => {
      let recommendedCudaVer: string | undefined;
      let recommendedRocmVer: string | undefined;

      if (entry.is_recommended && detectedHardware) {
        if (detectedHardware.has_nvidia_gpu && entry.cuda.length > 0) {
          const driverVer = detectedHardware.detected_cuda
            ? parseFloat(detectedHardware.detected_cuda)
            : 999;
          const supported = entry.cuda.filter((v) => parseFloat(v) <= driverVer);
          if (supported.length > 0) {
            supported.sort((a, b) => parseFloat(b) - parseFloat(a));
            recommendedCudaVer = supported[0];
          } else {
            recommendedCudaVer = entry.cuda[0];
          }
        } else if (detectedHardware.has_amd_gpu && entry.rocm.length > 0) {
          recommendedRocmVer = entry.rocm[entry.rocm.length - 1];
        }
      } else if (entry.is_recommended && !detectedHardware) {
        if (entry.cuda.length > 0) recommendedCudaVer = entry.cuda[0];
      }

      const showCuda = !detectedHardware || detectedHardware.has_nvidia_gpu;
      const showRocm = !detectedHardware || detectedHardware.has_amd_gpu;

      if (showCuda) {
        entry.cuda.forEach((cudaVer) => {
          const isRec = entry.is_recommended && cudaVer === recommendedCudaVer;
          options.push({
            id: `torch${entry.torch}-cuda${cudaVer}`,
            label: `PyTorch ${entry.torch} + CUDA ${cudaVer}`,
            torch: entry.torch,
            torchvision: entry.torchvision,
            torchaudio: entry.torchaudio,
            cuda: cudaVer,
            isRecommended: isRec,
            type: 'cuda',
          });
        });
      }

      if (showRocm) {
        entry.rocm.forEach((rocmVer) => {
          const isRec = entry.is_recommended && rocmVer === recommendedRocmVer;
          options.push({
            id: `torch${entry.torch}-rocm${rocmVer}`,
            label: `PyTorch ${entry.torch} + ROCm ${rocmVer}`,
            torch: entry.torch,
            torchvision: entry.torchvision,
            torchaudio: entry.torchaudio,
            rocm: rocmVer,
            isRecommended: isRec,
            type: 'rocm',
          });
        });
      }

      if (entry.cpu) {
        let isRec = false;
        if (entry.is_recommended) {
          if (detectedHardware?.has_nvidia_gpu && entry.cuda.length > 0) {
            isRec = false;
          } else if (detectedHardware?.has_amd_gpu && entry.rocm.length > 0) {
            isRec = false;
          } else {
            isRec = true;
          }
        }

        options.push({
          id: `torch${entry.torch}-cpu`,
          label: `PyTorch ${entry.torch} + CPU`,
          torch: entry.torch,
          torchvision: entry.torchvision,
          torchaudio: entry.torchaudio,
          isRecommended: isRec,
          type: 'cpu',
        });
      }
    });

    return options;
  }, [config.lerobotVersion, versions, detectedHardware]);

  const handleSelectCompute = useCallback(
    (option: ComputeOption) => {
      updateConfig({
        torchVersion: option.torch,
        torchvisionVersion: option.torchvision,
        torchaudioVersion: option.torchaudio,
        cudaVersion: option.type === 'cpu' ? 'cpu' : option.cuda || 'auto',
        rocmVersion: option.rocm,
      });
    },
    [updateConfig],
  );

  // Auto-select recommended option
  useEffect(() => {
    if (computeOptions.length === 0) return;

    const currentIsValid = computeOptions.some(
      (opt) =>
        opt.torch === config.torchVersion &&
        (opt.cuda === config.cudaVersion ||
          (opt.type === 'cpu' && config.cudaVersion === 'cpu') ||
          opt.rocm === config.rocmVersion),
    );

    if (!config.cudaVersion || config.cudaVersion === 'auto' || !currentIsValid) {
      const recommended =
        computeOptions.find((opt) => opt.isRecommended) || computeOptions[0];
      if (recommended) {
        handleSelectCompute(recommended);
      }
    }
  }, [
    computeOptions,
    config.cudaVersion,
    config.torchVersion,
    config.rocmVersion,
    handleSelectCompute,
  ]);

  const getHardwareDisplayName = () => {
    if (loading) return t('common.loading');
    if (!detectedHardware) return t('wizard.hardwareSelection.unknown');

    if (detectedHardware.detected_gpu) return detectedHardware.detected_gpu;
    if (detectedHardware.has_nvidia_gpu) return t('wizard.hardwareSelection.nvidiaGpu');
    if (detectedHardware.has_amd_gpu) return t('wizard.hardwareSelection.amdGpu');
    if (detectedHardware.is_apple_silicon)
      return t('wizard.hardwareSelection.appleSilicon');

    return t('wizard.hardwareSelection.cpuOnly');
  };

  if (loading || versionsLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.hardwareSelection.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.hardwareSelection.subtitle')}
        </p>
      </div>

      {/* Detected Hardware Info */}
      <div className="bg-surface-tertiary flex items-center gap-4 rounded-lg p-4">
        <div className="bg-surface-secondary flex h-10 w-10 items-center justify-center rounded-full">
          <Zap className="text-content-primary h-5 w-5" />
        </div>
        <div>
          <p className="text-content-secondary text-xs font-medium uppercase">
            {t('wizard.hardwareSelection.detected')}
          </p>
          <p className="text-content-primary font-medium">{getHardwareDisplayName()}</p>
          {detectedHardware &&
            (detectedHardware.detected_driver ||
              detectedHardware.detected_cuda ||
              detectedHardware.detected_rocm) && (
              <p className="text-content-tertiary text-xs">
                {detectedHardware.detected_driver && (
                  <>
                    {t('wizard.hardwareSelection.driver')}: {' '}
                    {detectedHardware.detected_driver}
                  </>
                )}
                {detectedHardware.detected_driver &&
                  (detectedHardware.detected_cuda || detectedHardware.detected_rocm) &&
                  ' • '}
                {detectedHardware.detected_cuda && (
                  <>CUDA: {detectedHardware.detected_cuda}</>
                )}
                {detectedHardware.detected_rocm && (
                  <>ROCm: {detectedHardware.detected_rocm}</>
                )}
              </p>
            )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {computeOptions.map((option) => {
          const isSelected =
            config.torchVersion === option.torch &&
            ((option.type === 'cpu' && config.cudaVersion === 'cpu') ||
              (option.type === 'cuda' && config.cudaVersion === option.cuda) ||
              (option.type === 'rocm' && config.rocmVersion === option.rocm));

          return (
            <div
              key={option.id}
              onClick={() => handleSelectCompute(option)}
              onKeyDown={(e) =>
                (e.key === 'Enter' || e.key === ' ') && handleSelectCompute(option)
              }
              role="button"
              tabIndex={0}
              className={cn(
                'relative cursor-pointer rounded-lg border p-4 transition-all focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none outline-none',
                isSelected
                  ? 'border-primary bg-primary/5'
                  : 'border-border-default bg-surface-secondary hover:border-border-subtle',
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {option.type === 'cpu' ? (
                    <Cpu className="text-content-tertiary h-5 w-5" />
                  ) : (
                    <Zap
                      className={cn(
                        'h-5 w-5',
                        option.type === 'rocm' ? 'text-status-danger' : 'text-success-icon',
                      )}
                    />
                  )}
                  <div>
                    <p className="text-content-primary text-sm font-medium">
                      {option.label}
                    </p>
                    {option.isRecommended && (
                      <span className="text-success-content text-xs font-medium">
                        {t('wizard.hardwareSelection.recommended')}
                      </span>
                    )}
                  </div>
                </div>

                {isSelected && (
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-content">
                    <Check className="h-3 w-3" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}