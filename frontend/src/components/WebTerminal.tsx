import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { light, oneDark } from './terminal-themes';
import { useTheme } from '../contexts/theme-context';
import { ShellIntegration, ShellEvent } from './ShellIntegration';

export type TerminalStatus = 'Idle' | 'Running' | 'Error' | 'Success';

interface TerminalProps {
  apiHost?: string;
  sessionId?: string;
  themeMode?: 'light' | 'dark';
  onStatusChange?: (status: TerminalStatus) => void;
  onOutput?: (data: string) => void;
  onInput?: (data: string) => void;
  onShellEvent?: (event: ShellEvent) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

const WebTerminal: React.FC<TerminalProps> = ({
  apiHost,
  sessionId,
  themeMode: propThemeMode,
  onStatusChange,
  onOutput,
  onInput,
  onShellEvent,
  onConnected,
  onDisconnected,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termInstance = useRef<Terminal | null>(null);
  const [status, setStatus] = useState<TerminalStatus>('Idle');
  const { effectiveTheme } = useTheme();

  // Use prop override if provided, otherwise use context theme
  const activeThemeMode = propThemeMode || effectiveTheme;

  // Effect to handle theme changes dynamically
  useEffect(() => {
    if (termInstance.current) {
      termInstance.current.options.theme =
        activeThemeMode === 'light' ? light : oneDark;
    }
  }, [activeThemeMode]);

  // Notify parent of status changes
  useEffect(() => {
    onStatusChange?.(status);
  }, [status, onStatusChange]);

  // Store callbacks in refs to avoid unnecessary reconnections
  const onInputRef = useRef(onInput);
  const onOutputRef = useRef(onOutput);
  const onShellEventRef = useRef(onShellEvent);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);

  // Update refs when callbacks change
  useEffect(() => {
    onInputRef.current = onInput;
    onOutputRef.current = onOutput;
    onShellEventRef.current = onShellEvent;
    onConnectedRef.current = onConnected;
    onDisconnectedRef.current = onDisconnected;
  });

  useEffect(() => {
    if (!containerRef.current || !sessionId) return;

    // 1. Setup Xterm.js
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Consolas, "Courier New", monospace',
      theme: activeThemeMode === 'light' ? light : oneDark,
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();

    term.loadAddon(fitAddon);
    term.open(containerRef.current);

    // Wait for renderer to be ready
    requestAnimationFrame(() => {
      try {
        fitAddon.fit();
      } catch (e) {
        console.warn('Failed to fit terminal:', e);
      }
    });

    termInstance.current = term;

    // 2. Initialize Shell Integration
    const shellIntegration = new ShellIntegration(term, {
      onShellEvent: (event) => {
        onShellEventRef.current?.(event);

        // Update status based on events
        if (event.type === 'command_start') {
          setStatus('Running');
        } else if (event.type === 'command_finished') {
          setStatus(event.exitCode === 0 ? 'Success' : 'Error');

          // Optional: Visual feedback
          if (event.exitCode !== 0) {
            term.write('\x1b[31m✘\x1b[0m ');
          }
        }
      },
    });

    // 2. Connect to Backend
    const connect = async () => {
      if (!sessionId) {
        term.write('\r\n\x1b[31mError: No session ID provided\x1b[0m\r\n');
        setStatus('Error');
        return;
      }

      try {
        let wsUrl: string;

        // Use provided session ID
        if (apiHost) {
          wsUrl = apiHost.replace(/^http/, 'ws') + `/api/ws/pty_sessions/${sessionId}`;
        } else {
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          wsUrl = `${protocol}//${window.location.host}/api/ws/pty_sessions/${sessionId}`;
        }

        console.log(`[WebTerminal] Connecting to WebSocket: ${wsUrl}`);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          term.focus();
          setStatus('Running'); // Assume running when connected

          // Send initial resize to match terminal dimensions
          ws.send(
            JSON.stringify({
              type: 'resize',
              cols: term.cols,
              rows: term.rows,
            }),
          );
          onConnectedRef.current?.();
        };

        ws.onmessage = (ev) => {
          // Render data from backend (includes shell output + system messages)
          term.write(ev.data);
          onOutputRef.current?.(ev.data);
        };

        ws.onerror = (error) => {
          console.error(
            `[WebTerminal] WebSocket error for session ${sessionId}:`,
            error,
          );
          term.write('\r\n\x1b[31m[Connection Error]\x1b[0m\r\n');
        };

        ws.onclose = (event) => {
          console.log(
            `[WebTerminal] WebSocket closed for session ${sessionId}, code: ${event.code}, reason: ${event.reason}`,
          );
          term.write('\r\n\x1b[33m[Connection Closed]\x1b[0m\r\n');
          setStatus('Idle');
          onDisconnectedRef.current?.();
        };

        // 3. Input Handling (Native Mode)
        term.onData((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'input', data }));
            onInputRef.current?.(data);
          }
        });

        // Resize Handling
        const handleResize = () => {
          fitAddon.fit();
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                type: 'resize',
                cols: term.cols,
                rows: term.rows,
              }),
            );
          }
        };
        window.addEventListener('resize', handleResize);

        return () => {
          window.removeEventListener('resize', handleResize);
          ws.close();
        };
      } catch (err) {
        term.write(`\r\n\x1b[31mError: ${err}\x1b[0m\r\n`);
        setStatus('Error');
      }
    };

    const cleanupPromise = connect();

    return () => {
      cleanupPromise.then((cleanup) => cleanup && cleanup());
      shellIntegration.dispose();
      term.dispose();
    };
  }, [
    apiHost,
    sessionId,
    activeThemeMode,
    // Removed callback dependencies - now using refs
  ]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Simple Status Indicator */}
      <div
        style={{
          position: 'absolute',
          top: 5,
          right: 15,
          zIndex: 10,
          color:
            status === 'Running'
              ? 'yellow'
              : status === 'Success'
                ? 'lightgreen'
                : status === 'Error'
                  ? 'red'
                  : '#aaa',
          fontWeight: 'bold',
          fontSize: '12px',
          pointerEvents: 'none',
        }}
      >
        ● {status}
      </div>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

export default WebTerminal;
