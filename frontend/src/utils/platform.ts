export const isElectron = (): boolean => {
  return !!(window as any).electronAPI?.isElectron;
};

export const getPlatform = (): string => {
  return (window as any).electronAPI?.platform || 'web';
};
