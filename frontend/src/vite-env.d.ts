/// <reference types="vite/client" />

interface ElectronAPI {
  platform: string;
  isElectron: boolean;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
