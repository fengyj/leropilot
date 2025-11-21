import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/ui/sidebar';

export function DashboardLayout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-primary text-content-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface-primary">
        <div className="min-h-full w-full p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
