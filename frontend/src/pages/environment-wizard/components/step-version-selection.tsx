import { Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { useEffect, useState } from 'react';

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
  is_stable: boolean;
  date?: string;
  torch_version?: string;
  compatibility_matrix?: CompatibilityEntry[];
  python_version?: string;
}

export function StepVersionSelection() {
  const { t } = useTranslation();
  const { config, updateConfig, detectedHardware, setDetectedHardware } =
    useWizardStore();
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch hardware info if missing
  useEffect(() => {
    if (!detectedHardware) {
      fetch('/api/environments/hardware')
        .then((res) => res.json())
        .then((data) => setDetectedHardware(data))
        .catch((err) => console.error('Failed to fetch hardware info:', err));
    }
  }, [detectedHardware, setDetectedHardware]);

  useEffect(() => {
    const fetchVersions = async () => {
      if (!config.repositoryId) return;

      setLoading(true);
      try {
        const response = await fetch(
          `/api/repositories/${config.repositoryId}/versions`,
        );
        if (response.ok) {
          const data = await response.json();
          setVersions(data);

          // Set default version if none selected
          if (!config.lerobotVersion && data.length > 0) {
            const defaultVersion = data.find((v: Version) => v.is_stable) || data[0];
            updateConfig({
              lerobotVersion: defaultVersion.tag,
              pythonVersion: defaultVersion.python_version ?? config.pythonVersion,
            });
          }
        }
      } catch (error) {
        console.error('Failed to fetch versions:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVersions();
    // Only re-fetch when repositoryId changes. Version selection should not trigger re-fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.repositoryId]);

  // Compute available options based on selected version
  // computeOptions are not needed in this step; hardware options are handled elsewhere
  // const computeOptions = useMemo(() => {
  // const ver = versions.find((v) => v.tag === config.lerobotVersion);
  // if (!ver?.compatibility_matrix) return [];

  // const options: ComputeOption[] = [];

  // ver.compatibility_matrix.forEach((entry) => {
  //   // Determine if we should recommend specific backend for this entry
  //   // entry.is_recommended is set by backend based on GPU presence

  //   let recommendedCudaVer: string | undefined;
  //   let recommendedRocmVer: string | undefined;

  //   if (entry.is_recommended && detectedHardware) {
  //     if (detectedHardware.has_nvidia_gpu && entry.cuda.length > 0) {
  //       // Pick highest supported CUDA version
  //       const driverVer = detectedHardware.detected_cuda
  //         ? parseFloat(detectedHardware.detected_cuda)
  //         : 999;
  //       const supported = entry.cuda.filter((v) => parseFloat(v) <= driverVer);
  //       if (supported.length > 0) {
  //         // Sort descending (assuming format "12.1")
  //         supported.sort((a, b) => parseFloat(b) - parseFloat(a));
  //         recommendedCudaVer = supported[0];
  //       } else {
  //         // Fallback to lowest if none supported (or driver too old)
  //         recommendedCudaVer = entry.cuda[0];
  //       }
  //     } else if (detectedHardware.has_amd_gpu && entry.rocm.length > 0) {
  //       // Pick highest supported ROCm version
  //       recommendedRocmVer = entry.rocm[entry.rocm.length - 1];
  //     }
  //   } else if (entry.is_recommended && !detectedHardware) {
  //     // Fallback if hardware info not yet loaded: recommend first CUDA if available
  //     if (entry.cuda.length > 0) recommendedCudaVer = entry.cuda[0];
  //   }

  //   // CUDA options
  //   entry.cuda.forEach((cudaVer) => {
  //     const isRec = entry.is_recommended && cudaVer === recommendedCudaVer;

  //     options.push({
  //       id: `torch${entry.torch}-cuda${cudaVer}`,
  //       label: `PyTorch ${entry.torch} + CUDA ${cudaVer}`,
  //       torch: entry.torch,
  //       cuda: cudaVer,
  //       isRecommended: isRec,
  //       type: 'cuda',
  //     });
  //   });

  //   // ROCm options
  //   entry.rocm.forEach((rocmVer) => {
  //     const isRec = entry.is_recommended && rocmVer === recommendedRocmVer;
  //     options.push({
  //       id: `torch${entry.torch}-rocm${rocmVer}`,
  //       label: `PyTorch ${entry.torch} + ROCm ${rocmVer}`,
  //       torch: entry.torch,
  //       rocm: rocmVer,
  //       isRecommended: isRec,
  //       type: 'rocm',
  //     });
  //   });

  //   // CPU option
  //   if (entry.cpu) {
  //     // Recommend CPU only if entry is recommended and NO GPU options are recommended
  //     let isRec = false;
  //     if (entry.is_recommended) {
  //       if (detectedHardware?.has_nvidia_gpu && entry.cuda.length > 0) {
  //         isRec = false;
  //       } else if (detectedHardware?.has_amd_gpu && entry.rocm.length > 0) {
  //         isRec = false;
  //       } else {
  //         isRec = true;
  //       }
  //     }

  //     options.push({
  //       id: `torch${entry.torch}-cpu`,
  //       label: `PyTorch ${entry.torch} + CPU`,
  //       torch: entry.torch,
  //       isRecommended: isRec,
  //       type: 'cpu',
  //     });
  //   }
  // });

  // return options;
  // }, [config.lerobotVersion, versions, detectedHardware]);

  // Auto-select recommended option
  // Moved to StepHardwareSelection

  const handleSelectVersion = (version: Version) => {
    updateConfig({
      lerobotVersion: version.tag,
      // Reset compute selection
      cudaVersion: undefined,
      rocmVersion: undefined,
      torchVersion: undefined,
      pythonVersion: version.python_version ?? config.pythonVersion,
    });
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* LeRobot Version Selection */}
      <div>
        <div className="mb-4">
          <h3 className="text-content-primary text-lg font-medium">
            {t('wizard.versionSelection.title')}
          </h3>
          <p className="text-content-secondary text-sm">
            {t('wizard.versionSelection.subtitle')}
          </p>
        </div>

        <div className="grid gap-3">
          {versions.map((version) => (
            <div
              key={version.tag}
              onClick={() => handleSelectVersion(version)}
              onKeyDown={(e) => e.key === 'Enter' && handleSelectVersion(version)}
              role="button"
              tabIndex={0}
              className={cn(
                'relative flex cursor-pointer items-center justify-between rounded-lg border p-4 transition-all',
                config.lerobotVersion === version.tag
                  ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
                  : 'border-border-default bg-surface-secondary hover:border-border-subtle',
              )}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-content-primary font-medium">
                    {version.tag}
                  </span>
                  {version.is_stable && (
                    <span className="bg-success-surface text-success-content rounded px-1.5 py-0.5 text-[10px] font-medium uppercase">
                      {t('wizard.versionSelection.stable')}
                    </span>
                  )}
                </div>
                {version.date && (
                  <p className="text-content-tertiary text-sm">
                    {t('wizard.versionSelection.released')}: {' '}
                    {new Date(version.date).toLocaleDateString()}
                  </p>
                )}
              </div>

              {config.lerobotVersion === version.tag && (
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
                  <Check className="h-3 w-3" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}