import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ChevronDown,
  ChevronUp,
  Activity,
  Box,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import { PageContainer } from '../../components/ui/page-container';
import { RobotViewer } from '../../components/robot-viewer';
import type { CalibrationEntry } from '../../components/robot-viewer/robot-canvas';
import { Button } from '../../components/ui/button';
import { Select } from '../../components/ui/select';
import { MotorGaugeGroup } from '../../components/ui/motor-gauge-group';
import { LoadingOverlay } from '../../components/ui/loading-overlay';
import { useRobotTelemetry } from '../../hooks/use-robot-telemetry';
import { CalibrationMethod, Robot } from '../../types/hardware';
import { MotorGaugeProps } from '../../components/ui/motor-gauge';
import { cn } from '../../utils/cn';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CalibrationPhase = 'idle' | 'started' | 'complete' | 'saved';

/** Per-motor running min/max position (radians) tracked during calibration. */
type MotorMinMaxMap = Record<
  string,
  Record<string, { min: number | null; max: number | null }>
>;

// ---------------------------------------------------------------------------
// Collapsible section (right column)
// ---------------------------------------------------------------------------

interface SectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

function Section({ title, icon, children, defaultExpanded = true }: SectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="border-border-default bg-surface-card flex flex-col overflow-hidden rounded-xl border shadow-sm transition-all duration-300">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="hover:bg-surface-secondary/50 flex items-center justify-between p-4 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 text-primary rounded-lg p-2">{icon}</div>
          <h3 className="text-content-primary text-lg font-semibold">{title}</h3>
        </div>
        {isExpanded ? (
          <ChevronUp className="text-content-tertiary h-5 w-5" />
        ) : (
          <ChevronDown className="text-content-tertiary h-5 w-5" />
        )}
      </button>
      <div
        className={cn(
          'overflow-hidden transition-all duration-300',
          isExpanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0',
        )}
      >
        <div className="border-border-default border-t p-4">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function HardwareCalibrationPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  // Robot data state
  const [robot, setRobot] = useState<Robot | null>(null);
  const [loading, setLoading] = useState(true);

  // Calibration method selection
  const [methods, setMethods] = useState<CalibrationMethod[]>([]);
  const [selectedMethodId, setSelectedMethodId] = useState<string>('');
  const [methodsLoading, setMethodsLoading] = useState(true);

  // Calibration phase
  const [phase, setPhase] = useState<CalibrationPhase>('idle');
  const [isSaving, setIsSaving] = useState(false);

  // Per-motor running min/max positions tracked from telemetry
  const [motorMinMax, setMotorMinMax] = useState<MotorMinMaxMap>({});
  // Reset only happens once �?after the first "Next Step" click
  const [hasResetMinMax, setHasResetMinMax] = useState(false);

  // Active bus tab when robot has multiple buses
  const [activeBusTab, setActiveBusTab] = useState<string>('');

  // API language code derived from current UI locale
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  const { telemetry, calibrationState, status, isConnected, sendCommand } =
    useRobotTelemetry({
      device_id: id || '',
      fps: 10,
    });

  // ------------------------------------------------------------------
  // Robot data fetch
  // ------------------------------------------------------------------

  const fetchRobot = useCallback(async () => {
    if (!id) return;
    try {
      const res = await fetch(`/api/hardware/robots/${id}?calibration_unit=radian`);
      if (res.ok) {
        const data: Robot = await res.json();
        setRobot(data);
      }
    } catch (err) {
      console.error('Failed to fetch robot:', err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRobot();
  }, [fetchRobot]);

  // ------------------------------------------------------------------
  // Flat motor-name → CalibrationEntry map derived from robot.calibration_settings.
  // range_min/range_max are in RAW_IN_RADIAN units because the robot is fetched
  // with calibration_unit=radian, matching the telemetry position unit.
  const viewerCalibration = useMemo<Record<string, CalibrationEntry>>(() => {
    if (!robot?.calibration_settings) return {};
    const map: Record<string, CalibrationEntry> = {};
    for (const cals of Object.values(robot.calibration_settings)) {
      for (const cal of cals) {
        map[cal.name] = {
          range_min: cal.range_min,
          range_max: cal.range_max,
          drive_mode: cal.drive_mode,
        };
      }
    }
    return map;
  }, [robot?.calibration_settings]);

  // ------------------------------------------------------------------

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(
          `/api/hardware/robots/${id}/available_calibration_methods?lang=${lang}`,
        );
        if (res.ok && !cancelled) {
          const data: CalibrationMethod[] = await res.json();
          setMethods(data);
          if (data.length > 0) setSelectedMethodId(data[0].method_id);
        }
      } catch (err) {
        console.error('Failed to fetch calibration methods:', err);
      } finally {
        if (!cancelled) setMethodsLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [id, lang]);

  // ------------------------------------------------------------------
  // Initialize motorMinMax and active bus tab from robot data
  // ------------------------------------------------------------------

  useEffect(() => {
    if (!robot) return;

    // Pre-populate min/max from existing calibration settings (if calibrated)
    if (robot.is_calibrated && robot.calibration_settings) {
      const minMax: MotorMinMaxMap = {};
      Object.entries(robot.calibration_settings).forEach(([busName, cals]) => {
        minMax[busName] = {};
        cals.forEach((cal) => {
          minMax[busName][cal.name] = { min: cal.range_min, max: cal.range_max };
        });
      });
      setMotorMinMax(minMax);
    }

    // Set default active bus tab
    if (robot.definition && typeof robot.definition === 'object') {
      const buses = Object.keys(robot.definition.motor_buses || {});
      if (buses.length > 0) setActiveBusTab(buses[0]);
    }
  }, [robot]);

  // ------------------------------------------------------------------
  // Sync calibrationState �?phase
  // ------------------------------------------------------------------

  useEffect(() => {
    if (!calibrationState) return;
    setPhase(calibrationState.is_complete ? 'complete' : 'started');
  }, [calibrationState]);

  // ------------------------------------------------------------------
  // Live min/max tracking from telemetry during recording step
  // ------------------------------------------------------------------

  useEffect(() => {
    // Only track after the first "Next Step" confirms recording has started
    if (!telemetry || !hasResetMinMax || phase !== 'started') return;

    setMotorMinMax((prev) => {
      let changed = false;
      const next = { ...prev };
      Object.entries(telemetry.motor_buses).forEach(([busName, busData]) => {
        Object.entries(busData.motors).forEach(([motorName, mot]) => {
          if (mot.position === null) return;
          const cur = next[busName]?.[motorName] ?? { min: null, max: null };
          const newMin =
            cur.min === null ? mot.position : Math.min(cur.min, mot.position);
          const newMax =
            cur.max === null ? mot.position : Math.max(cur.max, mot.position);
          if (newMin !== cur.min || newMax !== cur.max) {
            changed = true;
            next[busName] = { ...(next[busName] ?? {}) };
            next[busName][motorName] = { min: newMin, max: newMax };
          }
        });
      });
      return changed ? next : prev;
    });
  }, [telemetry, hasResetMinMax, phase]);

  // ------------------------------------------------------------------
  // Action handlers
  // ------------------------------------------------------------------

  const handleStart = useCallback(() => {
    if (!selectedMethodId || !isConnected) return;
    sendCommand({ type: 'calibration_start', method_id: selectedMethodId, lang });
  }, [selectedMethodId, isConnected, sendCommand, lang]);

  const handleNextStep = useCallback(() => {
    if (!isConnected) return;
    // On the first "Next Step" click: reset tracked positions to null
    if (!hasResetMinMax) {
      const emptyMinMax: MotorMinMaxMap = {};
      if (robot?.definition && typeof robot.definition === 'object') {
        Object.entries(robot.definition.motor_buses || {}).forEach(
          ([busName, busDef]) => {
            emptyMinMax[busName] = {};
            Object.keys(busDef.motors || {}).forEach((motorName) => {
              emptyMinMax[busName][motorName] = { min: null, max: null };
            });
          },
        );
      }
      setMotorMinMax(emptyMinMax);
      setHasResetMinMax(true);
    }
    sendCommand({ type: 'calibration_next' });
  }, [isConnected, hasResetMinMax, robot, sendCommand]);

  const handleSave = useCallback(async () => {
    if (!isConnected || isSaving) return;
    setIsSaving(true);
    try {
      sendCommand({ type: 'calibration_save' });
      // Refresh robot to reflect the newly saved calibration_settings
      await fetchRobot();
      setPhase('saved');
    } finally {
      setIsSaving(false);
    }
  }, [isConnected, isSaving, sendCommand, fetchRobot]);

  const handleDone = useCallback(() => navigate('/hardware'), [navigate]);
  const handleCancel = useCallback(() => navigate('/hardware'), [navigate]);

  // ------------------------------------------------------------------
  // Derived data: gauge groups with live rangeMin/rangeMax
  // ------------------------------------------------------------------

  const gaugeGroups = useMemo(() => {
    const groups: Record<string, Record<string, MotorGaugeProps>> = {};

    if (robot?.definition && typeof robot.definition === 'object') {
      Object.entries(robot.definition.motor_buses || {}).forEach(
        ([busName, busDef]) => {
          groups[busName] = {};
          Object.keys(busDef.motors || {}).forEach((motorName) => {
            groups[busName][motorName] = { speed: 0, angle: 0, limitMax: 120 };
          });
        },
      );
    }

    if (telemetry?.motor_buses) {
      Object.entries(telemetry.motor_buses).forEach(([busName, busData]) => {
        if (!groups[busName]) groups[busName] = {};
        Object.entries(busData.motors).forEach(([motorName, m]) => {
          const cur = groups[busName][motorName] ?? {
            speed: 0,
            angle: 0,
            limitMax: 120,
          };
          groups[busName][motorName] = {
            ...cur,
            speed: m.velocity,
            angle: m.position ?? 0,
          };
        });
      });
    }

    // Overlay position range from calibration tracking as limit angle markers
    Object.entries(motorMinMax).forEach(([busName, motors]) => {
      Object.entries(motors).forEach(([motorName, { min, max }]) => {
        if (!groups[busName]?.[motorName]) return;
        if (min !== null) groups[busName][motorName].limitAngleMin = min;
        if (max !== null) groups[busName][motorName].limitAngleMax = max;
      });
    });

    return groups;
  }, [robot, telemetry, motorMinMax]);

  // ------------------------------------------------------------------
  // Derived data: bus list and motor table rows
  // ------------------------------------------------------------------

  const busList = useMemo(() => {
    if (!robot?.definition || typeof robot.definition !== 'object') return [];
    return Object.keys(robot.definition.motor_buses || {});
  }, [robot]);

  const motorTableData = useMemo(() => {
    if (!robot?.definition || typeof robot.definition !== 'object') return {};
    const table: Record<
      string,
      { id: string; name: string; min: number | null; max: number | null }[]
    > = {};
    Object.entries(robot.definition.motor_buses).forEach(([busName, busDef]) => {
      table[busName] = Object.entries(busDef.motors || {}).map(
        ([motorName, motorDef]) => {
          const minMax = motorMinMax[busName]?.[motorName] ?? { min: null, max: null };
          const rawId = motorDef.id;
          const motorId = Array.isArray(rawId) ? rawId.join(',') : String(rawId);
          return { id: motorId, name: motorName, min: minMax.min, max: minMax.max };
        },
      );
    });
    return table;
  }, [robot, motorMinMax]);

  // ------------------------------------------------------------------
  // Step highlight helpers
  // ------------------------------------------------------------------

  // Use descriptions from calibrationState if available; fall back to selected method
  const selectedMethod = methods.find((m) => m.method_id === selectedMethodId);
  const stepDescriptions =
    calibrationState?.step_descriptions ?? selectedMethod?.steps ?? [];
  const currentStepIndex = calibrationState?.step_index ?? -1;

  // ------------------------------------------------------------------
  // Button state
  // ------------------------------------------------------------------

  const getActionLabel = (): string => {
    if (phase === 'idle') return t('hardware.calibration.buttons.start');
    if (phase === 'started') return t('hardware.calibration.buttons.nextStep');
    if (phase === 'complete')
      return isSaving
        ? t('hardware.calibration.status.saving')
        : t('hardware.calibration.buttons.save');
    return t('hardware.calibration.buttons.done');
  };

  const handleAction = () => {
    if (phase === 'idle') handleStart();
    else if (phase === 'started') handleNextStep();
    else if (phase === 'complete') void handleSave();
    else handleDone();
  };

  const actionDisabled =
    !isConnected ||
    isSaving ||
    (phase === 'idle' && (!selectedMethodId || methodsLoading));

  // ------------------------------------------------------------------
  // Render guards
  // ------------------------------------------------------------------

  if (loading) {
    return <LoadingOverlay message={t('hardware.editRobotModal.loading')} fancy />;
  }

  if (!robot) {
    return (
      <PageContainer>
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4">
          <AlertCircle className="text-content-tertiary h-12 w-12" />
          <p className="text-content-secondary">
            {t('hardware.editRobotModal.noData')}
          </p>
          <Button onClick={() => navigate('/hardware')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('wizard.buttons.back')}
          </Button>
        </div>
      </PageContainer>
    );
  }

  const hasUrdf =
    robot.definition && typeof robot.definition === 'object' && robot.definition.id;

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <PageContainer>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate('/hardware')}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-content-primary text-2xl font-bold">
                {t('hardware.calibration.title')} �?{robot.name}
              </h1>
              <div className="mt-1 flex items-center gap-2">
                <div
                  className={cn(
                    'h-2 w-2 rounded-full',
                    status === 'connected' ? 'bg-green-500' : 'bg-red-500',
                  )}
                />
                <span className="text-content-secondary text-xs font-medium tracking-wider uppercase">
                  {status}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Main content �?two columns */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* ------------------------------------------------- */}
          {/* Left column: Calibration panel                      */}
          {/* ------------------------------------------------- */}
          {/* min-h accounts for header + page padding so buttons always stay in viewport */}
          <div className="flex min-h-[calc(100vh-12rem)] flex-col lg:col-span-4">
            <div className="border-border-default bg-surface-card flex flex-1 flex-col gap-5 rounded-xl border p-6 shadow-sm">
              {/* Method selector �?hidden when only one option */}
              {!methodsLoading && methods.length > 1 && (
                <div>
                  <label className="text-content-secondary mb-1.5 block text-xs font-medium tracking-wider uppercase">
                    {t('hardware.calibration.method.select')}
                  </label>
                  <Select
                    value={selectedMethodId}
                    onChange={(e) => setSelectedMethodId(e.target.value)}
                    disabled={phase !== 'idle'}
                    options={methods.map((m) => ({
                      label: m.method_id,
                      value: m.method_id,
                    }))}
                  />
                </div>
              )}

              {methodsLoading && (
                <p className="text-content-secondary text-sm">
                  {t('hardware.calibration.loadingMethods')}
                </p>
              )}

              {!methodsLoading && methods.length === 0 && (
                <p className="text-sm text-yellow-600 dark:text-yellow-400">
                  {t('hardware.calibration.noMethods')}
                </p>
              )}

              {/* Step list */}
              {stepDescriptions.length > 0 && (
                <div>
                  <h3 className="text-content-secondary mb-3 text-xs font-medium tracking-wider uppercase">
                    {t('hardware.calibration.steps.label')}
                  </h3>
                  <ol className="space-y-2">
                    {stepDescriptions.map((desc, idx) => {
                      // A step is "done" when:
                      // - All steps are done (phase saved, or is_complete and current > this idx)
                      const isDone =
                        phase === 'saved' ||
                        calibrationState?.is_complete === true ||
                        (currentStepIndex !== -1 && currentStepIndex > idx);
                      const isActive = !isDone && currentStepIndex === idx;

                      return (
                        <li
                          key={idx}
                          className={cn(
                            'flex items-start gap-3 rounded-lg p-3 text-sm transition-colors',
                            isActive && 'bg-primary/10 border-primary/20 border',
                          )}
                        >
                          <span className="mt-0.5 flex-shrink-0">
                            {isDone ? (
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                            ) : isActive ? (
                              <div className="border-primary bg-primary/20 h-4 w-4 rounded-full border-2" />
                            ) : (
                              <Circle className="text-content-tertiary h-4 w-4" />
                            )}
                          </span>
                          <span
                            className={cn(
                              'flex-1 leading-snug',
                              isActive && 'text-content-primary font-medium',
                              isDone && 'text-content-secondary line-through',
                              !isActive && !isDone && 'text-content-secondary',
                            )}
                          >
                            {idx + 1}. {desc}
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                </div>
              )}

              {/* Motor position table */}
              {busList.length > 0 && (
                <div className="min-h-0 flex-1">
                  <h3 className="text-content-secondary mb-3 text-xs font-medium tracking-wider uppercase">
                    {t('hardware.calibration.table.busTitle')}
                  </h3>

                  {/* Bus tabs �?only shown when robot has multiple buses */}
                  {busList.length > 1 && (
                    <div className="border-border-subtle mb-3 flex gap-1 border-b">
                      {busList.map((bus) => (
                        <button
                          key={bus}
                          onClick={() => setActiveBusTab(bus)}
                          className={cn(
                            'rounded-t-md px-3 py-1.5 text-sm font-medium transition-colors',
                            activeBusTab === bus
                              ? 'border-primary text-content-primary border-b-2'
                              : 'text-content-secondary hover:text-content-primary',
                          )}
                        >
                          {bus}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Table */}
                  {(() => {
                    const activeBus = busList.length === 1 ? busList[0] : activeBusTab;
                    const rows = motorTableData[activeBus] ?? [];
                    return (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-border-subtle border-b">
                              <th className="text-content-secondary px-2 py-2 text-left font-medium">
                                {t('hardware.calibration.table.motorId')}
                              </th>
                              <th className="text-content-secondary px-2 py-2 text-left font-medium">
                                {t('hardware.calibration.table.name')}
                              </th>
                              <th className="text-content-secondary px-2 py-2 text-right font-medium">
                                {t('hardware.calibration.table.minPosition')}
                              </th>
                              <th className="text-content-secondary px-2 py-2 text-right font-medium">
                                {t('hardware.calibration.table.maxPosition')}
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row) => (
                              <tr
                                key={row.name}
                                className="border-border-subtle/50 hover:bg-surface-secondary/30 border-b transition-colors"
                              >
                                <td className="text-content-secondary px-2 py-2 font-mono">
                                  {row.id}
                                </td>
                                <td className="text-content-primary px-2 py-2">
                                  {row.name}
                                </td>
                                <td className="text-content-primary px-2 py-2 text-right font-mono tabular-nums">
                                  {row.min !== null
                                    ? row.min.toFixed(3)
                                    : t('hardware.calibration.table.notRecorded')}
                                </td>
                                <td className="text-content-primary px-2 py-2 text-right font-mono tabular-nums">
                                  {row.max !== null
                                    ? row.max.toFixed(3)
                                    : t('hardware.calibration.table.notRecorded')}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {hasResetMinMax && phase === 'started' && (
                          <p className="text-content-tertiary mt-2 text-xs italic">
                            {t('hardware.calibration.table.trackingNote')}
                          </p>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Push buttons to the bottom */}
              <div className="flex-1" />

              {/* Action buttons �?always at the bottom of the left panel */}
              <div className="border-border-subtle flex items-center justify-between border-t pt-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                  disabled={isSaving}
                >
                  <ArrowLeft className="mr-1.5 h-4 w-4" />
                  {t('hardware.calibration.buttons.cancel')}
                </Button>
                <Button onClick={handleAction} disabled={actionDisabled}>
                  {getActionLabel()}
                </Button>
              </div>
            </div>
          </div>

          {/* ------------------------------------------------- */}
          {/* Right column: Motor telemetry + URDF                */}
          {/* ------------------------------------------------- */}
          <div className="space-y-6 lg:col-span-8">
            {/* Real-time motor gauges */}
            <Section
              title={t('hardware.calibration.sections.telemetry')}
              icon={<Activity className="h-5 w-5" />}
            >
              <div className="space-y-6">
                {Object.keys(gaugeGroups).length > 0 ? (
                  Object.entries(gaugeGroups).map(([busName, motors]) => (
                    <MotorGaugeGroup
                      key={busName}
                      title={Object.keys(gaugeGroups).length > 1 ? busName : undefined}
                      motors={motors}
                    />
                  ))
                ) : (
                  <div className="text-content-tertiary flex flex-col items-center justify-center py-12">
                    <Activity className="mb-2 h-10 w-10 opacity-20" />
                    <p>
                      {status === 'connected'
                        ? t('hardware.common.noMotorsFound')
                        : t('hardware.cameraPreview.establishing')}
                    </p>
                  </div>
                )}
              </div>
            </Section>

            {/* 3D URDF viewer (conditional) */}
            {hasUrdf && (
              <Section
                title={t('hardware.calibration.sections.urdf')}
                icon={<Box className="h-5 w-5" />}
                defaultExpanded={true}
              >
                <RobotViewer robotId={robot.id} telemetry={telemetry} calibration={viewerCalibration} />
              </Section>
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
