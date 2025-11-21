import {
  LayoutDashboard,
  Settings,
  Bot,
  Video,
  MonitorPlay,
  Database,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '../../utils/cn';
import { useTranslation } from 'react-i18next';
import logo from '../../assets/logo.png';

export function Sidebar() {
  const location = useLocation();
  const { t } = useTranslation();

  const menuItems = [
    { icon: LayoutDashboard, label: t('nav.dashboard'), href: '/dashboard' },
    { icon: MonitorPlay, label: t('nav.environments'), href: '/environments' },
    { icon: Bot, label: t('nav.devices'), href: '/devices' },
    { icon: Video, label: t('nav.recording'), href: '/recording' },
    { icon: Database, label: t('nav.datasets'), href: '/datasets' },
    { icon: Settings, label: t('nav.settings'), href: '/settings' },
  ];

  return (
    <div className="border-border-default bg-surface-secondary flex w-64 flex-shrink-0 flex-col border-r">
      <div className="border-border-default flex h-16 items-center border-b px-6">
        <div className="flex items-center gap-2">
          <img src={logo} alt="LeRoPilot Logo" className="h-8 w-8 rounded-lg" />
          <span className="text-content-primary text-lg font-bold">LeRoPilot</span>
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
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-info-surface text-info-icon'
                  : 'text-content-secondary hover:bg-surface-tertiary hover:text-content-primary',
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-border-default border-t p-4">
        <div className="bg-surface-tertiary mt-4 rounded-lg p-3">
          <p className="text-content-tertiary mb-1 text-xs font-medium">
            {t('nav.activeEnvironment')}
          </p>
          <div className="flex items-center gap-2">
            <div className="bg-success-icon h-2 w-2 rounded-full" />
            <p className="text-content-primary text-sm font-medium">LeRobot v2.0</p>
          </div>
        </div>
      </div>
    </div>
  );
}
