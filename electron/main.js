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
    return path.join(process.resourcesPath, 'python', `leropilot${ext}`);
  } else {
    // 开发环境：使用系统 Python
    // 假设在项目根目录下运行 electron
    return 'python'; // 或者使用具体的 venv 路径，但在开发环境通常手动启动后端更方便
  }
}

// 启动 Python 后端
async function startPythonBackend() {
  // 在开发环境下，我们通常手动启动后端以便于调试
  // 如果需要 Electron 自动启动后端，可以取消下面的注释
  if (!app.isPackaged) {
    console.log('Development mode: Skipping automatic Python backend start. Please ensure backend is running on port 8000.');
    return;
  }

  const pythonPath = getPythonPath();
  const args = ['--port', '8000', '--no-browser'];

  console.log(`Starting Python backend: ${pythonPath} ${args.join(' ')}`);

  pythonProcess = spawn(pythonPath, args, {
    cwd: process.resourcesPath,
    stdio: 'inherit' // 将输出重定向到父进程，方便调试
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python backend:', err);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python backend exited with code ${code} and signal ${signal}`);
  });

  // 等待后端启动
  try {
    await waitOn({
      resources: ['http://127.0.0.1:8000/api/hello'],
      timeout: 30000,
      interval: 1000,
      tcpTimeout: 1000,
      window: 1000,
    });
    console.log('Python backend is ready');
  } catch (err) {
    console.error('Timeout waiting for Python backend:', err);
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
            await shell.openExternal('https://github.com/yourusername/leropilot/issues');
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
function createWindow() {
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

  const startUrl = !app.isPackaged
    ? 'http://localhost:5173'
    : `file://${path.join(__dirname, '../dist/frontend/index.html')}`;

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
  await startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
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
