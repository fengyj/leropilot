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

// Get Python executable path
function getPythonPath() {
  if (app.isPackaged) {
    // Production: Use packaged Python executable
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';

    // Standard path (installer/unpacked)
    const standardPath = path.join(process.resourcesPath, 'python', `leropilot-backend${ext}`);

    // Portable path (often next to the executable in temp dir)
    const portablePath = path.join(path.dirname(app.getPath('exe')), 'resources', 'python', `leropilot-backend${ext}`);

    // Fallback for some portable configurations where resources might be at root
    const rootPath = path.join(path.dirname(app.getPath('exe')), 'python', `leropilot-backend${ext}`);

    console.log('Searching for Python backend...');
    console.log(`Standard path: ${standardPath}`);
    console.log(`Portable path: ${portablePath}`);
    console.log(`Root path: ${rootPath}`);

    const fs = require('fs');
    if (fs.existsSync(standardPath)) return standardPath;
    if (fs.existsSync(portablePath)) return portablePath;
    if (fs.existsSync(rootPath)) return rootPath;

    // Default to standard path if nothing found (will fail later with clear error)
    return standardPath;
  } else {
    // Development: Use system Python
    // Assume running electron in project root
    return 'python'; // Or use specific venv path, but manual backend start is usually easier in dev
  }
}

// Get config file path
function getConfigPath() {
  const os = require('os');
  const homeDir = os.homedir();
  const configDir = path.join(homeDir, '.leropilot');
  return path.join(configDir, 'config.json');
}

// Read config file
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

  // Return null, let backend use its own defaults
  return null;
}

// Write config file
function writeConfig(config) {
  const fs = require('fs');
  const configPath = getConfigPath();
  const configDir = path.dirname(configPath);

  try {
    // Ensure config directory exists
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

// Parse command line arguments
function parseCommandLineArgs() {
  const args = process.argv.slice(app.isPackaged ? 1 : 2);
  const result = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    // Support --port=9000 or --port 9000
    if (arg === '--port' && i + 1 < args.length) {
      result.port = parseInt(args[i + 1], 10);
      i++;
    } else if (arg.startsWith('--port=')) {
      result.port = parseInt(arg.split('=')[1], 10);
    }
  }

  return result;
}

// Start Python backend
async function startPythonBackend() {
  // In development, we usually start backend manually for debugging
  if (!app.isPackaged) {
    console.log('Development mode: Skipping automatic Python backend start.');
    console.log('Please ensure backend is running manually.');
    // Try to detect port in dev, return null if failed
    return null;
  }

  // Parse command line arguments
  const cmdArgs = parseCommandLineArgs();

  // Read config
  let config = readConfig();

  // If --port argument is provided, update config and save
  if (cmdArgs.port) {
    console.log(`Port override detected: ${cmdArgs.port}`);

    // If no config file, create a basic one
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
  // Build arguments for backend
  const args = [];

  // Only add -u flag in development mode (when using Python interpreter)
  // PyInstaller executables don't accept this flag
  if (!app.isPackaged) {
    args.push('-u'); // Force unbuffered output for development
  }

  if (cmdArgs.port) {
    args.push('--port', cmdArgs.port.toString());
  }
  args.push('--no-browser');

  console.log(`Starting Python backend: ${pythonPath} ${args.join(' ')}`);

  let detectedPort = null;

  pythonProcess = spawn(pythonPath, args, {
    cwd: process.resourcesPath,
    stdio: ['ignore', 'pipe', 'pipe'] // Capture stdout and stderr
  });

  const handleOutput = (data, source) => {
    const output = data.toString();
    console.log(`[Backend ${source}]`, output);

    // Try to extract port from uvicorn output
    // Uvicorn output format: "Uvicorn running on http://127.0.0.1:8000"
    const portMatch = output.match(/http:\/\/[\d.]+:(\d+)/);
    if (portMatch && !detectedPort) {
      detectedPort = parseInt(portMatch[1], 10);
      console.log(`Detected backend port: ${detectedPort}`);
    }
  };

  // Listen to stdout and stderr to detect actual port
  // Note: Uvicorn logs usually go to stderr
  pythonProcess.stdout.on('data', (data) => handleOutput(data, 'stdout'));
  pythonProcess.stderr.on('data', (data) => handleOutput(data, 'stderr'));

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python backend:', err);

    // Check if the error is because the file doesn't exist
    if (err.code === 'ENOENT') {
      console.error('Python backend executable not found at:', pythonPath);
      console.error('This usually means the backend was not packaged correctly.');
    }
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python backend exited with code ${code} and signal ${signal}`);
  });

  // Wait for port detection or timeout
  const maxWaitTime = 15000; // Increased to 15 seconds
  const startTime = Date.now();
  while (!detectedPort && Date.now() - startTime < maxWaitTime) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  if (!detectedPort) {
    console.error('Could not detect backend port. Backend may have failed to start or output is buffered.');
    // If detection fails, try fallback to default or config port
    const fallbackPort = cmdArgs.port || (config && config.server && config.server.port) || 8000;
    console.log(`Falling back to port ${fallbackPort}`);
    detectedPort = fallbackPort;
  }

  // Wait for backend to start
  console.log(`Waiting for backend to be ready on port ${detectedPort}...`);
  console.log(`Health check URL: http://127.0.0.1:${detectedPort}/api/hello`);

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

    // Check if pythonProcess actually started
    if (!pythonProcess || pythonProcess.killed) {
      throw new Error(
        `Backend process failed to start.\n` +
        `Executable path: ${pythonPath}\n` +
        `Please check if the backend was packaged correctly.`
      );
    }

    throw new Error(
      `Failed to connect to backend on port ${detectedPort}.\n` +
      `The backend process is running but not responding.\n` +
      `Check logs for details.`
    );
  }
}

// Create application menu
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
          label: 'LeRobot Documentation',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/huggingface/lerobot');
          }
        },
        {
          label: 'LeRoPilot Documentation',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/fengyj/leropilot');
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

// Create main window
function createWindow(backendPort) {
  // Validate backendPort in production mode
  if (app.isPackaged && !backendPort) {
    const { dialog } = require('electron');
    dialog.showErrorBox('Configuration Error',
      'Backend port is not available.\n\n' +
      'The application backend failed to start properly.\n' +
      'Please check the logs or try running with --port <port>.'
    );
    app.quit();
    return;
  }

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
    : `http://127.0.0.1:${backendPort}`;

  console.log(`Loading URL: ${startUrl}`);
  mainWindow.loadURL(startUrl);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Open DevTools only in development mode
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`[Renderer Console] ${message}`);
  });

  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Page finished loading');
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error('Page failed to load:', errorCode, errorDescription, validatedURL);

    // Show error dialog for critical failures
    // -3 is ERR_ABORTED, which is normal for navigation cancellation
    if (errorCode !== -3 && errorCode !== 0) {
      const { dialog } = require('electron');
      dialog.showErrorBox('Failed to Load',
        `Failed to load the application.\n\n` +
        `URL: ${validatedURL}\n` +
        `Error: ${errorDescription} (${errorCode})\n\n` +
        `Please ensure the backend is running on port ${backendPort || 'unknown'}.`
      );
    }
  });
}

// App startup
app.whenReady().then(async () => {
  createMenu();

  let backendPort;
  try {
    backendPort = await startPythonBackend();
    createWindow(backendPort);
  } catch (err) {
    console.error('Fatal error during startup:', err);
    const { dialog } = require('electron');
    const portMsg = backendPort
      ? `Please check if port ${backendPort} is available or try running with --port <port>.`
      : 'Please try running with --port <port> to specify a custom port.';
    dialog.showErrorBox('Startup Error',
      'Failed to start the application backend.\n\n' +
      'Error details: ' + err.message + '\n\n' +
      portMsg
    );
    app.quit();
    return;
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(backendPort);
    }
  });
});

// Cleanup on exit
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
