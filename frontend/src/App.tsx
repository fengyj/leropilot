import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from './layouts/dashboard-layout';
import { EnvironmentListPage } from './pages/environment-list';
import { EnvironmentWizard } from './pages/environment-wizard';
import { EnvironmentInstallationPage } from './pages/environment-installation';
import { AdvancedInstallationPage } from './pages/advanced-installation-page';
import { SettingsPage } from './pages/settings-page';
import { HardwareDashboard } from './pages/hardware-dashboard';

interface ElectronAPI {
  platform: string;
  isElectron: boolean;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

function App() {
  console.log('App component rendering...');
  console.log('Platform:', window.electronAPI?.platform || 'web');
  console.log('Is Electron:', window.electronAPI?.isElectron || false);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/environments" replace />} />
          <Route path="environments" element={<EnvironmentListPage />} />
          <Route path="environments/new" element={<EnvironmentWizard />} />
          <Route
            path="environments/install"
            element={<EnvironmentInstallationPage />}
          />
          <Route
            path="environments/:envId/install"
            element={<EnvironmentInstallationPage />}
          />
          <Route
            path="environments/advanced-install"
            element={<AdvancedInstallationPage />}
          />
          {/* Placeholders for other routes */}
          <Route
            path="dashboard"
            element={<div className="text-content-tertiary">Dashboard Placeholder</div>}
          />
          <Route path="hardware" element={<HardwareDashboard />} />
          <Route path="hardware/discovery" element={<Navigate to="/hardware" replace />} />
          <Route path="hardware/:id/settings" element={<Navigate to="/hardware" replace />} />
          <Route path="hardware/:id/control" element={<Navigate to="/environments" replace />} />
          <Route path="hardware/:id/calibrate" element={<Navigate to="/environments" replace />} />
          <Route
            path="recording"
            element={<div className="text-content-tertiary">Recording Placeholder</div>}
          />
          <Route
            path="datasets"
            element={<div className="text-content-tertiary">Datasets Placeholder</div>}
          />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
