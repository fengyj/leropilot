import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Plus,
  Trash2,
  RefreshCw,
  ChevronRight,
  Loader2,
  AlertCircle,
  Link as LinkIcon,
  Layers,
  Settings,
} from 'lucide-react';
import { cn } from '../../../utils/cn';
import { Modal } from '../../../components/ui/modal';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Select } from '../../../components/ui/select';
import { MessageBox } from '../../../components/ui/message-box';
import { LoadingOverlay } from '../../../components/ui/loading-overlay';
import { Card, CardHeader, CardTitle, CardContent } from '../../../components/ui/card';
import { Robot, RobotDefinition, RobotMotorBusConnection, RobotMotorDefinition } from '../../../types/hardware';

/**
 * Validates if the hardware motors match the specification.
 * Returns a string error message if mismatch, null otherwise.
 */
const validateMotorCompliance = (
  hwMotors: Record<string, RobotMotorDefinition>,
  specMotors: Record<string, RobotMotorDefinition>,
  t: any
): string | null => {
  const hwList = Object.values(hwMotors);
  const specList = Object.values(specMotors);

  if (hwList.length !== specList.length) {
    return t('hardware.addRobotModal.motorSettings.countMismatch', {
      expected: specList.length,
      actual: hwList.length
    });
  }

  // Compare by ID
  for (const specMotor of specList) {
    const hwMatch = hwList.find(m => JSON.stringify(m.id) === JSON.stringify(specMotor.id));
    if (!hwMatch) {
      const idStr = Array.isArray(specMotor.id) ? specMotor.id.join('/') : specMotor.id;
      return t('hardware.addRobotModal.motorSettings.modelMismatch', {
        id: idStr,
        expected: specMotor.model,
        actual: t('hardware.addRobotModal.motorSettings.missing')
      });
    }
    if (hwMatch.model !== specMotor.model) {
      const idStr = Array.isArray(specMotor.id) ? specMotor.id.join('/') : specMotor.id;
      return t('hardware.addRobotModal.motorSettings.modelMismatch', {
        id: idStr,
        expected: specMotor.model,
        actual: hwMatch.model
      });
    }
  }

  return null;
};

/**
 * Common formatter for motor IDs (Int or Tuple)
 */
const renderMotorId = (id: number | [number, number], t: any) => {
  if (Array.isArray(id)) {
    return `${t('hardware.common.sendId')} ${id[0]} / ${t('hardware.common.recvId')} ${id[1]}`;
  }
  return `${t('hardware.common.motorId')} ${id}`;
};

interface MotorSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (motors: Record<string, RobotMotorDefinition>) => void;
  initialMotors: Record<string, RobotMotorDefinition>;
  specMotors?: Record<string, RobotMotorDefinition>;
  isReadOnly: boolean;
}

const MotorSettingsModal: React.FC<MotorSettingsModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialMotors,
  specMotors,
  isReadOnly
}) => {
  const { t } = useTranslation();
  const [editingMotors, setEditingMotors] = useState<Record<string, RobotMotorDefinition>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Clone motors
      const cloned = JSON.parse(JSON.stringify(initialMotors)) as Record<string, RobotMotorDefinition>;
      
      // If spec is provided, use spec names for matching hardware motors
      if (specMotors) {
        Object.values(specMotors).forEach((specMotor) => {
          const hwKey = Object.keys(cloned).find(k => JSON.stringify(cloned[k].id) === JSON.stringify(specMotor.id));
          if (hwKey) {
            cloned[hwKey].name = specMotor.name;
          }
        });
      }
      
      setEditingMotors(cloned);
      setError(null);
    }
  }, [isOpen, initialMotors, specMotors]);

  const complianceError = specMotors ? validateMotorCompliance(initialMotors, specMotors, t) : null;

  const handleSave = () => {
    // Validate unique names
    const names = Object.values(editingMotors).map(m => m.name);
    if (new Set(names).size !== names.length) {
      setError(t('hardware.addRobotModal.motorSettings.duplicateNameError'));
      return;
    }
    onSave(editingMotors);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isReadOnly ? t('hardware.addRobotModal.motorSettings.viewTitle') : t('hardware.addRobotModal.motorSettings.editTitle')}
      className="max-w-2xl"
    >
      <div className="space-y-6">
        {complianceError && (
          <div className="p-4 bg-warning-surface border border-warning-border rounded-xl flex items-start gap-3 text-warning-content text-sm shadow-sm ring-1 ring-warning-border/50">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-base mb-1">{t('hardware.addRobotModal.motorSettings.checkMismatch')}</p>
              <p className="opacity-90 leading-relaxed">{complianceError}</p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 bg-error-secondary/10 border border-error-default rounded-md flex items-center gap-2 text-error-default text-sm">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
          {(specMotors ? Object.entries(specMotors) : Object.entries(editingMotors)).map(([key, baseMotor]) => {
            // Find corresponding hardware motor if we're using spec as base
            const hwMotor = specMotors 
              ? Object.values(editingMotors).find(m => JSON.stringify(m.id) === JSON.stringify(baseMotor.id))
              : baseMotor;
            
            const isMissing = specMotors && !hwMotor;
            const isModelMismatch = specMotors && hwMotor && hwMotor.model !== baseMotor.model;
            // Use hardware info if exists, otherwise spec info
            const currentMotor = hwMotor || baseMotor;

            return (
              <Card key={key} className={cn(
                "overflow-hidden transition-all duration-200 shadow-md",
                (isModelMismatch || isMissing)
                  ? "bg-error-surface/[0.02] border-error-border/40" 
                  : "hover:border-border-default"
              )}>
                <CardHeader className={cn(
                  "px-4 py-2 border-b flex flex-row items-center justify-between space-y-0",
                  (isModelMismatch || isMissing)
                    ? "bg-error-surface/10 border-error-border/10"
                    : "bg-surface-tertiary/30 border-border-subtle/30"
                )}>
                  <CardTitle className="flex items-center gap-4">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider bg-surface-tertiary text-content-tertiary border border-border-default/50">
                      {renderMotorId(baseMotor.id, t)}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-content-tertiary opacity-80">
                        {t('hardware.common.motorModel')}:
                      </span>
                      <span className="text-xs font-bold text-content-primary">
                        {baseMotor.model}
                      </span>
                    </div>
                  </CardTitle>
                  {(isModelMismatch || isMissing) && specMotors && (
                    <div className="flex items-center gap-2 text-error-content">
                       <AlertCircle className="w-3.5 h-3.5" />
                       <span className="text-[10px] font-bold uppercase opacity-80">{t('hardware.addRobotModal.motorSettings.discoveredMotorLabel')}:</span>
                       <span className="text-[10px] font-bold px-2 py-0.5 bg-error-surface rounded border border-error-border shadow-sm">
                        {isMissing ? t('hardware.addRobotModal.motorSettings.missing') : (hwMotor ? (hwMotor.variant || hwMotor.model) : '')}
                      </span>
                    </div>
                  )}
                </CardHeader>

                <CardContent className="p-4 grid grid-cols-2 gap-6">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-content-tertiary ml-1">
                      {t('hardware.common.motorName')}
                    </label>
                    <Input
                      value={currentMotor.name || ''}
                      placeholder={baseMotor.name || `motor_${currentMotor.id}`}
                      onChange={e => {
                        if (isReadOnly || isMissing) return;
                        setEditingMotors(prev => {
                          const hwKey = Object.keys(prev).find(k => JSON.stringify(prev[k].id) === JSON.stringify(currentMotor.id));
                          if (!hwKey) return prev;
                          return {
                            ...prev,
                            [hwKey]: { ...prev[hwKey], name: e.target.value }
                          };
                        });
                      }}
                      disabled={isReadOnly || isMissing}
                      className="h-9 text-sm bg-surface-primary/50 border-border-subtle focus:border-primary transition-colors pr-8 font-medium"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-content-tertiary ml-1">
                      {t('hardware.common.driveMode')}
                    </label>
                    <div className="flex items-center h-9 pl-1">
                      <input
                        type="checkbox"
                        aria-label={t('hardware.common.driveMode')}
                        title={t('hardware.common.driveMode')}
                        checked={currentMotor.drive_mode === 1}
                        onChange={() => {
                          if (isReadOnly || isMissing) return;
                          setEditingMotors(prev => {
                            const hwKey = Object.keys(prev).find(k => JSON.stringify(prev[k].id) === JSON.stringify(currentMotor.id));
                            if (!hwKey) return prev;
                            return {
                              ...prev,
                              [hwKey]: { ...prev[hwKey], drive_mode: prev[hwKey].drive_mode === 1 ? 0 : 1 }
                            };
                          });
                        }}
                        disabled={isReadOnly || isMissing}
                        className="transition-all hover:scale-105 shadow-sm"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-border-default">
          {isReadOnly ? (
            <Button onClick={onClose}>{t('common.close')}</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
              <Button onClick={handleSave}>{t('common.confirm')}</Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
};

interface AddRobotModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (robotId: string) => void;
}

interface CustomBusEntry {
  name: string;
  deviceId: string;
}

export const AddRobotModal: React.FC<AddRobotModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;

  const [definitions, setDefinitions] = useState<RobotDefinition[]>([]);
  const [availableDevices, setAvailableDevices] = useState<Robot[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(t('hardware.addRobotModal.syncing'));
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [_showTransientConfirm, setShowTransientConfirm] = useState(false);
  const [duplicateCandidate, setDuplicateCandidate] = useState<{ id: string; name: string } | null>(null);
  const [refreshingDevices, setRefreshingDevices] = useState(false);

  const [selectedDefinitionId, setSelectedDefinitionId] = useState<string>("");
  const [category, setCategory] = useState<'robot'|'controller'>('robot');
  const [busConfigs, setBusConfigs] = useState<Record<string, string>>({}); // busName -> deviceId
  const [customBuses, setCustomBuses] = useState<CustomBusEntry[]>([{ name: 'component_1', deviceId: '' }]);
  const [expandedDevices, setExpandedDevices] = useState<Set<string>>(new Set());
  const [motorModalData, setMotorModalData] = useState<{
    componentName: string;
    deviceId: string;
    isReadOnly: boolean;
    specMotors?: Record<string, RobotMotorDefinition>;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Only load data if we haven't loaded it yet
      if (definitions.length === 0) {
        loadData();
      }

      // Reset form state on open
      setSelectedDefinitionId("");
      setCategory('robot');
      setCustomBuses([{ name: 'component_1', deviceId: '' }]);
      setBusConfigs({});
      setErrorMsg(null);
      setMotorModalData(null);
    }
  }, [isOpen]); // Only run when modal opens/closes

  // Keep category in sync with selected definition
  useEffect(() => {
    if (selectedDefinitionId === 'custom') {
      setCategory('robot');
    } else if (selectedDefinitionId) {
      const def = definitions.find(d => d.id === selectedDefinitionId);
      if (def) {
        setCategory((def as any).device_category || 'robot');
      }
    }
  }, [selectedDefinitionId, definitions]);

  const loadData = async () => {
    setLoading(true);
    setLoadingMessage(t('hardware.addRobotModal.syncing'));
    try {
      const [defRes, discRes] = await Promise.all([
        fetch(`/api/hardware/robots/definitions?lang=${lang}`),
        fetch(`/api/hardware/robots/discovery?lang=${lang}`)
      ]);

      if (defRes.ok) {
        const defs = await defRes.json();
        setDefinitions(defs);
      }
      if (discRes.ok) setAvailableDevices(await discRes.json());
    } catch (error) {
      console.error('Failed to load add robot data:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshDiscovery = async () => {
    setRefreshingDevices(true);
    try {
      const res = await fetch(`/api/hardware/robots/discovery?lang=${lang}`);
      if (res.ok) setAvailableDevices(await res.json());
    } catch (error) {
      console.error('Failed to refresh discovery:', error);
    } finally {
      setRefreshingDevices(false);
    }
  };

  const selectedDef = definitions.find(d => d.id === selectedDefinitionId);

  const toggleDeviceExpand = (id: string) => {
    const next = new Set(expandedDevices);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpandedDevices(next);
  };

  const handleOpenMotorSettings = (componentName: string, deviceId: string, isReadOnly: boolean, specMotors?: Record<string, RobotMotorDefinition>) => {
    // Clear previous errors first
    setErrorMsg(null);
    if (!deviceId) {
      setErrorMsg(t('hardware.addRobotModal.motorSettings.mustSelectDevice'));
      return;
    }
    setMotorModalData({ componentName, deviceId, isReadOnly, specMotors });
  };

  const handleSaveMotors = (newMotors: Record<string, RobotMotorDefinition>) => {
    if (!motorModalData) return;

    // Find device and update its definition
    setAvailableDevices(prev => prev.map(d => {
      if (d.id === motorModalData.deviceId) {
        // Deep clone and update
        const updated = JSON.parse(JSON.stringify(d));
        if (updated.definition && typeof updated.definition !== 'string') {
          // Update "motorbus" if exists (for custom), else first bus
          if (updated.definition.motor_buses["motorbus"]) {
            updated.definition.motor_buses["motorbus"].motors = newMotors;
          } else {
            const firstKey = Object.keys(updated.definition.motor_buses)[0];
            if (firstKey) updated.definition.motor_buses[firstKey].motors = newMotors;
          }
        }
        return updated;
      }
      return d;
    }));
  };

  const handleAddBus = () => {
    setCustomBuses([...customBuses, { name: `component_${customBuses.length + 1}`, deviceId: '' }]);
  };

  const handleRemoveBus = (index: number) => {
    if (customBuses.length > 1) {
      setCustomBuses(customBuses.filter((_, i) => i !== index));
    }
  };

  const getUsedDeviceIds = () => {
    const ids = new Set<string>();
    if (selectedDefinitionId && selectedDefinitionId !== "custom") {
      Object.values(busConfigs).forEach(id => { if (id) ids.add(id); });
    } else if (selectedDefinitionId === "custom") {
      customBuses.forEach(b => { if (b.deviceId) ids.add(b.deviceId); });
    }
    return ids;
  };

  // Build a map from assembly motor-bus key -> serial number for the current selection.
  // Returns null if any mapped device lacks a serial_number on its first motor bus (skip check in that case).
  const getMotorbusSerialsForSelection = (): Record<string, string> | null => {
    const map: Record<string, string> = {};

    if (selectedDefinitionId && selectedDefinitionId !== 'custom') {
      const busNames = Object.keys(selectedDef?.motor_buses || {});
      for (const busName of busNames) {
        const devId = busConfigs[busName];
        if (!devId) return null;
        const dev = availableDevices.find(d => d.id === devId);
        if (!dev) return null;
        const conn = dev.motor_bus_connections ? Object.values(dev.motor_bus_connections)[0] : null;
        if (!conn || !conn.serial_number) return null;
        map[busName] = String(conn.serial_number);
      }
      return map;
    }

    // custom assembly: use effective name (motorbus when single) for each custom bus
    for (let i = 0; i < customBuses.length; i++) {
      const bus = customBuses[i];
      const effectiveName = customBuses.length === 1 ? 'motorbus' : bus.name;
      if (!effectiveName) return null;
      if (!bus.deviceId) return null;
      const dev = availableDevices.find(d => d.id === bus.deviceId);
      if (!dev) return null;
      const conn = dev.motor_bus_connections ? Object.values(dev.motor_bus_connections)[0] : null;
      if (!conn || !conn.serial_number) return null;
      map[effectiveName] = String(conn.serial_number);
    }

    return map;
  };

  const validate = () => {
    const usedDeviceIds = new Set<string>();

    if (selectedDefinitionId && selectedDefinitionId !== "custom") {
      const busNames = Object.keys(selectedDef?.motor_buses || {});
      for (const name of busNames) {
        const devId = busConfigs[name];
        if (!devId) return t('hardware.addRobotModal.selectDeviceFor', { component: name });
        if (usedDeviceIds.has(devId)) return t('hardware.addRobotModal.duplicateDeviceError');
        usedDeviceIds.add(devId);

        // Check motor compliance
        const dev = availableDevices.find(d => d.id === devId);
        const specMotors = selectedDef?.motor_buses?.[name]?.motors;
        if (dev && specMotors && dev.definition && typeof dev.definition === 'object') {
          const hwBuses = dev.definition.motor_buses;
          const hwMotors = (hwBuses['motorbus'] || Object.values(hwBuses)[0])?.motors || {};
          const complianceErr = validateMotorCompliance(hwMotors, specMotors, t);
          if (complianceErr) {
            return `${name}: ${complianceErr}`;
          }
        }
      }
    } else if (selectedDefinitionId === "custom") {
      for (let i = 0; i < customBuses.length; i++) {
        const bus = customBuses[i];
        // Enforce "motorbus" name if only one component
        const effectiveName = customBuses.length === 1 ? 'motorbus' : bus.name;

        if (!effectiveName || !/^[a-zA-Z0-9_]+$/.test(effectiveName)) return t('hardware.addRobotModal.invalidComponentName', { name: effectiveName });
        if (!bus.deviceId) return t('hardware.addRobotModal.selectDeviceFor', { component: effectiveName });
        if (usedDeviceIds.has(bus.deviceId)) return t('hardware.addRobotModal.duplicateDeviceError');
        usedDeviceIds.add(bus.deviceId);
      }

      const names = customBuses.map((b) => customBuses.length === 1 ? 'motorbus' : b.name);
      if (new Set(names).size !== names.length) return t('hardware.addRobotModal.duplicateComponentName');
    } else {
      return t('hardware.addRobotModal.robotTypePlaceholder');
    }
    return null;
  };

  const handleCreate = async (ignoreTransient = false, ignoreDuplicate = false) => {
    const error = validate();
    if (error) {
      setErrorMsg(error);
      return;
    }

    const usedIds = Array.from(getUsedDeviceIds());
    const selectedDevices = availableDevices.filter(d => usedIds.includes(d.id));
    const hasTransient = selectedDevices.some(d => d.is_transient);

    if (hasTransient && !ignoreTransient) {
      setShowTransientConfirm(true);
      return;
    }

    // Additional duplicate check based on motor-bus keys and serial numbers:
    // - Build a map: busName -> serial_number for the candidate selection.
    // - Skip check if any selected bus lacks serial_number.
    // - For each existing robot, compare the set of motor-bus keys and the serial_number for each key.
    if (!ignoreDuplicate) {
      const candidateMap = getMotorbusSerialsForSelection();
      if (candidateMap) {
        try {
          const res = await fetch('/api/hardware/robots');
          if (res.ok) {
            const robots: Robot[] = await res.json();
            const candidateKeys = Object.keys(candidateMap);
            for (const r of robots) {
              const robotConns = r.motor_bus_connections || {};
              const robotKeys = Object.keys(robotConns);
              // Count must match
              if (robotKeys.length !== candidateKeys.length) continue;
              // Check each key exists and serial matches
              let match = true;
              for (const key of candidateKeys) {
                const rc = (robotConns as Record<string, RobotMotorBusConnection | undefined>)[key];
                if (!rc || !rc.serial_number) { match = false; break; }
                if (String(rc.serial_number) !== candidateMap[key]) { match = false; break; }
              }
              if (match) {
                setDuplicateCandidate({ id: r.id, name: r.name || (r.definition && typeof r.definition !== 'string' ? (r.definition as any).display_name : r.name) || t('common.unknown') });
                return;
              }
            }
          }
        } catch (e) {
          console.error('Failed to fetch robot list for duplicate check', e);
        }
      }
    }

    setLoading(true);
    setLoadingMessage(t('hardware.addRobotModal.creating'));
    const uuid = crypto.randomUUID();
    const shortId = uuid.slice(0, 4);

    let finalDefinition: any;
    let name: string;
    let motorBusConnections: Record<string, RobotMotorBusConnection> = {};

    if (selectedDefinitionId && selectedDefinitionId !== "custom") {
      finalDefinition = selectedDefinitionId;
      name = `${selectedDef?.display_name}-${shortId}`;
      Object.entries(busConfigs).forEach(([busName, devId]) => {
        const dev = availableDevices.find(d => d.id === devId);
        if (dev?.motor_bus_connections) {
          const firstBus = Object.values(dev.motor_bus_connections)[0];
          motorBusConnections[busName] = firstBus;
        }
      });
    } else {
      // Use localized "Robot" prefix (don't rely on `category`), e.g., "Robot-xxxx" in user language
      name = `${t('hardware.addRobotModal.custom_robot_name')}-${shortId}`;
      const mergedDescription = selectedDevices.map(d => d.definition && typeof d.definition !== 'string' ? d.definition.description : '').filter(Boolean).join(', ') || t('hardware.addRobotModal.customRobotName');

      const mergedMotorBuses: Record<string, any> = {};
      customBuses.forEach((cb) => {
        const dev = availableDevices.find(d => d.id === cb.deviceId);
        const effectiveName = customBuses.length === 1 ? 'motorbus' : cb.name;

        if (dev) {
          if (dev.definition && typeof dev.definition !== 'string') {
            const firstBusDef = Object.values(dev.definition.motor_buses)[0];
            mergedMotorBuses[effectiveName] = firstBusDef;
          }
          if (dev.motor_bus_connections) {
            motorBusConnections[effectiveName] = Object.values(dev.motor_bus_connections)[0];
          }
        }
      });

      // Use id and display_name from the first selected device's definition when available
      let customId = `custom-${uuid}`;
      let customDisplay: string | Record<string, string> = t('common.custom');
      if (selectedDevices.length > 0) {
        const srcDef = selectedDevices[0].definition;
        if (srcDef && typeof srcDef !== 'string') {
          if (srcDef.id) customId = srcDef.id;
          if (srcDef.display_name) customDisplay = srcDef.display_name;
        }
      }

      finalDefinition = {
        id: customId,
        display_name: customDisplay,
        description: mergedDescription,
        motor_buses: mergedMotorBuses,
        device_category: category
      };
    }

    const manufacturers = Array.from(new Set(selectedDevices.map(d => d.manufacturer).filter(Boolean)));
    const finalManufacturer = manufacturers.length === 1 ? manufacturers[0] : null;

    const newRobot: Robot = {
      id: uuid,
      name,
      status: 'offline',
      manufacturer: finalManufacturer as string | null,
      labels: {},
      created_at: new Date().toISOString(),
      is_transient: hasTransient,
      definition: finalDefinition,
      motor_bus_connections: motorBusConnections
    };

    try {
      const res = await fetch('/api/hardware/robots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRobot)
      });

      if (res.ok) {
        setLoading(false);
        onSuccess(uuid);
      } else {
        const err = await res.json();
        setLoading(false);
        setErrorMsg(t('hardware.addRobotModal.addFailed', { error: err.detail || t('common.unknownError') }));
      }
    } catch (error) {
      setLoading(false);
      setErrorMsg(t('hardware.addRobotModal.networkError'));
    }
  };

  const getDeviceOptions = (currentDeviceId: string) => {
    const usedIds = getUsedDeviceIds();
    return [
      { label: t('hardware.common.selectDevicePlaceholder'), value: '' },
      ...availableDevices.map(d => {
        return {
          label: `${d.name}${d.is_transient ? ` - ${t('hardware.common.transient')}` : ''}`,
          value: d.id,
          disabled: usedIds.has(d.id) && d.id !== currentDeviceId
        };
      })
    ];
  };

  const definitionOptions = [
    { label: t('hardware.addRobotModal.robotTypePlaceholder'), value: '' },
    ...definitions.map(d => ({ label: d.display_name, value: d.id })),
    { label: t('hardware.addRobotModal.customAssembly'), value: 'custom' }
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={t('hardware.addRobotModal.title')}
      className="max-w-5xl min-w-[800px] h-[75vh] min-h-[600px] p-0 border border-border-strong shadow-2xl"
      contentClassName="overflow-hidden p-0"
    >
      <div className="flex-1 flex overflow-hidden h-[calc(75vh-60px)] min-h-[540px]">
        {/* Left Side: Visual Preview */}
        <div className="hidden md:flex w-[40%] bg-surface-secondary/50 border-r border-border-default relative flex-col pt-12 pb-10 px-10 overflow-hidden">
          {/* Background Gradient Effect */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/5 pointer-events-none" />
          
          {/* Image Area: Takes remaining space */}
          <div className="flex-1 flex items-center justify-center relative min-h-0 w-full z-10">
            {selectedDefinitionId && selectedDefinitionId !== 'custom' && selectedDef?.id ? (
              <img
                key={selectedDef.id}
                src={`/api/hardware/robots/definitions/${selectedDef.id}/image`}
                alt={selectedDef.display_name}
                className="block max-w-full max-h-full w-auto h-auto mx-auto object-contain drop-shadow-xl animate-in fade-in zoom-in slide-in-from-bottom-4 duration-700 ease-out"
                // Fallback for when image fails to load (optional but recommended)
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                  (e.target as HTMLImageElement).parentElement?.querySelector('.image-placeholder')?.classList.remove('hidden');
                }}
              />
            ) : null}

            {/* Placeholder icon shown when no image or custom selection */}
            <div className={`image-placeholder flex flex-col items-center text-content-tertiary p-8 border-2 border-dashed border-border-default rounded-3xl animate-in fade-in duration-500 ${(selectedDefinitionId && selectedDefinitionId !== 'custom' && selectedDef?.id) ? 'hidden' : ''}`}>
              <Bot className="h-32 w-32 mb-4 opacity-10" />
              <div className="h-1.5 w-16 bg-content-tertiary/20 rounded-full" />
            </div>
          </div>

          {/* Info Area: Fixed Height */}
          <div className="h-44 flex flex-col shrink-0 mt-10">
            {selectedDefinitionId ? (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-1000 ease-out">
                <h3 className="text-2xl font-bold text-content-primary tracking-tight truncate mb-3">
                  {selectedDefinitionId === 'custom' ? t('hardware.addRobotModal.customRobotName') : selectedDef?.display_name}
                </h3>
                <p className="text-sm text-content-secondary leading-relaxed line-clamp-4">
                  {selectedDefinitionId === 'custom'
                    ? t('hardware.addRobotModal.customRobotDescription')
                    : (selectedDef?.description || t('hardware.addRobotModal.noDescription'))}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-content-tertiary border-t border-border-default/50 pt-8">
                <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-30">{t('hardware.addRobotModal.waitingForSelection')}</p>
              </div>
            )}
          </div>

          {/* Subtle decoration elements */}
          <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-surface-tertiary via-surface-tertiary/50 to-transparent pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-full h-32 bg-gradient-to-t from-surface-tertiary via-surface-tertiary/50 to-transparent pointer-events-none" />
        </div>

        {/* Right Side: Configuration (Scrollable) */}
        <div className="flex-1 flex flex-col bg-surface-primary relative min-w-0 h-full">
          {loading && !errorMsg && (
            <LoadingOverlay
              message={loadingMessage}
              size="lg"
              fancy
              className="rounded-xl"
            />
          )}

          <div className="flex-1 overflow-y-auto custom-scrollbar z-10">
            <div className="flex flex-col min-h-full p-8 space-y-8">
              <div className="flex-1 space-y-8">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label htmlFor="robot-type-select" className="text-sm font-semibold text-content-primary flex items-center gap-2">
                      <Bot className="h-4 w-4 text-primary" />
                      {t('hardware.addRobotModal.robotType')}
                    </label>
                    <Select
                      id="robot-type-select"
                      name="robot-type-select"
                      options={definitionOptions}
                      value={selectedDefinitionId}
                      onChange={(e) => {
                        setSelectedDefinitionId(e.target.value);
                        setBusConfigs({});
                        if (e.target.value === 'custom') {
                          setCustomBuses([{ name: 'component_1', deviceId: '' }]);
                        }
                      }}
                    />
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                      <label htmlFor="device-category-select" className="text-sm font-semibold text-content-primary flex items-center gap-2">
                        <Layers className="h-4 w-4 text-primary" />
                        {t('hardware.addRobotModal.category')}
                      </label>
                      <Select
                        id="device-category-select"
                        name="device-category-select"
                        options={[
                          { label: t('hardware.common.categoryRobot'), value: 'robot' },
                          { label: t('hardware.common.categoryController'), value: 'controller' }
                        ]}
                        value={category}
                        onChange={(e) => setCategory(e.target.value as 'robot' | 'controller')}
                        // disable unless user selected custom assembly
                        disabled={selectedDefinitionId !== 'custom'}
                      />

                  </div>
                </div>

                {selectedDefinitionId && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-semibold text-content-primary flex items-center gap-2">
                        <LinkIcon className="h-4 w-4 text-primary" />
                        {t('hardware.addRobotModal.componentConnections')}
                      </label>
                      {selectedDefinitionId === 'custom' && (
                        <Button variant="secondary" size="sm" onClick={handleAddBus}>
                          <Plus className="h-3 w-3 mr-1" /> {t('hardware.addRobotModal.addComponent')}
                        </Button>
                      )}
                    </div>

                    <div className="space-y-4 bg-surface-secondary/30 p-4 rounded-xl border border-border-subtle shadow-inner">
                      {selectedDefinitionId !== 'custom' ? (
                        selectedDef && Object.keys(selectedDef.motor_buses).length > 0 ? (
                          (() => {
                            const busNames = Object.keys(selectedDef.motor_buses);
                            return busNames.map(busName => (
                              <div key={busName} className="space-y-2">
                                {busNames.length > 1 && (
                                  <div className="flex items-center gap-2">
                                    <label htmlFor={`bus-config-${busName}`} className="text-[10px] font-bold text-content-tertiary uppercase tracking-widest">{busName}</label>
                                    <span className="h-px flex-1 bg-border-subtle/50" />
                                  </div>
                                )}
                                <Select
                                  id={`bus-config-${busName}`}
                                  name={`bus-config-${busName}`}
                                  aria-label={busNames.length === 1 ? t('hardware.addRobotModal.componentConnections') : busName}
                                  options={getDeviceOptions(busConfigs[busName] || '')}
                                  value={busConfigs[busName] || ''}
                                  onChange={(e) => setBusConfigs({ ...busConfigs, [busName]: e.target.value })}
                                />
                                <button
                                  type="button"
                                  onClick={() => handleOpenMotorSettings(busName, busConfigs[busName], true, selectedDef.motor_buses[busName].motors)}
                                  className="text-[10px] text-primary hover:underline flex items-center gap-1 mt-1 opacity-80 hover:opacity-100 transition-opacity"
                                >
                                  <Settings className="h-3 w-3" />
                                  {t('hardware.addRobotModal.motorSettings.viewLink')}
                                </button>
                              </div>
                            ));
                          })()
                        ) : (
                          <div className="text-center py-4 text-xs text-content-tertiary">{t('hardware.addRobotModal.noRequirements')}</div>
                        )
                      ) : (
                        customBuses.map((bus, index) => (
                          <div key={index} className="space-y-2 p-3 bg-surface-primary rounded-lg border border-border-subtle shadow-sm relative group">
                            {customBuses.length > 1 && (
                              <div className="flex items-center gap-2">
                                <Input
                                  id={`custom-bus-name-${index}`}
                                  name={`custom-bus-name-${index}`}
                                  aria-label={t('hardware.addRobotModal.componentNamePlaceholder')}
                                  placeholder={t('hardware.addRobotModal.componentNamePlaceholder')}
                                  className="h-8 text-xs flex-1 bg-surface-secondary/50"
                                  value={bus.name}
                                  onChange={(e) => {
                                    const next = [...customBuses];
                                    next[index].name = e.target.value;
                                    setCustomBuses(next);
                                  }}
                                />
                                <Button variant="secondary" size="sm" onClick={() => handleRemoveBus(index)} className="h-8 w-8 p-0 text-content-tertiary hover:text-status-danger transition-colors border-border-default">
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                            <Select
                              id={`custom-bus-device-${index}`}
                              name={`custom-bus-device-${index}`}
                              aria-label={t('hardware.common.selectDevicePlaceholder')}
                              options={getDeviceOptions(bus.deviceId)}
                              value={bus.deviceId}
                              onChange={(e) => {
                                const next = [...customBuses];
                                next[index].deviceId = e.target.value;
                                setCustomBuses(next);
                              }}
                            />
                            <button
                              type="button"
                              onClick={() => handleOpenMotorSettings(bus.name, bus.deviceId, false)}
                              className="text-[10px] text-primary hover:underline flex items-center gap-1 mt-1 opacity-80 hover:opacity-100 transition-opacity"
                            >
                              <Settings className="h-3 w-3" />
                              {t('hardware.addRobotModal.motorSettings.editLink')}
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                <div className="space-y-4 pt-4">
                  <div className="flex items-center justify-between border-b border-border-subtle pb-2">
                    <label id="discovery-details-label" className="text-sm font-semibold text-content-primary flex items-center gap-2">
                      {t('hardware.addRobotModal.discoveryDetails')}
                    </label>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={refreshDiscovery}
                      disabled={refreshingDevices}
                      className="h-7 text-[10px] border-border-default"
                    >
                      <RefreshCw className={`h-3 w-3 mr-1 ${refreshingDevices ? 'animate-spin' : ''}`} />
                      {t('hardware.addRobotModal.refreshDiscovery')}
                    </Button>
                  </div>

                  <div className="max-h-none overflow-visible pr-2 relative">
                    {refreshingDevices && (
                      <LoadingOverlay
                        message={t('hardware.addRobotModal.scanningPorts')}
                        size="md"
                        fancy
                        className="rounded-xl"
                      />
                    )}

                    {!refreshingDevices && availableDevices.length === 0 && (
                      <div className="py-12 flex flex-col items-center justify-center border-2 border-dashed border-border-subtle/50 rounded-xl bg-surface-secondary/10 text-center px-6">
                        <div className="h-12 w-12 rounded-full bg-surface-tertiary flex items-center justify-center mb-4">
                          <AlertCircle className="h-6 w-6 text-content-tertiary" />
                        </div>
                        <h4 className="text-sm font-bold text-content-secondary mb-1">{t('hardware.addRobotModal.noHardwareFound')}</h4>
                        <p className="text-[11px] text-content-tertiary max-w-[240px]">
                          {t('hardware.addRobotModal.noHardwareHelp')}
                        </p>
                      </div>
                    )}

                    {!refreshingDevices && availableDevices.map((device) => {
                      const isExpanded = expandedDevices.has(device.id);
                      const usedIds = getUsedDeviceIds();
                      const isAssigned = usedIds.has(device.id);

                      // Extract motors from definition
                      let motors: any[] = [];
                      if (device.definition && typeof device.definition !== 'string') {
                        // Follow user instruction: check "motorbus" key first, otherwise take first bus
                        const busDef = device.definition.motor_buses["motorbus"] || Object.values(device.definition.motor_buses)[0];
                        if (busDef) {
                          motors = Object.values(busDef.motors);
                        }
                      }

                      const connection = device.motor_bus_connections ? Object.values(device.motor_bus_connections)[0] : null;

                      return (
                        <div key={device.id} className={`mb-2 border rounded-lg overflow-hidden transition-all duration-200 shadow-sm ${isAssigned
                          ? 'border-primary/50 bg-primary/5 ring-1 ring-primary/20'
                          : 'border-border-subtle bg-surface-secondary/20 hover:border-content-tertiary'
                          }`}>
                          <div
                            className="p-3 flex items-center justify-between cursor-pointer group"
                            onClick={() => toggleDeviceExpand(device.id)}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : 'text-content-tertiary'}`}>
                                <ChevronRight className="h-4 w-4" />
                              </div>
                              <div className="flex flex-col">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-bold text-content-primary">
                                    {device.name}
                                  </span>
                                  {device.is_transient && (
                                    <span className="px-1 py-0.5 rounded text-[8px] bg-surface-tertiary text-content-secondary font-bold uppercase tracking-tighter border border-border-default">
                                      {t('hardware.common.transient')}
                                    </span>
                                  )}
                                  {isAssigned && (
                                    <span className="px-1.5 py-0.5 rounded-full text-[9px] bg-primary text-primary-content font-bold">
                                      {t('hardware.addRobotModal.assigned')}
                                    </span>
                                  )}
                                </div>
                                <span className="text-[10px] text-content-tertiary">
                                  {t('hardware.common.interfaces')}: {connection?.interface || t('common.unknown')} • {connection?.baudrate ? `${connection.baudrate} ${t('hardware.common.baudrateUnit')}` : t('hardware.common.baudrateAuto')}{connection?.serial_number && (
                                    <span className="ml-3 text-[10px] text-content-tertiary">• {t('hardware.common.sn')}: {connection.serial_number}</span>
                                  )}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-content-secondary font-medium">
                                {t('hardware.common.motors', { count: motors.length })}
                              </span>
                            </div>
                          </div>

                          {isExpanded && (
                            <div className="bg-surface-secondary/50 border-t border-border-subtle/30 px-3 py-2 space-y-1">
                              {motors.length === 0 ? (
                                <div className="text-[10px] text-content-tertiary italic py-2 pl-7">{t('hardware.common.noMotorsFound')}</div>
                              ) : (
                                motors.map((m, idx) => (
                                  <div key={idx} className="flex items-center gap-4 text-[10px] py-1.5 pl-7 border-b border-border-subtle last:border-0 hover:bg-surface-tertiary transition-colors">
                                    <div className="flex-none text-content-secondary flex items-center gap-1.5">
                                      <span className="h-1 w-1 rounded-full bg-content-tertiary" />
                                      <span className="text-content-primary font-bold">
                                        {renderMotorId(m.id, t)}
                                      </span>
                                    </div>
                                    <div className="flex-1 flex items-center justify-between min-w-0">
                                      <span className="text-content-primary font-medium truncate">{m.model}</span>
                                    </div>
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Bottom Actions: Pins to bottom when content is short, follows content when scrolls */}
              <div className="pt-6 border-t border-border-default flex justify-end items-center gap-3 mt-auto">
                <Button variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
                {/* TODO: 等机器人编辑 modal 做好后，创建成功并关闭此添加窗口后，应自动打开编辑窗口（传入新创建的 robot id） */}
                <Button
                  onClick={() => handleCreate()}
                  disabled={loading || refreshingDevices}
                  className="px-6 shadow-lg shadow-primary/10"
                >
                  {loading ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-2" /> {t('hardware.addRobotModal.creating')}</>
                  ) : t('common.create')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Duplicate-check Confirm MessageBox */}
      <MessageBox
        isOpen={!!duplicateCandidate}
        onClose={() => setDuplicateCandidate(null)}
        type="warning"
        title={t('hardware.addRobotModal.possibleDuplicateTitle') || t('common.confirm')}
        message={t('hardware.addRobotModal.possibleDuplicateFound')}
        description={t('hardware.addRobotModal.possibleDuplicateFoundMessage', { name: duplicateCandidate?.name })}
        buttonType="ok-cancel"
        onConfirm={() => { setDuplicateCandidate(null); handleCreate(false, true); }}
      />

      {/* Error MessageBox */}
      <MessageBox
        isOpen={!!errorMsg}
        onClose={() => setErrorMsg(null)}
        type="error"
        title={t('common.error')}
        message={t('hardware.addRobotModal.error')}
        description={errorMsg || ""}
        buttonType="ok"
      />

      {/* Motor Settings Modal */}
      {motorModalData && (
        <MotorSettingsModal
          isOpen={!!motorModalData}
          onClose={() => setMotorModalData(null)}
          onSave={handleSaveMotors}
          isReadOnly={motorModalData.isReadOnly}
          specMotors={motorModalData.specMotors}
          initialMotors={(() => {
            const dev = availableDevices.find((d: Robot) => d.id === (motorModalData as any).deviceId);
            if (dev?.definition && typeof dev.definition === 'object') {
              const def = dev.definition as RobotDefinition;
              return def.motor_buses["motorbus"]?.motors || Object.values(def.motor_buses)[0]?.motors || {};
            }
            return {};
          })()}
        />
      )}
    </Modal>
  );
};