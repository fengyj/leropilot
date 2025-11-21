const { app, BrowserWindow, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const waitOn = require('wait-on');

let pythonProcess = null;
let mainWindow = null;

// Check if running in WSL
const isWSL = require('os').release().toLowerCase().includes('microsoft');

if (isWSL) {
  console.log('WSL detected: Applying compatibility flags');
  app.disableHardwareAcceleration();
  app.commandLine.appendSwitch('no-sandbox');
  app.commandLine.appendSwitch('disable-gpu');
  app.commandLine.appendSwitch('disable-software-rasterizer');
  app.commandLine.appendSwitch('disable-dev-shm-usage'); // Use /tmp instead of /dev/shm
  app.commandLine.appendSwitch('in-process-gpu'); // Run GPU in main process to avoid shared memory issues
}

// 获取 Python 可执行文件路径
function getPythonPath() {
  if (app.isPackaged) {
    // 生产环境：使用打包的 Python 可执行文件
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';
    return path.join(process.resourcesPath, 'python', `leropilot-backend${ext}`);
  } else {
    // 开发环境：使用系统 Python
    // 假设在项目根目录下运行 electron
    return 'python'; // 或者使用具体的 venv 路径，但在开发环境通常手动启动后端更方便
  }
}

// 获取配置文件路径
function getConfigPath() {
  const os = require('os');
  const homeDir = os.homedir();
  const configDir = path.join(homeDir, '.leropilot');
  return path.join(configDir, 'config.json');
}

// 读取配置文件
function readConfig() {
  const fs = require('fs');
  const configPath = getConfigPath();

  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(configData);
    }
  } catch (err) {
    console.error('Failed to read config:', err);
  }

  // 返回 null，让后端使用自己的默认值
  return null;
}

// 写入配置文件
function writeConfig(config) {
  const fs = require('fs');
  const configPath = getConfigPath();
  const configDir = path.dirname(configPath);

  try {
    // 确保配置目录存在
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }

    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
    console.log('Config saved to:', configPath);
    return true;
  } catch (err) {
    console.error('Failed to write config:', err);
    return false;
  }
}

// 解析命令行参数
function parseCommandLineArgs() {
  const args = process.argv.slice(app.isPackaged ? 1 : 2);
  const result = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    // 支持 --port=9000 或 --port 9000
    if (arg === '--port' && i + 1 < args.length) {
      result.port = parseInt(args[i + 1], 10);
      i++;
    } else if (arg.startsWith('--port=')) {
      result.port = parseInt(arg.split('=')[1], 10);
    }
  }

  return result;
}

// 启动 Python 后端
async function startPythonBackend() {
  // 在开发环境下，我们通常手动启动后端以便于调试
  if (!app.isPackaged) {
    console.log('Development mode: Skipping automatic Python backend start.');
    console.log('Please ensure backend is running manually.');
    // 开发环境下尝试检测端口，如果失败返回 null
    return null;
  }

  // 解析命令行参数
  const cmdArgs = parseCommandLineArgs();

  // 读取配置
  let config = readConfig();

  // 如果提供了 --port 参数，更新配置并保存
  if (cmdArgs.port) {
    console.log(`Port override detected: ${cmdArgs.port}`);

    // 如果没有配置文件，创建一个基本的
    if (!config) {
      config = {
        server: { port: cmdArgs.port, host: '127.0.0.1', auto_open_browser: true },
        ui: { theme: 'system', preferred_language: 'en' }
      };
    } else {
      config.server = config.server || {};
      config.server.port = cmdArgs.port;
    }

    writeConfig(config);
    console.log(`Config updated with new port: ${cmdArgs.port}`);
  }

  const pythonPath = getPythonPath();
  // 如果有 --port 参数，传递给后端；否则让后端使用配置文件或自己的默认值
  const args = cmdArgs.port
    ? ['--port', cmdArgs.port.toString(), '--no-browser']
    : ['--no-browser'];

  console.log(`Starting Python backend: ${pythonPath} ${args.join(' ')}`);

  let detectedPort = null;

  pythonProcess = spawn(pythonPath, args, {
    cwd: process.resourcesPath,
    stdio: ['ignore', 'pipe', 'pipe'] // 捕获 stdout 和 stderr
  });

  // 监听 stdout 以检测实际使用的端口
  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log('[Backend]', output);

    // 尝试从 uvicorn 输出中提取端口号
    // Uvicorn 输出格式: "Uvicorn running on http://127.0.0.1:8000"
    const portMatch = output.match(/http:\/\/[\d.]+:(\d+)/);
    if (portMatch && !detectedPort) {
      detectedPort = parseInt(portMatch[1], 10);
      console.log(`Detected backend port: ${detectedPort}`);
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error('[Backend Error]', data.toString());
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python backend:', err);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python backend exited with code ${code} and signal ${signal}`);
  });

  // 等待端口检测或超时
  const maxWaitTime = 10000; // 10 秒
  const startTime = Date.now();
  while (!detectedPort && Date.now() - startTime < maxWaitTime) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  if (!detectedPort) {
    throw new Error('Could not detect backend port. Backend may have failed to start.');
  }

  // 等待后端启动
  try {
    await waitOn({
      resources: [`http://127.0.0.1:${detectedPort}/api/hello`],
      timeout: 30000,
      interval: 1000,
      tcpTimeout: 1000,
      window: 1000,
    });
    console.log(`Python backend is ready on port ${detectedPort}`);
    return detectedPort;
  } catch (err) {
    console.error('Timeout waiting for Python backend:', err);
    throw new Error(`Failed to connect to backend on port ${detectedPort}`);
  }
}

// 创建应用菜单
function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Quit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => app.quit()
        }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/huggingface/lerobot');
          }
        },
        {
          label: 'Report Issue',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/fengyj/leropilot/issues');
          }
        },
        { type: 'separator' },
        {
          label: 'About LeRoPilot',
          click: () => {
            // TODO: Show about dialog
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// 创建主窗口
function createWindow(backendPort) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: 'LeRoPilot',
    show: false,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // In development: use Vite dev server
  // In production: use Python backend server (port detected from backend)
  const startUrl = !app.isPackaged
    ? 'http://localhost:5173'
    : `http://127.0.0.1:${backendPort || 8000}`;

  console.log(`Loading URL: ${startUrl}`);
  mainWindow.loadURL(startUrl);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // 仅在开发模式下打开 DevTools
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`[Renderer Console] ${message}`);
  });

  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Page finished loading');
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Page failed to load:', errorCode, errorDescription);
  });
}

// 应用启动
app.whenReady().then(async () => {
  createMenu();
  const backendPort = await startPythonBackend();
  createWindow(backendPort);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(backendPort);
    }
  });
});

// 退出时清理
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('quit', () => {
  if (pythonProcess) {
    console.log('Killing Python backend process...');
    pythonProcess.kill();
  }
});
