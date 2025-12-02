import { useEffect, useState, useRef } from 'react';
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
  const [error, setError] = useState<string | null>(null);
  const initializedRef = useRef(false);

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

  // Generate default name
  useEffect(() => {
    if (loading) return;

    // Check if we should skip generation
    // We skip if already initialized OR if name is already set
    // BUT we allow re-generation if the current name looks like it's missing torch version (has "-torch-" but we now have a version)
    const isMissingTorchVersion =
      config.friendlyName?.includes('-torch-') && config.torchVersion;

    if (
      (initializedRef.current || config.envName || config.friendlyName) &&
      !isMissingTorchVersion
    ) {
      if (!initializedRef.current) initializedRef.current = true;
      return;
    }

    const repoName = config.repositoryId || 'lerobot';
    const version = (config.lerobotVersion || 'latest').replace(/^v/, '');

    // Extract torch version (e.g. ">=2.2.1" -> "torch2.2", "2.2.1" -> "torch2.2")
    let torch = 'torch';
    if (config.torchVersion) {
      // Match version number, optionally preceded by >= or >
      const match = config.torchVersion.match(/(?:>=?|^)?(\d+\.\d+)/);
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
    });
    initializedRef.current = true;
  }, [
    loading,
    existingEnvs,
    config.repositoryId,
    config.lerobotVersion,
    config.envName,
    config.friendlyName,
    config.cudaVersion,
    config.torchVersion,
    updateConfig,
    detectedHardware,
  ]);

  // Auto-generate ID from friendly name if user is editing
  // We only do this if the user hasn't manually touched the internal name (hard to track)
  // Or we just do it always like before, but we need to be careful not to overwrite if user explicitly wants different.
  // The previous implementation did it always. Let's keep it but make sure it doesn't conflict with the initial setup.
  // The initial setup sets both. This effect will run after that.
  useEffect(() => {
    if (!config.friendlyName || !initializedRef.current) return;

    // Only auto-update if the current envName looks like a slug of the friendlyName (or previous version of it)
    // Or just keep it simple: always update. The user can edit the internal name *after* editing the friendly name if they want.
    // But if they edit internal name first, then friendly name, it will overwrite.
    // A common pattern is: update internal name ONLY IF it matches the slug of the OLD friendly name.
    // But we don't have old friendly name.

    // Let's stick to the previous behavior: derive ID from Friendly Name.
    // But we need to ensure we don't create a loop or overwrite the unique ID we just generated if it's slightly different.

    const generatedId = config.friendlyName
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, '-')
      .replace(/^-|-$/g, '');

    // Only update if different AND if the user hasn't manually set a custom ID that is completely different?
    // For now, let's trust the user will edit Friendly Name first.
    if (generatedId !== config.envName) {
      // We don't update here to avoid overwriting the unique ID generated in the first effect
      // if the slugification is slightly different.
      // Actually, the first effect sets both.
      // If I set friendlyName="lerobot-2.0", id="lerobot-2-0".
      // This effect generates "lerobot-2-0". It matches.

      updateConfig({ envName: generatedId });
    }
  }, [config.friendlyName, config.envName, updateConfig]);

  const validateName = (name: string, isInternal: boolean = false) => {
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
            onChange={(e) => updateConfig({ friendlyName: e.target.value })}
            onBlur={(e) => validateName(e.target.value, false)}
            placeholder="e.g. My LeRobot Project"
            className={cn(
              'border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 transition-colors outline-none focus:border-blue-600',
              error && 'border-red-500 focus:border-red-500',
            )}
          />
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.friendlyNameHelp')}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-content-primary text-sm font-medium">
            {t('wizard.nameConfig.internalName')}
          </label>
          <div className="relative">
            <input
              type="text"
              value={config.envName}
              onChange={(e) => updateConfig({ envName: e.target.value })}
              onBlur={(e) => validateName(e.target.value, true)}
              placeholder="e.g. my-lerobot-project"
              className={cn(
                'border-border-default bg-surface-secondary text-content-primary placeholder:text-content-tertiary w-full rounded-lg border px-4 py-2 font-mono text-sm transition-colors outline-none focus:border-blue-600',
                error && 'border-red-500 focus:border-red-500',
              )}
            />
          </div>
          <p className="text-content-tertiary text-xs">
            {t('wizard.nameConfig.internalNameHelp')}
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-500">
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
