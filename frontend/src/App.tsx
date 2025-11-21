import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { DashboardLayout } from "./layouts/dashboard-layout";
import { EnvironmentListPage } from "./pages/environment-list-page";
import { EnvironmentWizard } from "./pages/environment-wizard";
import { SettingsPage } from "./pages/settings-page";

function App() {
  console.log('App component rendering...');
  console.log('Platform:', (window as any).electronAPI?.platform || 'web');
  console.log('Is Electron:', (window as any).electronAPI?.isElectron || false);
  
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/environments" replace />} />
          <Route path="environments" element={<EnvironmentListPage />} />
          <Route path="environments/new" element={<EnvironmentWizard />} />
          {/* Placeholders for other routes */}
          <Route path="dashboard" element={<div className="text-zinc-400">Dashboard Placeholder</div>} />
          <Route path="devices" element={<div className="text-zinc-400">Devices Placeholder</div>} />
          <Route path="recording" element={<div className="text-zinc-400">Recording Placeholder</div>} />
          <Route path="datasets" element={<div className="text-zinc-400">Datasets Placeholder</div>} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
