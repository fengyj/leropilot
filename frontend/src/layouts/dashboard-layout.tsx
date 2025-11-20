import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/ui/sidebar";

export function DashboardLayout() {
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="container mx-auto p-8 max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
