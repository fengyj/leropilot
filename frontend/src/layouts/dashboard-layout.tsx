import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/ui/sidebar";

export function DashboardLayout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-zinc-50 dark:bg-zinc-950">
        <div className="min-h-full w-full p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
