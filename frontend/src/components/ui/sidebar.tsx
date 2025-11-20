import { NavLink } from "react-router-dom";
import { LayoutDashboard, Box, Video, Database, Settings, HardDrive } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../../utils/cn";
import { LanguageSwitcher } from "./language-switcher";

export function Sidebar() {
  const { t } = useTranslation();
  
  const navItems = [
    { icon: LayoutDashboard, label: t("nav.dashboard"), to: "/dashboard" },
    { icon: Box, label: t("nav.environments"), to: "/environments" },
    { icon: HardDrive, label: t("nav.devices"), to: "/devices" },
    { icon: Video, label: t("nav.recording"), to: "/recording" },
    { icon: Database, label: t("nav.datasets"), to: "/datasets" },
    { icon: Settings, label: t("nav.settings"), to: "/settings" },
  ];

  return (
    <div className="flex h-screen w-64 flex-col border-r border-slate-800 bg-slate-950">
      <div className="flex h-16 items-center px-6 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold">L</span>
          </div>
          <span className="text-lg font-bold text-slate-100">LeRoPilot</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-600/10 text-blue-500"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-100"
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800 space-y-2">
        <LanguageSwitcher />
        <div className="rounded-lg bg-slate-900 p-4">
          <p className="text-xs font-medium text-slate-400">{t("sidebar.activeEnvironment")}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-sm text-slate-200">LeRobot v2.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
