const { app, BrowserWindow, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const waitOn = require('wait-on');
const fs = require('fs');

let pythonProcess = null;
let mainWindow = null;
let splashWindow = null;

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

  const pythonPath = getPythonPath();
  // Build arguments for backend
  const args = [];

  // Only add -u flag in development mode (when using Python interpreter)
  // PyInstaller executables don't accept this flag
  if (!app.isPackaged) {
    args.push('-u'); // Force unbuffered output for development
  }

  // Pass port to backend only if provided via command line
  // Otherwise, let Python backend use its saved config (or default)
  if (cmdArgs.port) {
    console.log(`Port override detected from command line: ${cmdArgs.port}`);
    args.push('--port', cmdArgs.port.toString());
  }
  args.push('--no-browser');

  console.log(`Starting Python backend: ${pythonPath} ${args.join(' ')}`);

  let detectedPort = null;

  // Set environment to disable Python output buffering
  const env = { ...process.env, PYTHONUNBUFFERED: '1' };

  pythonProcess = spawn(pythonPath, args, {
    cwd: process.resourcesPath,
    stdio: ['ignore', 'pipe', 'pipe'], // Capture stdout and stderr
    env: env
  });

  let backendOutput = '';  // Collect output for error reporting
  let backendExited = false;
  let backendExitCode = null;
  let backendError = null;

  const handleOutput = (data, source) => {
    const output = data.toString();
    console.log(`[Backend ${source}]`, output);
    backendOutput += output;  // Collect for error reporting

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
    backendError = err;

    // Check if the error is because the file doesn't exist
    if (err.code === 'ENOENT') {
      console.error('Python backend executable not found at:', pythonPath);
      console.error('This usually means the backend was not packaged correctly.');
    }
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python backend exited with code ${code} and signal ${signal}`);
    backendExited = true;
    backendExitCode = code;
  });

  // Wait for port detection or timeout (reduced to 5 seconds)
  updateSplashStatus('Detecting backend port...');
  const maxWaitTime = 5000;
  const startTime = Date.now();
  while (!detectedPort && !backendExited && Date.now() - startTime < maxWaitTime) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  // Check if backend crashed during startup
  if (backendExited) {
    const errorMsg = backendOutput.length > 500
      ? '...' + backendOutput.slice(-500)
      : backendOutput;
    throw new Error(
      `Backend process crashed during startup (exit code: ${backendExitCode}).\n\n` +
      `Output:\n${errorMsg || 'No output captured'}`
    );
  }

  if (backendError) {
    throw new Error(`Failed to start backend: ${backendError.message}`);
  }

  if (!detectedPort) {
    console.error('Could not detect backend port. Backend may have failed to start or output is buffered.');
    // If detection fails, use command-line port or default
    // The backend will save the port to config if it was provided via --port
    const fallbackPort = cmdArgs.port || 8000;
    console.log(`Falling back to port ${fallbackPort}`);
    detectedPort = fallbackPort;
  }

  // Wait for backend to start
  updateSplashStatus('Waiting for backend to be ready...');
  console.log(`Waiting for backend to be ready on port ${detectedPort}...`);
  console.log(`Health check URL: http://127.0.0.1:${detectedPort}/api/hello`);

  try {
    await waitOn({
      resources: [`http://127.0.0.1:${detectedPort}/api/hello`],
      timeout: 15000,  // Reduced from 30s to 15s
      interval: 500,   // Check more frequently
      tcpTimeout: 1000,
      window: 500,
    });
    updateSplashStatus('Loading application...');
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

    // Check if port is actually in use
    throw new Error(
      `Failed to connect to backend on port ${detectedPort}.\n\n` +
      `Possible causes:\n` +
      `1. The port is already in use by another process\n` +
      `2. The backend process crashed (check logs)\n` +
      `3. Firewall or antivirus is blocking the connection\n\n` +
      `Solutions:\n` +
      `• Try again in a few seconds (port may still be releasing)\n` +
      `• Restart your computer to clear the port\n` +
      `• Use a different port: leropilot --port 9000\n` +
      `• Check task manager for processes using port ${detectedPort}`
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

// Create splash window for startup
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 320,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Read icon and convert to base64
  const iconPath = path.join(__dirname, 'icon.png');
  let iconBase64 = '';
  try {
    const iconData = fs.readFileSync(iconPath);
    iconBase64 = iconData.toString('base64');
  } catch (e) {
    console.error('Failed to load icon:', e);
  }

  // Create splash HTML content with logo image
  // Color scheme based on logo: orange gradient (#FF8A65 to #F4511E)
  const splashHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
          background: linear-gradient(135deg, #FFF5F2 0%, #FFE8E0 50%, #FFDDD3 100%);
          height: 100vh;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          color: #333;
          border-radius: 12px;
          user-select: none;
          -webkit-app-region: drag;
          border: 1px solid rgba(244, 81, 30, 0.1);
        }
        .logo {
          width: 88px;
          height: 88px;
          margin-bottom: 16px;
          border-radius: 20px;
          box-shadow: 0 8px 24px rgba(244, 81, 30, 0.25);
        }
        h1 {
          font-size: 28px;
          font-weight: 600;
          margin-bottom: 4px;
          background: linear-gradient(135deg, #FF8A65 0%, #F4511E 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        .status {
          font-size: 14px;
          margin-top: 16px;
          color: #888;
        }
        .spinner {
          width: 36px;
          height: 36px;
          border: 3px solid rgba(244, 81, 30, 0.15);
          border-radius: 50%;
          border-top-color: #F4511E;
          animation: spin 1s ease-in-out infinite;
          margin-top: 16px;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      </style>
    </head>
    <body>
      ${iconBase64 ? `<img class="logo" src="data:image/png;base64,${iconBase64}" alt="LeRoPilot" />` : ''}
      <h1>LeRoPilot</h1>
      <div class="spinner"></div>
      <div class="status" id="status">Starting backend...</div>
      <script>
        const { ipcRenderer } = require('electron');
        ipcRenderer.on('splash-status', (event, message) => {
          document.getElementById('status').textContent = message;
        });
      </script>
    </body>
    </html>
  `;

  splashWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(splashHtml));
  splashWindow.center();
  splashWindow.show();
}

function updateSplashStatus(message) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.send('splash-status', message);
  }
}

function closeSplashWindow() {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
    splashWindow = null;
  }
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
    closeSplashWindow();
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

  // Show splash screen in production
  if (app.isPackaged) {
    createSplashWindow();
  }

  let backendPort;
  try {
    backendPort = await startPythonBackend();
    createWindow(backendPort);
  } catch (err) {
    console.error('Fatal error during startup:', err);
    closeSplashWindow();
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

app.on('before-quit', () => {
  killPythonBackend();
});

app.on('quit', () => {
  killPythonBackend();
});

function killPythonBackend() {
  if (pythonProcess && !pythonProcess.killed) {
    console.log('Killing Python backend process...');

    if (process.platform === 'win32') {
      // Windows: Use taskkill to forcefully kill the process tree
      try {
        require('child_process').execSync(`taskkill /pid ${pythonProcess.pid} /T /F`, {
          stdio: 'ignore'
        });
      } catch (e) {
        // Process might already be dead
        console.log('taskkill failed (process may already be terminated):', e.message);
      }
    } else {
      // Unix: Send SIGTERM first, then SIGKILL
      try {
        pythonProcess.kill('SIGTERM');
        // Give it a moment to terminate gracefully
        setTimeout(() => {
          if (pythonProcess && !pythonProcess.killed) {
            pythonProcess.kill('SIGKILL');
          }
        }, 1000);
      } catch (e) {
        console.log('Failed to kill process:', e.message);
      }
    }

    pythonProcess = null;
  }
}
