export type DeviceCategory = 'robot' | 'controller' | 'camera';
export type DeviceStatus = 'available' | 'offline' | 'occupied' | 'invalid';

export interface RobotMotorBusConnection {
  motor_bus_type: string;
  interface: string | null;
  baudrate: number;
  serial_number: string | null;
}

export interface MotorCalibration {
  name: string;
  drive_mode: number;
  homing_offset: number;
  range_min: number;
  range_max: number;
}

export interface RobotMotorDefinition {
  id: number | [number, number];
  name: string;
  variant: string | null;
  model: string;
  is_active: boolean;
  bus_id: number;
  drive_mode?: number; // 0 = normal, 1 = inverted
}

export interface MotorBusDefinition {
  type: string;
  motors: Record<string, RobotMotorDefinition>;
  baud_rate: number | null;
  interface_type: string | null;
}

export interface RobotDefinition {
  id: string;
  lerobot_name: string | null;
  display_name: string;
  description: string;
  support_version_from: string | null;
  support_version_end: string | null;
  device_category?: DeviceCategory;
  motor_buses: Record<string, MotorBusDefinition>;
}

export interface Robot {
  id: string;
  name: string;
  status: DeviceStatus;
  manufacturer: string | null;
  labels: Record<string, string>;
  created_at: string;
  is_transient: boolean;
  definition: RobotDefinition | string | null;
  motor_bus_connections: Record<string, RobotMotorBusConnection> | null;
  custom_protection_settings?: Record<string, { type: string; value: number }[]>;
  calibration_settings?: Record<string, MotorCalibration[]>;
  is_calibrated?: boolean;
}

export interface CameraSummary {
  index: number;
  name: string;
  width: number | null;
  height: number | null;
  available: boolean;
}

export interface MotorProtectionParams {
  temp_warning: number;
  temp_critical: number;
  temp_max: number;
  voltage_min: number;
  voltage_max: number;
  current_max: number;
  current_peak: number;
}

export interface MotorInfo {
  id: number;
  model: string;
  firmware_version?: string;
  protection?: MotorProtectionParams;
}

export interface ProtectionViolation {
  type: string;
  value: number;
  limit: number;
}

export interface ProtectionStatus {
  status: 'ok' | 'warning' | 'critical';
  violations: ProtectionViolation[];
}

export interface MotorTelemetry {
  motor_id: number | [number, number];
  position: number | null;
  position_type: 'raw' | 'calibrated' | 'normalized' | 'raw_in_radian' | 'calibrated_in_radian';
  goal_position: number | null;
  velocity: number;
  torque: number | null;
  current: number | null;
  temperature: number | null;
  voltage: number | null;
  moving: boolean;
  error: number;
  protection_status: ProtectionStatus;
}

export interface MotorBusData {
  bus_name: string;
  motors: Record<string, MotorTelemetry>;
}

export interface RobotTelemetryFrame {
  timestamp: number;
  motor_buses: Record<string, MotorBusData>;
  actual_fps: number;
  normalized: boolean;
}

// WebSocket Message Types
export interface TelemetryMessage {
  type: 'telemetry';
  frame: RobotTelemetryFrame;
}

export interface SessionInitMessage {
  type: 'session_init';
  robot_id: string;
  normalized: boolean;
  fps: number;
}

export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

export interface CommandAckMessage {
  type: 'ack';
  command_type: string;
  success: boolean;
  message?: string;
}

export interface CalibrationStateMessage {
  type: 'calibration_state';
  step_index: number;
  step_count: number;
  is_complete: boolean;
  method_id: string;
  step_descriptions: string[];
}

export interface CalibrationMethod {
  method_id: string;
  steps: string[];
}
