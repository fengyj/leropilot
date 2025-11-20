import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { DashboardLayout } from "./layouts/dashboard-layout";
import { EnvironmentListPage } from "./pages/environment-list-page";
import { EnvironmentWizard } from "./pages/environment-wizard";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/environments" replace />} />
          <Route path="environments" element={<EnvironmentListPage />} />
          <Route path="environments/new" element={<EnvironmentWizard />} />
          {/* Placeholders for other routes */}
          <Route path="dashboard" element={<div className="text-slate-400">Dashboard Placeholder</div>} />
          <Route path="devices" element={<div className="text-slate-400">Devices Placeholder</div>} />
          <Route path="recording" element={<div className="text-slate-400">Recording Placeholder</div>} />
          <Route path="datasets" element={<div className="text-slate-400">Datasets Placeholder</div>} />
          <Route path="settings" element={<div className="text-slate-400">Settings Placeholder</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
