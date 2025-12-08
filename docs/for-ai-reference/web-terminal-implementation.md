# Web Terminal 核心组件设计文档 (Production Ready)

## 1. 系统架构概述

本系统采用 **B/S 架构**，通过 WebSocket 实现前端 Xterm.js 与后端 PTY 进程的全双工通信。

- **Frontend:** React + Xterm.js + Shell Integration Addon
- **Backend:** Python (FastAPI)
- **Core Logic:** `PtySession` 类采用 **"生产者-消费者"** 模型：
  - **生产者 A:** 后台线程读取物理 PTY 设备。
  - **生产者 B:** `write_system_message` 方法产生应用层通知。
  - **消费者:** WebSocket Handler 从聚合队列中读取数据发送给前端。

## 2. 项目目录结构

以下为示意结构组织，请以实际项目文件结构组织为准：

```text
project_root/
├── src/
│   ├── main.py                # FastAPI 入口与 WebSocket 控制器
│   ├── pty_session.py         # 核心 PTY 会话管理（含 OS 差异处理）
│   ├── requirements.txt       # Python 依赖
│   └── scripts/               # VS Code Shell Integration 脚本
│       ├── shellIntegration-bash.sh
│       ├── shellIntegration.ps1
│       └── shellIntegration-rc.zsh
└── frontend/
    ├── src/
    │   ├── Terminal.tsx       # 终端组件
    │   └── App.tsx
    └── package.json
```

PS: VS Code Shell Integration 脚本来自: https://github.com/microsoft/vscode/tree/main/src/vs/workbench/contrib/terminal/common/scripts

---

## 3. 后端实现规范 (Python)

### 3.1 依赖管理 (`backend/requirements.txt`)

```text
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=11.0
pydantic>=2.0
# Windows 平台特定依赖
pywinpty>=2.0.10; sys_platform == 'win32'
```

PS: 依赖包请以实际项目文件为准。如果是新的依赖，尽量使用新的稳定版本。

### 3.2 核心会话逻辑 (`backend/pty_session.py`)

**设计重点：**

- 使用 `queue.Queue` 和 `threading.Thread` 隔离物理 I/O，解决 Windows/Linux 读取阻塞行为不一致的问题。
- 提供 `write_system_message` 接口，绕过 PTY 直接向前端发送数据。
- 统一的 `close` 资源清理机制，防止僵尸进程。

```python
import os
import sys
import platform
import struct
import fcntl
import termios
import threading
import queue
import time
import signal
from typing import Optional

# OS Detection
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    from winpty import PtyProcess
else:
    import pty

class PtySession:
    def __init__(self, cols: int, rows: int, cwd: str = None):
        self.cols = cols
        self.rows = rows
        self.fd: Optional[int] = None
        self.proc = None
        self.pid: Optional[int] = None

        # 处理默认路径：如果没传，或者路径不存在，则使用用户 Home 目录
        user_home = os.path.expanduser("~")
        if not cwd or not os.path.exists(cwd):
            self.cwd = user_home
        else:
            self.cwd = cwd

        # --- I/O Aggregation ---
        # 统一输出队列：存放来自 Shell 的 bytes 和系统消息 bytes
        self._output_queue = queue.Queue()
        self._stop_event = threading.Event()

        # 1. Detect & Start Shell
        self.shell_path = self._detect_shell()
        self._start_pty()

        # 2. Start Background Reader Thread
        # 专门负责从物理 PTY 搬运数据到队列，隔离阻塞风险
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        # 3. Inject Shell Integration
        self._inject_integration_script()

    def _detect_shell(self) -> str:
        if IS_WINDOWS:
            # 优先 PowerShell Core (pwsh), 其次 Windows PowerShell
            # 生产环境建议检查文件是否存在
            return os.environ.get("COMSPEC", "powershell.exe")
        else:
            return os.environ.get("SHELL", "/bin/bash")

    def _start_pty(self):
        """跨平台 PTY 启动逻辑"""
        if IS_WINDOWS:
            # Windows: Pywinpty
            try:
                self.proc = PtyProcess.spawn(self.shell_path, dims=(self.rows, self.cols), cwd=self.cwd)
                self.fd = self.proc.fd
                self.pid = self.proc.pid
            except FileNotFoundError:
                # Fallback if shell not found
                self.shell_path = "cmd.exe"
                self.proc = PtyProcess.spawn(self.shell_path, dims=(self.rows, self.cols), cwd=self.cwd)
                self.fd = self.proc.fd
        else:
            # Linux/macOS: Native PTY
            self.pid, self.fd = pty.fork()
            if self.pid == 0:  # Child process
                try:
                    os.chdir(self.cwd)
                except OSError:
                    pass # 如果切换失败，保持在当前目录
                # Set Standard Terminal Environment
                os.environ['TERM'] = 'xterm-256color'
                os.execv(self.shell_path, [self.shell_path])
            else:  # Parent process
                self._resize_linux(self.rows, self.cols)

    def _read_loop(self):
        """后台线程：物理 PTY -> Queue"""
        while not self._stop_event.is_set():
            try:
                data = b""
                if IS_WINDOWS:
                    # winpty read may block or return empty
                    data = self.proc.read(1024).encode('utf-8')
                else:
                    # Linux read is blocking
                    data = os.read(self.fd, 1024)

                if not data:
                    # EOF detected (Shell exited)
                    break

                self._output_queue.put(data)

            except (OSError, EOFError):
                break
            except Exception as e:
                # Log error internal
                break

        # Signal EOF to consumer
        self._output_queue.put(None)

    def _inject_integration_script(self):
        """加载 VS Code Shell Integration 脚本"""
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        cmd = ""
        shell_name = os.path.basename(self.shell_path).lower()

        if IS_WINDOWS and ("powershell" in shell_name or "pwsh" in shell_name):
            path = os.path.join(script_dir, "shellIntegration.ps1")
            if os.path.exists(path):
                cmd = f". '{path}'"

        elif "zsh" in shell_name:
            path = os.path.join(script_dir, "shellIntegration-rc.zsh")
            if os.path.exists(path):
                cmd = f"source '{path}'"

        elif "bash" in shell_name:
            path = os.path.join(script_dir, "shellIntegration-bash.sh")
            if os.path.exists(path):
                cmd = f"source '{path}'"

        if cmd:
            # 自动执行注入命令，并清屏
            self.write_command(cmd)
            self.write_command("clear" if not IS_WINDOWS else "Clear-Host")

    # --- Public API ---

    def read(self, timeout: float = 0.1) -> bytes:
        """消费者方法：从聚合队列读取数据"""
        try:
            data = self._output_queue.get(timeout=timeout)
            if data is None:
                return b"" # EOF marker
            return data
        except queue.Empty:
            return b""

    def write(self, data: str):
        """写入原始数据到 Shell (模拟键盘)"""
        if self.proc is None and self.fd is None:
            return

        try:
            if IS_WINDOWS:
                self.proc.write(data)
            else:
                os.write(self.fd, data.encode('utf-8'))
        except OSError:
            pass

    def write_command(self, command: str):
        """工具方法：执行命令 (自动追加回车)"""
        # \r 兼容所有平台
        self.write(command + "\r")

    def write_system_message(self, message: str, color: str = "green"):
        """工具方法：直接向输出流注入系统消息 (不经过 Shell)"""
        colors = {
            "red": "\x1b[31m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "blue": "\x1b[34m",
            "reset": "\x1b[0m"
        }
        c = colors.get(color, colors["reset"])
        # Format: CRLF + Color + Msg + Reset + CRLF
        formatted = f"\r\n{c}[System]: {message}{colors['reset']}\r\n"
        self._output_queue.put(formatted.encode('utf-8'))

    def resize(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        if IS_WINDOWS and self.proc:
            self.proc.setwinsize(rows, cols)
        elif not IS_WINDOWS and self.fd:
            self._resize_linux(rows, cols)

    def _resize_linux(self, rows, cols):
        try:
            s = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)
        except OSError:
            pass

    def close(self):
        """健壮的资源清理"""
        self._stop_event.set()

        if IS_WINDOWS:
            if self.proc:
                self.proc.terminate()
                self.proc = None
        else:
            if self.fd:
                try:
                    os.close(self.fd)
                except OSError: pass
                self.fd = None
            if self.pid:
                try:
                    # 发送 SIGKILL 确保退出
                    os.kill(self.pid, signal.SIGKILL)
                    # 必须 waitpid 防止僵尸进程
                    os.waitpid(self.pid, 0)
                except OSError: pass
                self.pid = None
```

### 3.3 接口控制 (`backend/main.py`)

**设计重点：**

- **非阻塞读取：** 使用 `asyncio.to_thread` (Python 3.9+) 或 `loop.run_in_executor` 调用阻塞的 `queue.get`。
- **生命周期管理：** WebSocket 断开 (`finally` 块) 必须触发 `pty.close()`。
- **安全 Origin:** 显式定义允许的 Origin 列表。

```python
import asyncio
import uuid
import logging
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pty_session import PtySession

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# SECURITY: Configure specific origins for production
ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "file://",  # If using Electron loading local files
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,  # Don't use "*" in production if possible
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Session Store
# TODO: In production, consider LRU cache or cleanup task for stale sessions
sessions: Dict[str, PtySession] = {}

class SessionRequest(BaseModel):
    cols: int = 80
    rows: int = 24
    cwd: Optional[str] = None

@app.post("/api/pty_sessions")
async def create_session(req: SessionRequest):
    session_id = str(uuid.uuid4())
    try:
        session = PtySession(req.cols, req.rows, req.cwd)
        sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return {"error": str(e)}, 500

@app.websocket("/ws/pty_sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Security: Validate session existence
    if session_id not in sessions:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    pty = sessions[session_id]
    loop = asyncio.get_running_loop()

    # Inject Welcome Message (via Queue)
    pty.write_system_message("Connected to Backend Terminal.", "green")

    # --- Task: PTY -> WebSocket ---
    async def pty_reader():
        try:
            while True:
                # run_in_executor avoids blocking the Async Event Loop
                # pty.read is now thread-safe reading from internal Queue
                data = await loop.run_in_executor(None, pty.read)

                if not data:
                    break # EOF or Session Closed

                await websocket.send_text(data.decode(errors='ignore'))
        except Exception as e:
            logger.error(f"Reader error: {e}")
        finally:
            # If reader dies, close socket
            await websocket.close()

    reader_task = asyncio.create_task(pty_reader())

    # --- Loop: WebSocket -> PTY ---
    try:
        while True:
            msg = await websocket.receive_json()

            msg_type = msg.get("type")

            if msg_type == "input":
                # Raw input pass-through
                pty.write(msg.get("data", ""))

            elif msg_type == "resize":
                pty.resize(msg.get("rows", 24), msg.get("cols", 80))

            elif msg_type == "command":
                # API driven command execution
                cmd = msg.get("command")
                if cmd:
                    pty.write_command(cmd)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WS Loop error: {e}")
    finally:
        # Cleanup
        reader_task.cancel()
        pty.close()
        if session_id in sessions:
            del sessions[session_id]
        logger.info(f"Session closed: {session_id}")

if __name__ == "__main__":
    import uvicorn
    # Use 127.0.0.1 for local security
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

---

## 4. 前端实现规范 (React)

### 4.1 依赖安装

```bash
npm install xterm xterm-addon-fit @xterm/addon-shell-integration
```

### 4.2 终端组件 (`frontend/src/Terminal.tsx`)

**设计重点：**

- **原生行为：** 不拦截粘贴，允许 PTY 处理多行命令。
- **状态感知：** 利用 VS Code 脚本发出的 OSC 133 信号更新 UI 状态。
- **API 主机配置：** 支持灵活配置后端地址。

```tsx
import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { ShellIntegrationAddon } from "@xterm/addon-shell-integration";
import "xterm/css/xterm.css";

interface TerminalProps {
  apiHost?: string; // e.g. "http://127.0.0.1:8000"
}

const WebTerminal: React.FC<TerminalProps> = ({
  apiHost = "http://127.0.0.1:8000",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termInstance = useRef<Terminal | null>(null);
  const [status, setStatus] = useState<
    "Idle" | "Running" | "Error" | "Success"
  >("Idle");

  useEffect(() => {
    if (!containerRef.current) return;

    // 1. Setup Xterm.js
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Consolas, "Courier New", monospace',
      theme: {
        background: "#1e1e1e",
        foreground: "#ffffff",
      },
      allowProposedApi: true, // Required for Shell Integration
    });

    const fitAddon = new FitAddon();
    const shellIntegration = new ShellIntegrationAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(shellIntegration);
    term.open(containerRef.current);
    fitAddon.fit();
    termInstance.current = term;

    // 2. Handle Shell Events (OSC 133)
    // These are triggered by the hidden sequences injected by backend scripts
    shellIntegration.onDidChangeCommandState((e) => {
      if (e.state === "COMMAND_START") {
        setStatus("Running");
      } else if (e.state === "COMMAND_FINISHED") {
        console.log(`Command finished. Exit Code: ${e.exitCode}`);
        setStatus(e.exitCode === 0 ? "Success" : "Error");

        // Optional: Visual Feedback in terminal
        if (e.exitCode !== 0) {
          term.write("\x1b[31m✘\x1b[0m "); // Print red X
        }
      }
    });

    // 3. Connect to Backend
    const connect = async () => {
      try {
        // Create Session
        const res = await fetch(`${apiHost}/api/pty_sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cols: term.cols, rows: term.rows }),
        });

        if (!res.ok) throw new Error("Failed to create session");
        const { session_id } = await res.json();

        // Connect WebSocket
        const wsUrl =
          apiHost.replace(/^http/, "ws") + `/ws/pty_sessions/${session_id}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          term.focus();
        };

        ws.onmessage = (ev) => {
          // Render data from backend (includes shell output + system messages)
          term.write(ev.data);
        };

        ws.onclose = () => {
          term.write("\r\n\x1b[33m[Connection Closed]\x1b[0m\r\n");
        };

        // 4. Input Handling (Native Mode)
        term.onData((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "input", data }));
          }
        });

        // Resize Handling
        const handleResize = () => {
          fitAddon.fit();
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                type: "resize",
                cols: term.cols,
                rows: term.rows,
              })
            );
          }
        };
        window.addEventListener("resize", handleResize);

        return () => {
          window.removeEventListener("resize", handleResize);
          ws.close();
        };
      } catch (err) {
        term.write(`\r\n\x1b[31mError: ${err}\x1b[0m\r\n`);
      }
    };

    const cleanupPromise = connect();

    return () => {
      cleanupPromise.then((cleanup) => cleanup && cleanup());
      term.dispose();
    };
  }, [apiHost]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Simple Status Indicator */}
      <div
        style={{
          position: "absolute",
          top: 5,
          right: 15,
          zIndex: 10,
          color:
            status === "Running"
              ? "yellow"
              : status === "Success"
              ? "lightgreen"
              : status === "Error"
              ? "red"
              : "#aaa",
          fontWeight: "bold",
          fontSize: "12px",
          pointerEvents: "none",
        }}
      >
        ● {status}
      </div>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default WebTerminal;
```

### 4.3 主题支持

**浅色主题：**

```
export const nord: ITheme = {
    background: '#2e3440', // 核心：非常舒服的灰蓝色
    foreground: '#d8dee9', // 柔和的灰白文字，不刺眼
    cursor: '#d8dee9',
    selectionBackground: '#434c5e',
    black: '#3b4252',
    red: '#bf616a',
    green: '#a3be8c',
    yellow: '#ebcb8b',
    blue: '#81a1c1',
    magenta: '#b48ead',
    cyan: '#88c0d0',
    white: '#e5e9f0',
    brightBlack: '#4c566a',
    brightRed: '#bf616a',
    brightGreen: '#a3be8c',
    brightYellow: '#ebcb8b',
    brightBlue: '#81a1c1',
    brightMagenta: '#b48ead',
    brightCyan: '#8fbcbb',
    brightWhite: '#eceff4',
};
```

**深色主题：**

```
export const oneDark: ITheme = {
    background: '#282c34',
    foreground: '#abb2bf',
    cursor: '#528bff',
    selectionBackground: '#3e4451',
    black: '#282c34',
    red: '#e06c75',
    green: '#98c379',
    yellow: '#e5c07b',
    blue: '#61afef',
    magenta: '#c678dd',
    cyan: '#56b6c2',
    white: '#dcdfe4',
    brightBlack: '#5c6370',
    brightRed: '#e06c75',
    brightGreen: '#98c379',
    brightYellow: '#e5c07b',
    brightBlue: '#61afef',
    brightMagenta: '#c678dd',
    brightCyan: '#56b6c2',
    brightWhite: '#ffffff',
};
```
