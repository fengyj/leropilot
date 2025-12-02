import { Terminal, IDisposable } from '@xterm/xterm';

// --- Shell Event Types ---

export const SHELL_EVENT_TYPES = {
  PROMPT_START: 'prompt_start',
  INPUT_START: 'input_start',
  COMMAND_START: 'command_start',
  COMMAND_OUTPUT: 'command_output',
  COMMAND_FINISHED: 'command_finished',
  CWD_UPDATE: 'cwd_update',
} as const;

export type ShellEventType = (typeof SHELL_EVENT_TYPES)[keyof typeof SHELL_EVENT_TYPES];

export interface BaseShellEvent {
  timestamp: number;
}

export interface PromptStartEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.PROMPT_START;
}

export interface InputStartEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.INPUT_START;
}

export interface CommandStartEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.COMMAND_START;
  commandLine: string;
}

export interface CommandOutputEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.COMMAND_OUTPUT;
}

export interface CommandFinishedEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.COMMAND_FINISHED;
  exitCode: number;
  duration: number;
}

export interface CwdUpdateEvent extends BaseShellEvent {
  type: typeof SHELL_EVENT_TYPES.CWD_UPDATE;
  path: string;
}

export type ShellEvent =
  | PromptStartEvent
  | InputStartEvent
  | CommandStartEvent
  | CommandOutputEvent
  | CommandFinishedEvent
  | CwdUpdateEvent;

export interface ShellHandlers {
  onShellEvent: (event: ShellEvent) => void;
}

export class ShellIntegration {
  private term: Terminal;
  private handlers: ShellHandlers;
  private oscDisposable: IDisposable | undefined;

  private currentCommandLine: string = '';
  private commandStartTime: number = 0;
  private _isCommandRunning: boolean = false;

  constructor(term: Terminal, handlers: ShellHandlers) {
    this.term = term;
    this.handlers = handlers;
    this._registerHandler();
  }

  private _emit(event: ShellEvent) {
    this.handlers.onShellEvent(event);
  }

  private _registerHandler() {
    this.oscDisposable = this.term.parser.registerOscHandler(633, (data) => {
      try {
        const parts = data.split(';');
        const type = parts[0];

        switch (type) {
          case 'A':
            this._emit({ type: SHELL_EVENT_TYPES.PROMPT_START, timestamp: Date.now() });
            break;
          case 'B':
            this._emit({ type: SHELL_EVENT_TYPES.INPUT_START, timestamp: Date.now() });
            break;
          case 'E':
            this.currentCommandLine = parts.slice(1).join(';');
            break;
          case 'C':
            this._isCommandRunning = true;
            this.commandStartTime = Date.now();
            this._emit({
              type: SHELL_EVENT_TYPES.COMMAND_START,
              commandLine: this.currentCommandLine,
              timestamp: this.commandStartTime,
            });
            this._emit({
              type: SHELL_EVENT_TYPES.COMMAND_OUTPUT,
              timestamp: Date.now(),
            });
            break;
          case 'D':
            if (!this._isCommandRunning) return true;
            {
              let exitCode = -1;
              if (parts[1]) {
                const parsed = parseInt(parts[1], 10);
                if (!isNaN(parsed)) exitCode = parsed;
              }
              const duration = Date.now() - this.commandStartTime;
              this._emit({
                type: SHELL_EVENT_TYPES.COMMAND_FINISHED,
                exitCode,
                duration,
                timestamp: Date.now(),
              });
              this._isCommandRunning = false;
              this.currentCommandLine = '';
            }
            break;
          case 'P':
            {
              const prop = parts.slice(1).join(';');
              if (prop.startsWith('Cwd=')) {
                this._emit({
                  type: SHELL_EVENT_TYPES.CWD_UPDATE,
                  path: prop.substring(4),
                  timestamp: Date.now(),
                });
              }
            }
            break;
        }
      } catch (e) {
        console.error('OSC 633 Parse Error', e);
      }
      return true;
    });
  }

  public dispose() {
    this.oscDisposable?.dispose();
  }
}
