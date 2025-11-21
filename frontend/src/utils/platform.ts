export const isElectron = (): boolean => {
  return !!window.electronAPI?.isElectron;
};

export const getPlatform = (): string => {
  return window.electronAPI?.platform || 'web';
};
