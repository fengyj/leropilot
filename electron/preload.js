const { contextBridge } = require('electron');

const api = {
  platform: process.platform,
  isElectron: true
};

try {
  contextBridge.exposeInMainWorld('electronAPI', api);
} catch (error) {
  // Fallback when contextIsolation is false
  window.electronAPI = api;
}
