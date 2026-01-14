import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Save,
  AlertTriangle,
  RotateCcw,
  AlertCircle,
  Cpu,
  RefreshCw,
  ShieldCheck,
  Ruler
} from 'lucide-react';
import { Modal } from '../../../components/ui/modal';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { MessageBox } from '../../../components/ui/message-box';

import { StatusIcon } from './status-icon';
import {
  Robot,
  RobotDefinition,
  RobotMotorBusConnection,
  MotorCalibration
} from '../../../types/hardware';
import { LoadingOverlay } from '../../../components/ui/loading-overlay';

interface EditRobotModalProps {
  isOpen: boolean;
  onClose: () => void;
  robotId: string | null;
}

interface MotorLimit {
  type: string;
  value: number;
}

type ProtectionSettings = Record<string, MotorLimit[]>;

// Helper for Motor ID value only (no labels), used inside table cells
const renderMotorIdValue = (id: number | [number, number]) => {
  if (Array.isArray(id)) {
    return `${id[0]} / ${id[1]}`;
  }
  return `${id}`;
};

// Parse protection key strings from backend or legacy formats.
// Accepts formats like 'brand:model:variant', 'brand|model|variant', 'brand,model,variant',
// or tuple-like strings. Returns { brand, model, variant } with empty strings when missing.
const parseProtectionKey = (k: string) => {
  if (!k) return { brand: '', model: '', variant: '' };
  let parts: string[] = [];
  if (typeof k === 'string') {
    if (k.includes(':')) parts = k.split(':');
    else if (k.includes('|')) parts = k.split('|');
    else if (k.includes(',')) parts = k.split(',');
    else {
      // try to parse tuple-like strings like "('brand', 'model')"
      const m = k.match(/['"]?([^,'"\)\(]+)['"]?(?:\s*,\s*['"]?([^,'"\)\(]+)['"]?)?(?:\s*,\s*['"]?([^,'"\)\(]+)['"]?)?/);
      if (m) parts = m.slice(1).filter(Boolean);
      else parts = [k];
    }
  }
  const brand = (parts[0] || '').trim();
  const model = (parts[1] || '').trim();
  const variant = (parts[2] || '').trim();
  return { brand, model, variant };
};

export const EditRobotModal: React.FC<EditRobotModalProps> = ({
  isOpen,
  onClose,
  robotId
}) => {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [robot, setRobot] = useState<Robot | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Form State
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [protectionSettings, setProtectionSettings] = useState<ProtectionSettings>({});
  const [existingRobots, setExistingRobots] = useState<Robot[]>([]);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);

  // Initialize state
  useEffect(() => {
    if (isOpen && robotId) {
      setLoading(true);
      // Load robot data
      const load = async () => {
        try {
            const [robotRes, devicesRes] = await Promise.all([
                fetch(`/api/hardware/robots/${robotId}`),
                fetch('/api/hardware/robots?refresh_status=false')
            ]);

            if (robotRes.ok && devicesRes.ok) {
                const r: Robot = await robotRes.json();
                const allRobots: Robot[] = await devicesRes.json();

                setRobot(r);
                setName(r.name);
                setProtectionSettings(r.custom_protection_settings || {});
                // Keep a cached list of existing robots (no status refresh) for used-by detection
                setExistingRobots(allRobots);
            } else {
                setErrorMsg(t('hardware.editRobotModal.noData'));
                onClose();
            }
        } catch (e) {
            console.error(e);
            setErrorMsg(t('hardware.editRobotModal.noData'));
        } finally {
            setLoading(false);
        }
      };
      load();
    } else if (!isOpen) {
      setRobot(null);
      setName("");
      setProtectionSettings({});
      setErrorMsg(null);
    }
  }, [isOpen, robotId, onClose, t]);

  const checkNameUnique = (val: string) => {
    if (!val || val === robot?.name) return;
    const exists = existingRobots.some(r => r.id !== robotId && r.name.toLowerCase() === val.toLowerCase());
    setNameError(exists ? t('hardware.editRobotModal.nameTaken') : null);
  };

  const handleSave = async () => {
    if (nameError) return;
    if (!name.trim()) {
        setNameError(t('hardware.editRobotModal.nameRequired'));
        return;
    }

    setSaving(true);
    try {
      // NOTE: do NOT send motor_bus_connections here — this form does not edit connections and sending them
      // can cause validation errors on the server. Only send fields that the user edited.

      // Normalize protection settings keys to colon-separated format expected by the backend
      const normalizedProtection: Record<string, any> = {};
      Object.entries(protectionSettings || {}).forEach(([k, v]) => {
        const parsed = parseProtectionKey(String(k));
        const parts = [parsed.brand, parsed.model].filter(p => p !== undefined && p !== null && String(p) !== '');
        if (parsed.variant && String(parsed.variant) !== 'null') parts.push(parsed.variant);
        if (parts.length < 2) return; // skip invalid keys
        const normKey = parts.join(':');
        // Ensure numeric values for limits and skip NaN
        normalizedProtection[normKey] = (v || []).map((lim: any) => ({
          type: String(lim.type),
          value: Number(lim.value)
        })).filter((l: any) => !Number.isNaN(l.value));
      });

      const payload: Record<string, any> = {
        name,
      };

      if (Object.keys(normalizedProtection).length > 0) {
        payload.custom_protection_settings = normalizedProtection;
      }

      const res = await fetch(`/api/hardware/robots/${robotId}?verify=false`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        // Try to extract server error details to help debugging
        let detailMsg = '';
        try {
          const body = await res.json();
          if (body && body.detail) detailMsg = Array.isArray(body.detail) ? body.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ') : (body.detail.msg || body.detail || '');
          else if (body && body.message) detailMsg = body.message;
        } catch (e) {
          // ignore JSON parse errors
        }
        throw new Error(detailMsg ? `${t('hardware.editRobotModal.saveFailed')}: ${detailMsg}` : t('hardware.editRobotModal.saveFailed'));
      }

      onClose();
    } catch (err: any) {
      setErrorMsg(err?.message || t('hardware.editRobotModal.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleRestoreDefaults = async () => {
    setShowRestoreConfirm(false);
    if (!robotId) return;
    
    try {
        const res = await fetch(`/api/hardware/robots/${robotId}/motor_models_info`);
        if (!res.ok) throw new Error("failed");
        const models = await res.json();
        
        const newProt: ProtectionSettings = {};
        models.forEach((m: any) => {
            // Use colon-separated keys to match backend format (brand:model[:variant])
            const parts = [m.brand, m.model, m.variant].filter(p => p !== undefined && p !== null && String(p) !== '').map(String);
            const key = parts.join(':');
            const limits = m.limits || {};
            if (Object.keys(limits).length > 0) {
                newProt[key] = Object.entries(limits).map(([type, lim]: [string, any]) => ({
                    type,
                    value: typeof lim === "object" ? lim.value : lim
                }));
            }
        });
        setProtectionSettings(newProt);
    } catch (e) {
        setErrorMsg(t("hardware.editRobotModal.restoreFailed"));
    }
  };

  const handleLimitChange = (groupKey: string, index: number, newValue: string) => {
    const val = parseFloat(newValue);
    if (isNaN(val)) return;
    setProtectionSettings(prev => ({
      ...prev,
      [groupKey]: prev[groupKey].map((l, i) => i === index ? { ...l, value: val } : l)
    }));
  };

  // Helper to check which other robot (if any) is using this device. Returns the robot's display name or null.



  // Derived Values
  const definition = robot?.definition as RobotDefinition;

  // Localized display name for robot type (definition.display_name may be a string or map)
  const getDefinitionDisplayName = () => {
    if (!definition) return t('hardware.editRobotModal.unknownType');
    const disp = (definition as any).display_name;
    if (!disp) return t('hardware.editRobotModal.unknownType');
    if (typeof disp === 'string') return disp;
    if (typeof disp === 'object') {
      // prefer current language, fallback to 'en' or first available
      if (disp[lang]) return disp[lang];
      if (disp['en']) return disp['en'];
      const first = Object.values(disp).find(v => typeof v === 'string');
      if (first) return String(first);
    }
    return t('hardware.editRobotModal.unknownType');
  };
  
  const allCalibrations = useMemo(() => {
    const calMap = robot?.calibration_settings || {};
    return Object.values(calMap).flat() as MotorCalibration[];
  }, [robot?.calibration_settings, lang]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => onClose()}
      title={t('hardware.editRobotModal.title')}
      className="max-w-4xl min-w-[700px] h-[90vh] p-0 flex flex-col border border-border-strong shadow-2xl"
      contentClassName="flex-1 flex flex-col overflow-hidden p-0 bg-surface-primary"
    >
      <div className="flex-1 overflow-y-auto custom-scrollbar p-8 space-y-8">
        {loading && (
           <LoadingOverlay message={t('hardware.editRobotModal.loading')} size="md" fancy />
        )}

        {!loading && robot && (
          <>
            {/* Row 1: Header / Badges */}
            <div className="flex items-start justify-between border-b border-border-subtle pb-6">
              <div className="space-y-4 flex-1">
                 <div className="flex items-center gap-3">
                     <Bot className="w-4 h-4 text-primary" />
                     <span className="text-lg font-bold text-content-primary">{getDefinitionDisplayName()}</span>

                     {/* Category badge: show after type */}
                     <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-tertiary text-content-secondary border border-border-default uppercase tracking-wider">
                       {definition?.device_category === 'controller' ? t('hardware.common.categoryController') : t('hardware.common.categoryRobot')}
                     </span>

                     {robot.is_transient && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-status-warning/10 text-status-warning border border-status-warning/20 uppercase tracking-wider flex items-center gap-1.5 animate-pulse">
                          <AlertTriangle className="w-3 h-3" />
                          {t('hardware.common.transient')}
                        </span>
                     )}
                 </div>
                 {/* Row 2: Name Input */}
                 <div className="max-w-md relative">
                    <label className="text-xs font-bold text-content-tertiary uppercase tracking-wider mb-1 block">{t('hardware.editRobotModal.namePlaceholder')}</label>
                    <Input 
                        value={name} 
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setName(e.target.value); setNameError(null); }} 
                        onBlur={() => checkNameUnique(name)}
                        className={`font-bold text-lg h-auto py-2 ${nameError ? 'border-status-danger text-status-danger' : ''}`}
                    />
                    {nameError && <span className="text-[10px] text-status-danger absolute -bottom-4 left-0 font-medium">{nameError}</span>}
                 </div>
              </div>
              

            </div>

            {/* Row 3: Components (Motor Buses) */}
            <div className="space-y-4">
               <div className="flex items-center gap-2 text-content-primary">
                  <div className="p-1.5 rounded-md bg-surface-secondary text-primary"><Cpu className="w-4 h-4" /></div>
                  <h3 className="text-sm font-bold uppercase tracking-wide">{t('hardware.editRobotModal.motorbusGroupsTitle')}</h3>
               </div>
               
               <div className="space-y-6">
                  {definition && Object.keys(definition.motor_buses).length > 0 ? (
                    Object.entries(definition.motor_buses).map(([busName, busDef]) => {
                        const conn = robot?.motor_bus_connections ? (robot.motor_bus_connections as Record<string, RobotMotorBusConnection>)[busName] : null;
                        const isSingleBus = Object.keys(definition.motor_buses).length === 1;
                        // If any motor in this bus uses a pair id (Send/Recv), show a paired header
                        const hasPairIds = busDef.motors && Object.values(busDef.motors).some((m: any) => Array.isArray(m.id));

                        return (
                           <div key={busName} className="border border-border-default rounded-xl overflow-hidden bg-surface-secondary/5">
                              {/* Group Header */}
                              <div className="bg-surface-secondary/40 border-b border-border-subtle px-4 py-3 flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                      {!isSingleBus ? (
                                        <>
                                          <span className="text-xs font-black text-content-primary uppercase tracking-wider">{t('hardware.editRobotModal.componentLabel')}: {busName}</span>

                                          {/* Connection display (read-only) shown here only when multiple motorbuses */}
                                          <div className="w-[300px]">
                                             {conn ? (
                                               <div className="text-sm font-medium">
                                                 {robot?.status !== 'offline' && conn.interface ? `${conn.interface}${conn.serial_number ? ` (SN:${conn.serial_number})` : ''}` : '—'}
                                               </div>
                                             ) : (
                                               <span className="text-sm text-content-tertiary">{t('hardware.common.selectDevicePlaceholder')}</span>
                                             )}
                                          </div>
                                        </>
                                      ) : null}
                                  </div>

                                  {/* Per-group status badge (online/offline based on interface presence) */}
                                  <div className="ml-4">
                                     <StatusIcon status={conn && conn.interface ? 'available' : 'offline'} />
                                  </div>

                              </div> 

                              {/* Bus Details */}
                              {conn && (
                                 <div className="px-5 py-2 flex items-center gap-6 border-b border-border-subtle bg-surface-primary/50 text-[11px] text-content-secondary">
                                    <span className="flex items-center gap-1.5"><span className="text-content-tertiary font-bold uppercase tracking-wider">{t('hardware.common.interfaces')}:</span> <span className="font-mono text-content-primary">{robot?.status !== 'offline' && conn.interface ? conn.interface : '—'}</span></span>
                                    <span className="h-3 w-px bg-border-subtle/80" />
                                    <span className="flex items-center gap-1.5"><span className="text-content-tertiary font-bold uppercase tracking-wider">{t('hardware.common.sn')}:</span> <span className="font-mono text-content-primary">{conn.serial_number || 'N/A'}</span></span>
                                    <span className="h-3 w-px bg-border-subtle/80" />
                                    <span className="flex items-center gap-1.5"><span className="text-content-tertiary font-bold uppercase tracking-wider">{t('hardware.common.baudrate')}:</span> <span className="font-mono text-content-primary">{conn.baudrate ? `${conn.baudrate} ${t('hardware.common.baudrateUnit')}` : t('hardware.common.baudrateAuto')}</span></span>
                                 </div>
                              )}

                              {/* Motor List */}
                              <div className="p-4 bg-surface-primary">
                                 <div className="flex items-center gap-2 mb-3">
                                    <div className="w-1.5 h-1.5 rounded-full bg-content-tertiary" />
                                    <span className="text-[10px] font-bold text-content-tertiary uppercase tracking-widest">{t('hardware.common.motors', { count: Object.keys(busDef.motors || {}).length })}</span>
                                 </div>
                                 <div className="border border-border-subtle rounded-lg overflow-hidden">
                                    <table className="w-full text-left border-collapse">
                                       <thead className="bg-surface-secondary/40">
                                          <tr className="border-b border-border-subtle">
                                             <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.common.motorName')}</th>
                                             <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{hasPairIds ? `${t('hardware.common.sendId')} / ${t('hardware.common.recvId')}` : t('hardware.common.motorId')}</th>
                                             <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.editRobotModal.motorTable.model')}</th>
                                             <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.editRobotModal.motorTable.driveReversed')}</th>
                                             <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary text-right">{t('hardware.editRobotModal.motorTable.needCalibration')}</th>
                                          </tr>
                                       </thead>
                                       <tbody>
                                          {busDef.motors && Object.values(busDef.motors).length > 0 ? (
                                             Object.values(busDef.motors).map((motor: any, idx) => (
                                                <tr key={idx} className="hover:bg-surface-secondary/20 border-b border-border-subtle last:border-0 transition-colors">
                                                   <td className="py-2.5 px-4 font-bold text-xs text-content-primary w-[20%]">{motor.name}</td>
                                                   <td className="py-2.5 px-4 font-mono text-xs text-content-secondary w-[25%]">{renderMotorIdValue(motor.id)}</td>
                                                   <td className="py-2.5 px-4 text-xs text-content-secondary w-[25%]">{motor.variant || motor.model || '—'}</td>
                                                   <td className="py-2.5 px-4 text-xs text-content-secondary w-[20%]">
                                                      <div className="text-xs font-bold">
                                                         {motor.drive_mode === 1 ? (
                                                            <span role="img" aria-label={t('hardware.editRobotModal.inverted')} className="text-success-icon text-xs font-bold">✓</span>
                                                         ) : (
                                                            <span role="img" aria-label={t('hardware.editRobotModal.normal')} className="text-status-danger text-xs font-bold">✕</span>
                                                         )}
                                                      </div>
                                                   </td>
                                                   <td className="py-2.5 px-4 text-right text-xs text-content-primary w-[10%]">
                                                      {motor.need_calibration ? (
                                                         <span role="img" aria-label={t('common.yes')} className="text-success-icon text-xs font-bold">✓</span>
                                                      ) : (
                                                         <span role="img" aria-label={t('common.no')} className="text-status-danger text-xs font-bold">✕</span>
                                                      )}
                                                   </td>
                                                </tr>
                                             ))
                                          ) : (
                                             <tr>
                                                <td colSpan={5} className="h-24 text-center text-xs text-content-tertiary italic">{t('hardware.common.noMotorsFound')}</td>
                                             </tr>
                                          )}
                                       </tbody>
                                    </table>
                                 </div>
                              </div>
                           </div>
                        );
                    })
                  ) : (
                    <div className="text-sm text-content-tertiary border border-dashed border-border-default rounded-xl p-8 text-center bg-surface-secondary/10">
                       <AlertCircle className="w-6 h-6 mx-auto mb-2 opacity-20" />
                       {t('hardware.editRobotModal.noData')}
                    </div>
                  )}
               </div>
            </div>

            {/* Row 4: Calibration */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-content-primary">
                 <div className="p-1.5 rounded-md bg-surface-secondary text-primary"><Ruler className="w-4 h-4" /></div>
                 <h3 className="text-sm font-bold uppercase tracking-wide">{t('hardware.editRobotModal.calibrationTitle')}</h3>
              </div>
              
              <div className="border border-border-subtle rounded-xl overflow-hidden shadow-sm">
                 <table className="w-full text-left border-collapse">
                    <thead className="bg-surface-secondary/40">
                       <tr className="border-b border-border-subtle">
                          <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.common.motorName')}</th>
                          <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.editRobotModal.homingOffset')}</th>
                          <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.editRobotModal.rangeMin')}</th>
                          <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary">{t('hardware.editRobotModal.rangeMax')}</th>
                          <th className="h-9 px-4 text-[10px] font-black uppercase tracking-wider text-content-tertiary text-right">{t('hardware.common.driveMode')}</th>
                       </tr>
                    </thead>
                    <tbody>
                       {allCalibrations.length > 0 ? (
                          allCalibrations.map((cal: any, idx) => (
                             <tr key={idx} className="hover:bg-surface-secondary/20 border-b border-border-subtle last:border-0 transition-colors">
                                <td className="py-2.5 px-4 font-bold text-xs text-content-primary">{cal.name}</td>
                                <td className="py-2.5 px-4 font-mono text-xs text-content-secondary">{cal.homing_offset}</td>
                                <td className="py-2.5 px-4 font-mono text-xs text-content-secondary">{cal.range_min}</td>
                                <td className="py-2.5 px-4 font-mono text-xs text-content-secondary">{cal.range_max}</td>
                                <td className="py-2.5 px-4 text-right">
                                   <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${cal.drive_mode === 1 ? 'bg-status-warning/10 text-status-warning border-status-warning/20' : 'bg-surface-secondary text-content-tertiary border-border-default'}`}>
                                      {cal.drive_mode === 1 ? t('hardware.editRobotModal.inverted') : t('hardware.editRobotModal.normal')}
                                   </span>
                                </td>
                             </tr>
                          ))
                       ) : (
                          <tr>
                             <td colSpan={5} className="h-24 text-center text-xs text-content-tertiary italic">{t('hardware.editRobotModal.noData')}</td>
                          </tr>
                       )}
                    </tbody>
                 </table>
              </div>
            </div>

            {/* Row 5: Protection Settings */}
            <div className="space-y-4 pb-4">
               <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-content-primary">
                     <div className="p-1.5 rounded-md bg-surface-secondary text-primary"><ShieldCheck className="w-4 h-4" /></div>
                     <h3 className="text-sm font-bold uppercase tracking-wide">{t('hardware.editRobotModal.protectionTitle')}</h3>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setShowRestoreConfirm(true)} className="h-7 px-2 text-[10px] font-bold uppercase text-primary hover:text-primary-hover hover:bg-primary/10 gap-1.5">
                     <RotateCcw className="w-3 h-3" />
                     {t('hardware.editRobotModal.restoreDefaults')}
                  </Button>
               </div>

               <div className="space-y-6">
                 {Object.keys(protectionSettings).length === 0 ? (
                    <div className="text-center p-8 border border-dashed border-border-subtle rounded-xl bg-surface-secondary/5">
                       <p className="text-xs text-content-tertiary italic">{t('hardware.editRobotModal.noData')}</p>
                    </div>
                 ) : (
                    Object.entries(protectionSettings).map(([groupKey, limits]) => {
                        // groupKey may come in various formats (colon, pipe, comma, tuple-like). Parse robustly.
                        const { model, variant } = parseProtectionKey(String(groupKey));
                        const keyTitle = variant && variant !== "null" ? variant : (model || '—');
                        
                        return (
                           <div key={groupKey} className="space-y-3">
                              <div className="flex items-center gap-2 px-1">
                                 <div className="w-1 h-3 rounded-full bg-primary" />
                                 <h4 className="text-[11px] font-bold text-content-primary uppercase tracking-wider">{keyTitle}</h4>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                                 {limits.map((limit, idx) => (
                                    <div key={idx} className="bg-surface-secondary/30 rounded-lg p-2 border border-border-subtle hover:border-border-muted transition-colors group">
                                       <label className="text-[9px] font-black text-content-tertiary uppercase tracking-tighter truncate block mb-1.5 group-hover:text-content-secondary transition-colors" title={limit.type}>
                                          {limit.type.replace(/_/g, " ")}
                                       </label>
                                       <Input
                                          type="number"
                                          value={limit.value}
                                          aria-label={limit.type}
                                          title={limit.type}
                                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleLimitChange(groupKey, idx, e.target.value)}
                                          className="h-6 text-xs font-mono bg-surface-primary border-border-subtle focus-visible:ring-1 focus-visible:ring-primary/20 px-1.5"
                                       />
                                    </div>
                                 ))}
                              </div>
                           </div>
                        );
                    })
                 )}
               </div>
            </div>
            
          </>
        )}
         {/* Footer moved into scroll area */}
         <div className="space-y-4 pb-4 px-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
               {robot?.is_transient && (
                  <div className="flex items-center gap-2 text-status-warning bg-status-warning/5 px-3 py-1.5 rounded-lg border border-status-warning/10 animate-pulse">
                     <AlertTriangle className="w-4 h-4" />
                     <span className="text-[10px] font-bold uppercase tracking-wide leading-none">{t('hardware.editRobotModal.resetHint')}</span>
                  </div>
               )}
            </div>
            <div className="flex items-center gap-3">
                <Button variant="secondary" onClick={() => onClose()}>{t('common.cancel')}</Button>
                <Button onClick={handleSave} disabled={saving || !!nameError}>
                   {saving ? (
                      <>
                        <RefreshCw className="w-3 h-3 animate-spin mr-2" />
                        {t('hardware.editRobotModal.saving')}
                      </>
                   ) : (
                      <>
                        <Save className="w-3.5 h-3.5 mr-2" />
                        {t('common.save')}
                      </>
                   )}
                </Button>
            </div>
         </div>
      


      </div>

       {/* Restore Confirm MessageBox */}
       <MessageBox
         isOpen={showRestoreConfirm}
         onClose={() => setShowRestoreConfirm(false)}
         type="warning"
         title={t("hardware.editRobotModal.restoreDefaults")}
         message={t('hardware.editRobotModal.restoreConfirm')}
         description="This action cannot be undone."
         buttonType="ok-cancel"
         confirmText={t("hardware.editRobotModal.restoreConfirmAction")}
         onConfirm={handleRestoreDefaults}
       />

       {/* Error MessageBox */}
       <MessageBox
         isOpen={!!errorMsg}
         onClose={() => setErrorMsg(null)}
         type="error"
         title={t("common.error")}
         message={errorMsg || ""}
         buttonType="ok"
       />

    </Modal>
  );
};
