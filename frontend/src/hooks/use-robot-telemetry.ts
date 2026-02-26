import { useState, useEffect, useRef, useCallback } from 'react';
import { CalibrationStateMessage, RobotTelemetryFrame } from '../types/hardware';

interface UseRobotTelemetryOptions {
    device_id: string;
    normalized?: boolean;
    fps?: number;
}

export function useRobotTelemetry({
    device_id,
    normalized = false,
    fps = 10
}: UseRobotTelemetryOptions) {
    const [telemetry, setTelemetry] = useState<RobotTelemetryFrame | null>(null);
    const [calibrationState, setCalibrationState] = useState<CalibrationStateMessage | null>(null);
    const [status, setStatus] = useState<'connecting' | 'connected' | 'error' | 'disconnected'>('disconnected');
    const [error, setError] = useState<string | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const heartbeatIntervalRef = useRef<number | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const intentionalCloseRef = useRef(false); // Track intentional close vs unexpected disconnect

    const connect = useCallback(() => {
        if (!device_id) return;

        // Prevent creating duplicate connections if one is already open/connecting/closing
        // This handles React StrictMode double-mounting where cleanup happens between renders
        const existing = wsRef.current;
        if (existing && existing.readyState !== WebSocket.CLOSED) {
            console.log(`Skipping reconnect: existing connection state=${existing.readyState}`);
            return;
        }

        intentionalCloseRef.current = false; // Reset flag for new connection
        setStatus('connecting');
        setError(null);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/api/ws/hardware/robots/${device_id}?normalized=${normalized}&fps=${fps}`;

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log(`Telemetry WS connected: ${device_id}`);
            setStatus('connected');
            reconnectAttemptsRef.current = 0; // Reset reconnect counter on success
            
            // Start heartbeat interval (send every 2 seconds, timeout is 5 seconds)
            if (heartbeatIntervalRef.current !== null) {
                window.clearInterval(heartbeatIntervalRef.current);
            }
            heartbeatIntervalRef.current = window.setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'heartbeat' }));
                }
            }, 2000);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'telemetry' && data.frame) {
                    setTelemetry(data.frame);
                } else if (data.type === 'calibration_state') {
                    setCalibrationState(data as CalibrationStateMessage);
                } else if (data.type === 'error') {
                    setError(data.message || 'Unknown server error');
                    setStatus('error');
                    console.error('[Telemetry] Server error:', data);
                } else if (data.type === 'command_ack') {
                    // Heartbeat acknowledgment - connection is healthy
                    console.debug('[Telemetry] Command ack:', data.command_type);
                } else if (data.type === 'session_init') {
                    // Session initialized successfully
                    console.log('[Telemetry] Session initialized:', data);
                } else {
                    console.warn('[Telemetry] Unknown message type:', data.type, data);
                }
            } catch (err) {
                console.error('Failed to parse telemetry message:', err);
            }
        };

        ws.onerror = (event) => {
            console.error('Telemetry WS error:', event);
            setStatus('error');
            setError('WebSocket connection error');
        };

        ws.onclose = (event) => {
            console.log(`Telemetry WS disconnected: ${device_id}, code=${event.code}, reason=${event.reason}`);
            
            // Clear heartbeat interval
            if (heartbeatIntervalRef.current !== null) {
                window.clearInterval(heartbeatIntervalRef.current);
                heartbeatIntervalRef.current = null;
            }
            
            // Preserve error state if already set by onerror
            setStatus((s) => (s === 'error' ? 'error' : 'disconnected'));

            // Auto reconnect logic - only if not intentionally closed
            if (!intentionalCloseRef.current && reconnectTimerRef.current === null) {
                // Only stop retrying for permanent errors (device not found or invalid hardware)
                const shouldRetry = event.code !== 4004; // Don't retry if device not found
                
                if (!shouldRetry) {
                    console.warn(`Device not found (code ${event.code}), stopping reconnection attempts`);
                    setError(`Device not found: ${event.reason || 'Unknown reason'}`);
                    return;
                }
                
                // For all other errors (including OFFLINE status), use exponential backoff
                reconnectAttemptsRef.current += 1;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current - 1), 16000);
                
                console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})...`);
                
                reconnectTimerRef.current = window.setTimeout(() => {
                    reconnectTimerRef.current = null;
                    connect();
                }, delay);
            }
        };
    }, [device_id, normalized, fps]);

    useEffect(() => {
        connect();
        return () => {
            // Cleanup: close WebSocket and clear timers
            intentionalCloseRef.current = true; // Mark as intentional close
            
            // Clear heartbeat interval
            if (heartbeatIntervalRef.current !== null) {
                window.clearInterval(heartbeatIntervalRef.current);
                heartbeatIntervalRef.current = null;
            }
            
            // Clear reconnect timer
            if (reconnectTimerRef.current !== null) {
                window.clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            
            // Close WebSocket
            const ws = wsRef.current;
            if (ws && ws.readyState !== WebSocket.CLOSED) {
                console.log(`Cleaning up WebSocket (state=${ws.readyState}) for ${device_id}`);
                ws.close();
                // Important: set to null to prevent reuse of closing/closed connection
                wsRef.current = null;
            }
        };
    }, [connect, device_id]);

    const sendCommand = useCallback((cmd: object) => {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(cmd));
        } else {
            console.warn('[Telemetry] Cannot send command — WebSocket not open:', cmd);
        }
    }, []);

    return {
        telemetry,
        calibrationState,
        status,
        error,
        isConnected: status === 'connected',
        sendCommand,
    };
}

