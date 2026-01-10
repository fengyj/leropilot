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
  Link as LinkIcon
} from 'lucide-react';
import { Modal } from '../../../components/ui/modal';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Select } from '../../../components/ui/select';
import { LoadingOverlay } from '../../../components/ui/loading-overlay';
import { Robot, RobotDefinition, RobotMotorBusConnection } from '../../../types/hardware';

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
  const [refreshingDevices, setRefreshingDevices] = useState(false);

  const [selectedDefinitionId, setSelectedDefinitionId] = useState<string>("");
  const [busConfigs, setBusConfigs] = useState<Record<string, string>>({}); // busName -> deviceId
  const [customBuses, setCustomBuses] = useState<CustomBusEntry[]>([{ name: 'component_1', deviceId: '' }]);
  const [expandedDevices, setExpandedDevices] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (isOpen) {
      // Only load data if we haven't loaded it yet
      if (definitions.length === 0) {
        loadData();
      }

      // Reset form state on open
      setSelectedDefinitionId("");
      setCustomBuses([{ name: 'component_1', deviceId: '' }]);
      setBusConfigs({});
      setErrorMsg(null);
    }
  }, [isOpen]); // Only run when modal opens/closes

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

  const validate = () => {
    const usedDeviceIds = new Set<string>();

    if (selectedDefinitionId && selectedDefinitionId !== "custom") {
      const busNames = Object.keys(selectedDef?.motor_buses || {});
      for (const name of busNames) {
        const devId = busConfigs[name];
        if (!devId) return t('hardware.addRobotModal.selectDeviceFor', { component: name });
        if (usedDeviceIds.has(devId)) return t('hardware.addRobotModal.duplicateDeviceError');
        usedDeviceIds.add(devId);
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

  const handleCreate = async (ignoreTransient = false) => {
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
      name = `robot-${shortId}`;
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

      finalDefinition = {
        id: `custom-${uuid}`,
        display_name: t('common.custom'),
        description: mergedDescription,
        motor_buses: mergedMotorBuses,
        urdf: null
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
      { label: t('hardware.addRobotModal.selectDevicePlaceholder'), value: '' },
      ...availableDevices.map(d => {
        const iface = d.motor_bus_connections ? Object.values(d.motor_bus_connections)[0]?.interface : t('common.unknown');
        return {
          label: `${iface} (${d.name}${d.is_transient ? ` - ${t('hardware.robotCard.transient')}` : ''})`,
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
      className="max-w-5xl min-w-[800px] h-[75vh] min-h-[600px] p-0 border-border-default shadow-2xl ring-1 ring-border-subtle/50"
      contentClassName="overflow-hidden p-0"
    >
      <div className="flex-1 flex overflow-hidden h-[calc(75vh-60px)] min-h-[540px]">
        {/* Left Side: Visual Preview */}
        <div className="hidden md:flex w-[40%] bg-surface-tertiary border-r border-border-default relative flex-col pt-12 pb-10 px-10 overflow-hidden">
          {/* Image Area: Takes remaining space */}
          <div className="flex-1 flex items-center justify-center relative min-h-0 w-full">
            {selectedDefinitionId && selectedDefinitionId !== 'custom' && selectedDef?.id ? (
              <img
                key={selectedDef.id}
                src={`/api/hardware/robots/definitions/${selectedDef.id}/image`}
                alt={selectedDef.display_name}
                className="block max-w-full max-h-full w-auto h-auto object-contain drop-shadow-xl animate-in fade-in zoom-in slide-in-from-bottom-4 duration-700 ease-out"
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
                <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-30">Waiting for Selection</p>
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
              <div className="space-y-8">
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

                {selectedDefinitionId && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-semibold text-content-primary flex items-center gap-2">
                        <LinkIcon className="h-4 w-4 text-primary" />
                        {t('hardware.addRobotModal.componentConnections')}
                      </label>
                      {selectedDefinitionId === 'custom' && (
                        <Button variant="secondary" size="sm" onClick={handleAddBus} className="h-7 text-[10px] px-2 shadow-sm border-border-default">
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
                              aria-label={t('hardware.addRobotModal.selectDevicePlaceholder')}
                              className="h-8 bg-surface-secondary/50"
                              options={getDeviceOptions(bus.deviceId)}
                              value={bus.deviceId}
                              onChange={(e) => {
                                const next = [...customBuses];
                                next[index].deviceId = e.target.value;
                                setCustomBuses(next);
                              }}
                            />
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

              </div>

              <div className="space-y-4 pt-4 flex-1 flex flex-col">
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

                <div className="max-h-none overflow-visible pr-2 flex-1 min-h-[300px] relative">
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
                                    {t('hardware.robotCard.transient')}
                                  </span>
                                )}
                                {isAssigned && (
                                  <span className="px-1.5 py-0.5 rounded-full text-[9px] bg-primary text-primary-content font-bold">
                                    {t('hardware.addRobotModal.assigned')}
                                  </span>
                                )}
                              </div>
                              <span className="text-[10px] text-content-tertiary">
                                {t('hardware.robotCard.interfaces')}: {connection?.interface || t('common.unknown')} • {connection?.baudrate || 'Auto'} bps
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-content-secondary font-medium">
                              {t('hardware.addRobotModal.motors', { count: motors.length })}
                            </span>
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="bg-surface-secondary/50 border-t border-border-subtle/30 px-3 py-2 space-y-1">
                            {motors.length === 0 ? (
                              <div className="text-[10px] text-content-tertiary italic py-2 pl-7">{t('hardware.addRobotModal.noMotorsFound')}</div>
                            ) : (
                              motors.map((m, idx) => (
                                <div key={idx} className="flex items-center gap-4 text-[10px] py-1.5 pl-7 border-b border-border-subtle last:border-0 hover:bg-surface-tertiary transition-colors">
                                  <div className="flex-none text-content-secondary flex items-center gap-1.5">
                                    <span className="h-1 w-1 rounded-full bg-content-tertiary" />
                                    <span className="text-content-primary font-mono flex items-center gap-3">
                                      {Array.isArray(m.id) ? (
                                        <>
                                          <span className="flex items-center gap-1">
                                            <span className="text-[9px] text-content-tertiary uppercase tracking-tighter">Send ID:</span>
                                            <span className="text-primary font-bold">{m.id[0]}</span>
                                          </span>
                                          <span className="flex items-center gap-1">
                                            <span className="text-[9px] text-content-tertiary uppercase tracking-tighter">Recv ID:</span>
                                            <span className="text-primary font-bold">{m.id[1]}</span>
                                          </span>
                                        </>
                                      ) : (
                                        <span className="flex items-center gap-1">
                                          <span className="text-[9px] text-content-tertiary uppercase tracking-tighter">Motor ID:</span>
                                          <span className="text-primary font-bold">{m.id}</span>
                                        </span>
                                      )}
                                    </span>
                                  </div>
                                  <div className="flex-1 flex items-center justify-between min-w-0">
                                    <span className="text-content-primary font-medium truncate">{m.brand} {m.model}</span>
                                    <span className="shrink-0 text-[10px] text-content-secondary bg-surface-tertiary px-1.5 py-0.5 rounded border border-border-default ml-2">
                                      {m.variant || 'Standard'}
                                    </span>
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

              {/* Bottom Actions: Part of scroll flow */}
              <div className="pt-6 border-t border-zinc-800 flex justify-end items-center gap-3 mt-auto">
                <Button variant="secondary" onClick={onClose} className="border-zinc-700">
                  {t('common.cancel')}
                </Button>
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

      {/* Error Modal */}
      <Modal
        isOpen={!!errorMsg}
        onClose={() => setErrorMsg(null)}
        title={t('common.error')}
        className="max-w-md"
      >
        <div className="p-6 flex flex-col items-center text-center">
          <div className="h-12 w-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <AlertCircle className="h-6 w-6 text-red-500" />
          </div>
          <h3 className="text-lg font-bold text-content-primary mb-2">{t('hardware.addRobotModal.error')}</h3>
          <p className="text-sm text-content-secondary mb-6">
            {errorMsg}
          </p>
          <Button onClick={() => setErrorMsg(null)} className="w-full bg-red-600 hover:bg-red-700 text-white border-0">
            {t('common.confirm')}
          </Button>
        </div>
      </Modal>
    </Modal>
  );
};