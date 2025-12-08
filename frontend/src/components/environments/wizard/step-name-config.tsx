import { useEffect, useState, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';

interface Environment {
  id: string;
  display_name: string;
}

export function StepNameConfig() {
  const { t } = useTranslation();
  const { config, updateConfig, detectedHardware, setDetectedHardware } =
    useWizardStore();
  const [existingEnvs, setExistingEnvs] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [friendlyNameError, setFriendlyNameError] = useState<string | null>(null);
  const [envNameError, setEnvNameError] = useState<string | null>(null);
  const initializedRef = useRef(false);

  // Create a stable key from version-related config to detect changes
  const versionKey = useMemo(
    () =>
      `${config.repositoryId}-${config.lerobotVersion}-${config.torchVersion}-${config.cudaVersion}`,
    [
      config.repositoryId,
      config.lerobotVersion,
      config.torchVersion,
      config.cudaVersion,
    ],
  );

  // Fetch existing environments and hardware info if missing
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [envsResponse, hardwareResponse] = await Promise.all([
          fetch('/api/environments'),
          !detectedHardware
            ? fetch('/api/environments/hardware')
            : Promise.resolve(null),
        ]);

        if (envsResponse.ok) {
          const data = await envsResponse.json();
          setExistingEnvs(data);
        }

        if (hardwareResponse && hardwareResponse.ok) {
          const data = await hardwareResponse.json();
          setDetectedHardware(data);
        }
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [detectedHardware, setDetectedHardware]);

  // Generate default name (on first load or when versions change and user hasn't modified name)
  useEffect(() => {
    if (loading) return;

    // Detect if version-related config has changed since last generation
    // Use lastGeneratedVersionKey from store (persists across component remounts)
    const versionChanged =
      config.lastGeneratedVersionKey !== '' &&
      config.lastGeneratedVersionKey !== versionKey;

    // Should we regenerate the name?
    // 1. First time: generate if no name set yet (lastGeneratedVersionKey is empty)
    // 2. Version changed: only regenerate if user hasn't manually modified the name
    const shouldGenerate =
      config.lastGeneratedVersionKey === '' ||
      (versionChanged && !config.isNameUserModified);

    if (!shouldGenerate) {
      initializedRef.current = true;
      return;
    }

    const repoName = config.repositoryId || 'lerobot';
    const version = (config.lerobotVersion || 'latest').replace(/^v/, '');

    // Extract torch version (e.g. ">=2.2.1" -> "torch2.2.1", "2.2.1" -> "torch2.2.1")
    let torch = 'torch';
    if (config.torchVersion) {
      // Match version number (major.minor.patch), optionally preceded by >= or >
      const match = config.torchVersion.match(/(?:>=?|^)?(\d+\.\d+(?:\.\d+)?)/);
      if (match) {
        torch = `torch${match[1]}`;
      }
    }

    let hardware = 'cpu';
    if (config.cudaVersion && config.cudaVersion !== 'cpu') {
      if (config.cudaVersion === 'auto') {
        if (detectedHardware?.has_nvidia_gpu && detectedHardware.detected_cuda) {
          hardware = `cuda${detectedHardware.detected_cuda}`;
        } else if (detectedHardware?.has_amd_gpu) {
          hardware = detectedHardware.detected_rocm
            ? `rocm${detectedHardware.detected_rocm}`
            : 'rocm';
        } else if (detectedHardware?.is_apple_silicon) {
          hardware = 'mps';
        } else {
          // Fallback if auto selected but no hardware detected (shouldn't happen if flow is correct)
          hardware = 'cpu';
        }
      } else {
        hardware = `cuda${config.cudaVersion}`;
      }
    }

    const baseName = `${repoName}-${version}-${torch}-${hardware}`;

    let name = baseName;
    let counter = 1;

    // Check for duplicates and increment
    // We check against both ID and Display Name to be safe and avoid confusion
    while (existingEnvs.some((e) => e.id === name || e.display_name === name)) {
      name = `${baseName}-${counter}`;
      counter++;
    }

    const id = name
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, '-')
      .replace(/^-|-$/g, '');

    updateConfig({
      friendlyName: name,
      envName: id,
      isNameUserModified: false, // Reset flag when auto-generating
      lastGeneratedVersionKey: versionKey, // Store the version key used for this generation
    });
    initializedRef.current = true;
  }, [
    loading,
    existingEnvs,
    config.repositoryId,
    config.lerobotVersion,
    config.cudaVersion,
    config.torchVersion,
    config.isNameUserModified,
    config.lastGeneratedVersionKey,
    updateConfig,
    detectedHardware,
    versionKey,
  ]);

  // Track if the user is editing envName independently
  const [isEnvNameIndependent, setIsEnvNameIndependent] = useState(false);

  // Handle friendlyName change - sync to envName unless user has edited envName independently
  const handleFriendlyNameChange = (value: string) => {
    const updates: Partial<typeof config> = {
      friendlyName: value,
      isNameUserModified: true,
    };

    // Only auto-sync envName if user hasn't edited it independently
    if (!isEnvNameIndependent) {
      const generatedId = value
        .toLowerCase()
        .replace(/[^a-z0-9._-]+/g, '-')
        .replace(/^-|-$/g, '');
      updates.envName = generatedId;
    }

    updateConfig(updates);
  };

  // Handle envName change - mark as independent editing
  const handleEnvNameChange = (value: string) => {
    setIsEnvNameIndependent(true);
    updateConfig({ envName: value, isNameUserModified: true });
  };

  // Reset isEnvNameIndependent when name is auto-generated
  useEffect(() => {
    if (config.lastGeneratedVersionKey === versionKey && !config.isNameUserModified) {
      setIsEnvNameIndependent(false);
    }
  }, [config.lastGeneratedVersionKey, config.isNameUserModified, versionKey]);

  const validateName = (name: string, isInternal: boolean = false) => {
    const setError = isInternal ? setEnvNameError : setFriendlyNameError;

    if (!name) {
      setError(null);
      return;
    }

    // Format check for internal name
    if (isInternal) {
      const validFormat = /^[a-z0-9._-]+$/.test(name);
      if (!validFormat) {
        setError(t('wizard.nameConfig.formatError'));
        return;
      }
    }

    // Check if name exists in existingEnvs (as ID or Display Name)
    // We primarily care about ID uniqueness for the system, but checking Display Name is good for UX.
    // The prompt says "check name cannot be duplicate with existing ones".
    const isDuplicate = existingEnvs.some(
      (e) => e.id === name || e.display_name === name,
    );

    if (isDuplicate) {
      setError(t('wizard.nameConfig.duplicateError'));
    } else {
      setError(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.nameConfig.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.nameConfig.subtitle')}
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <label className="text-content-primary text-sm font-medium">
            {t('wizard.nameConfig.friendlyName')}
          </label>
          <input
            type="text"
            value={config.friendlyName}
            onChange={(e) => handleFriendlyNameChange(e.target.value)}
            onBlur={(e) => validateName(e.target.value, false)}
            placeholder="e.g. My LeRobot Project"
            className={cn(
              'border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 transition-colors outline-none focus:border-blue-600',
              friendlyNameError && 'border-red-500 focus:border-red-500',
            )}
          />
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.friendlyNameHelp')}
          </p>
          {friendlyNameError && (
            <p className="text-sm text-red-500">{friendlyNameError}</p>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-content-primary text-sm font-medium">
            {t('wizard.nameConfig.internalName')}
          </label>
          <div className="relative">
            <input
              type="text"
              value={config.envName}
              onChange={(e) => handleEnvNameChange(e.target.value)}
              onBlur={(e) => validateName(e.target.value, true)}
              placeholder="e.g. my-lerobot-project"
              className={cn(
                'border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 font-mono text-sm transition-colors outline-none focus:border-blue-600',
                envNameError && 'border-red-500 focus:border-red-500',
              )}
            />
          </div>
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.internalNameHelp')}
          </p>
          {envNameError && <p className="text-sm text-red-500">{envNameError}</p>}
        </div>
      </div>
    </div>
  );
}
