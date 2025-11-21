import { LayoutDashboard, Settings, Bot, Video, MonitorPlay, Database } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "../../utils/cn";
import { useTranslation } from "react-i18next";
import logo from "../../assets/logo.png";

export function Sidebar() {
  const location = useLocation();
  const { t } = useTranslation();

  const menuItems = [
    { icon: LayoutDashboard, label: t("nav.dashboard"), href: "/dashboard" },
    { icon: MonitorPlay, label: t("nav.environments"), href: "/environments" },
    { icon: Bot, label: t("nav.devices"), href: "/devices" },
    { icon: Video, label: t("nav.recording"), href: "/recording" },
    { icon: Database, label: t("nav.datasets"), href: "/datasets" },
    { icon: Settings, label: t("nav.settings"), href: "/settings" },
  ];

  return (
    <div className="flex w-64 flex-col border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex-shrink-0">
      <div className="flex h-16 items-center px-6 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <img src={logo} alt="LeRoPilot Logo" className="h-8 w-8 rounded-lg" />
          <span className="text-lg font-bold text-zinc-900 dark:text-white">LeRoPilot</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname.startsWith(item.href);
          
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-white"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-200 dark:border-zinc-800 p-4">
        <div className="mt-4 rounded-lg bg-zinc-100 dark:bg-zinc-900 p-3">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">{t("nav.activeEnvironment")}</p>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">LeRobot v2.0</p>
          </div>
        </div>
      </div>
    </div>
  );
}
