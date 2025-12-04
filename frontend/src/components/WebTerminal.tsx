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

  // Handle text selection for copy functionality
  const handleCopy = () => {
    const selection = termInstance.current?.getSelection();
    if (selection) {
      navigator.clipboard.writeText(selection).then(() => {
        console.log('[WebTerminal] Text copied to clipboard');
      });
    }
  };

  // Track if we've already connected to this session (React Strict Mode protection)
  const connectedSessionRef = useRef<string | null>(null);

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

    // React Strict Mode protection: skip if we've already connected to this session
    // and the WebSocket connection is still alive
    if (connectedSessionRef.current === sessionId) {
      console.log(
        `[WebTerminal] Already connected to session ${sessionId}, skipping duplicate mount`,
      );
      return;
    }

    // Mark this session as connected
    connectedSessionRef.current = sessionId;

    console.log(`[WebTerminal] Initializing terminal for session ${sessionId}`);

    // 1. Setup Xterm.js
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Consolas, "Courier New", monospace',
      theme: activeThemeMode === 'light' ? light : oneDark,
      allowProposedApi: true,
      // Enable text selection and copy support
      scrollback: 1000,
      screenKeys: false,
      // Allow selection to be copied to clipboard
      rightClickSelectsWord: true,
      // Enable mouse events for better selection support
      mouseWheelScroll: true,
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
    // Note: shellIntegration subscribes to terminal events internally,
    // we don't need to explicitly use it, but we keep the reference
    // to ensure it's not garbage collected while the terminal is active
    new ShellIntegration(term, {
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

    // Store WebSocket instance for cleanup
    let ws: WebSocket | null = null;
    let resizeHandler: (() => void) | null = null;

    // 3. Connect to Backend
    const connect = () => {
      let wsUrl: string;

      // Use provided session ID
      if (apiHost) {
        wsUrl = apiHost.replace(/^http/, 'ws') + `/api/ws/pty_sessions/${sessionId}`;
      } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/api/ws/pty_sessions/${sessionId}`;
      }

      console.log(`[WebTerminal] Connecting to WebSocket: ${wsUrl}`);
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`[WebTerminal] WebSocket connected for session ${sessionId}`);
        term.focus();
        setStatus('Running'); // Assume running when connected

        // Send initial resize to match terminal dimensions
        ws?.send(
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
        console.error(`[WebTerminal] WebSocket error for session ${sessionId}:`, error);
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

      // 4. Input Handling (Native Mode)
      term.onData((data) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'input', data }));
          onInputRef.current?.(data);
        }
      });

      // Resize Handling
      resizeHandler = () => {
        fitAddon.fit();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: 'resize',
              cols: term.cols,
              rows: term.rows,
            }),
          );
        }
      };
      window.addEventListener('resize', resizeHandler);
    };

    // Start connection
    connect();

    // Cleanup function for when component unmounts or session changes
    return () => {
      if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
      }
      if (ws) {
        ws.close();
      }
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
      {/* Status Indicator and Toolbar */}
      <div
        style={{
          position: 'absolute',
          top: 5,
          right: 15,
          zIndex: 10,
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
        }}
      >
        {/* Copy Button */}
        <button
          onClick={handleCopy}
          title="Copy selected text"
          style={{
            padding: '4px 8px',
            fontSize: '12px',
            backgroundColor: '#f0f0f0',
            border: '1px solid #ccc',
            borderRadius: '3px',
            cursor: 'pointer',
            transition: 'background-color 0.2s',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#e0e0e0';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#f0f0f0';
          }}
        >
          📋 Copy
        </button>

        {/* Status Indicator */}
        <div
          style={{
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
      </div>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

export default WebTerminal;
