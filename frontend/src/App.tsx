import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardLayout } from './layouts/dashboard-layout';
import { EnvironmentListPage } from './pages/environment-list-page';
import { EnvironmentWizard } from './pages/environment-wizard';
import { SettingsPage } from './pages/settings-page';

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
          {/* Placeholders for other routes */}
          <Route
            path="dashboard"
            element={<div className="text-content-tertiary">Dashboard Placeholder</div>}
          />
          <Route
            path="devices"
            element={<div className="text-content-tertiary">Devices Placeholder</div>}
          />
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
