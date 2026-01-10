import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/ui/sidebar';

export function DashboardLayout() {
  return (
    <div className="bg-surface-primary text-content-primary flex h-screen w-screen overflow-hidden min-w-[800px] overflow-x-auto">
      <Sidebar />
      <main className="bg-surface-primary flex-1 overflow-y-auto">
        <div className="min-h-full w-full p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
