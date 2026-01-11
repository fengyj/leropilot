export type DeviceCategory = 'robot' | 'controller' | 'camera';
export type DeviceStatus = 'available' | 'offline' | 'occupied' | 'invalid';

export interface RobotMotorBusConnection {
  motor_bus_type: string;
  interface: string | null;
  baudrate: number;
  serial_number: string | null;
}

export interface RobotMotorDefinition {
  id: number;
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
  urdf: string | null;
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

export interface MotorTelemetry {
  id: number;
  present_position: number;
  present_velocity: number;
  present_current: number;
  present_voltage: number;
  present_temperature: number;
  error?: number;
  moving?: boolean;
}

// WebSocket Types
export type WebSocketMessageType = 
  | 'telemetry' 
  | 'event' 
  | 'ack' 
  | 'start_telemetry' 
  | 'stop_telemetry' 
  | 'command' 
  | 'emergency_stop';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  timestamp?: number;
  payload?: any;
}

export interface TelemetryMessage extends WebSocketMessage {
  type: 'telemetry';
  payload: {
    motors: MotorTelemetry[];
  };
}

export interface EventMessage extends WebSocketMessage {
  type: 'event';
  payload: {
    code: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    details?: any;
  };
}

export interface MotorCommand {
  id: number;
  goal_position?: number;
  goal_velocity?: number;
  torque_enabled?: boolean;
}

export interface BulkMotorCommand {
  commands: MotorCommand[];
}
