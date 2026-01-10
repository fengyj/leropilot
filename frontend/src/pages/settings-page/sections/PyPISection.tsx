import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Server } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { cn } from '../../../utils/cn';
import type { AppConfig, PyPIMirror } from '../types';

interface PyPISectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
}

export function PyPISection({ config, setConfig }: PyPISectionProps) {
  const { t } = useTranslation();
  const [newMirrorName, setNewMirrorName] = useState('');
  const [newMirrorUrl, setNewMirrorUrl] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [hoveredMirrorName, setHoveredMirrorName] = useState<string | null>(null);

  const handleAddMirror = () => {
    if (!newMirrorName || !newMirrorUrl) return;

    const newMirror: PyPIMirror = {
      name: newMirrorName,
      url: newMirrorUrl,
      enabled: false,
    };

    setConfig({
      ...config,
      pypi: {
        ...config.pypi,
        mirrors: [...config.pypi.mirrors, newMirror],
      },
    });

    setNewMirrorName('');
    setNewMirrorUrl('');
    setIsAdding(false);
  };

  const handleDeleteMirror = (name: string) => {
    if (window.confirm(t('settings.pypi.deleteConfirm', { name }))) {
      setConfig({
        ...config,
        pypi: {
          ...config.pypi,
          mirrors: config.pypi.mirrors.filter((m) => m.name !== name),
        },
      });
    }
  };

  const handleEnableMirror = (name: string | null) => {
    setConfig({
      ...config,
      pypi: {
        ...config.pypi,
        mirrors: config.pypi.mirrors.map((m) => ({
          ...m,
          enabled: m.name === name,
        })),
      },
    });
  };

  const activeMirror = config.pypi.mirrors.find((m) => m.enabled);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <CardTitle>{t('settings.pypi.title')}</CardTitle>
            <p className="text-content-secondary text-sm">
              {t('settings.pypi.description')}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setIsAdding(!isAdding)}>
            <Plus className="mr-2 h-4 w-4" />
            {t('settings.pypi.addMirror')}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add New Mirror Form */}
        {isAdding && (
          <div className="bg-surface-secondary mb-4 space-y-3 rounded-lg border p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="pypi-mirror-name" className="text-content-secondary text-xs font-medium uppercase">
                  {t('settings.pypi.name')}
                </label>
                <input
                  id="pypi-mirror-name"
                  name="pypi-mirror-name"
                  type="text"
                  className="border-border-default bg-surface-primary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={newMirrorName}
                  onChange={(e) => setNewMirrorName(e.target.value)}
                  placeholder="e.g. Aliyun"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="pypi-mirror-url" className="text-content-secondary text-xs font-medium uppercase">
                  {t('settings.pypi.url')}
                </label>
                <input
                  id="pypi-mirror-url"
                  name="pypi-mirror-url"
                  type="text"
                  className="border-border-default bg-surface-primary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={newMirrorUrl}
                  onChange={(e) => setNewMirrorUrl(e.target.value)}
                  placeholder="https://mirrors.aliyun.com/pypi/simple/"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsAdding(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                size="sm"
                onClick={handleAddMirror}
                disabled={!newMirrorName || !newMirrorUrl}
              >
                {t('common.confirm')}
              </Button>
            </div>
          </div>
        )}

        {/* Official PyPI Option */}
        <div
          role="button"
          tabIndex={0}
          className={cn(
            'flex cursor-pointer items-center justify-between rounded-lg border p-3 transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none',
            !activeMirror
              ? 'border-blue-500/30 bg-blue-500/5'
              : 'border-border-default bg-surface-secondary hover:border-border-subtle',
          )}
          onClick={() => handleEnableMirror(null)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              handleEnableMirror(null);
            }
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                !activeMirror
                  ? 'bg-blue-500 text-white'
                  : 'bg-surface-tertiary text-content-tertiary',
              )}
            >
              <Server className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-content-primary font-medium">{t('settings.pypi.officialPyPI')}</span>
                {!activeMirror && (
                  <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs font-medium text-blue-500">
                    {t('settings.pypi.currentMirror')}
                  </span>
                )}
              </div>
              <div className="text-content-tertiary text-xs">
                {t('settings.pypi.usingOfficial')}
              </div>
            </div>
          </div>
        </div>

        {/* Mirror List */}
        <div className="space-y-3">
          {config.pypi.mirrors.map((mirror) => (
            <div
              key={mirror.name}
              role="button"
              tabIndex={0}
              className={cn(
                'flex cursor-pointer items-center justify-between rounded-lg border p-3 transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none',
                mirror.enabled
                  ? 'border-blue-500/30 bg-blue-500/5'
                  : 'border-border-default bg-surface-secondary hover:border-border-subtle',
              )}
              onClick={() => handleEnableMirror(mirror.name)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  handleEnableMirror(mirror.name);
                }
              }}
              onMouseEnter={() => setHoveredMirrorName(mirror.name)}
              onMouseLeave={() => setHoveredMirrorName(null)}
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-full',
                    mirror.enabled
                      ? 'bg-blue-500 text-white'
                      : 'bg-surface-tertiary text-content-tertiary',
                  )}
                >
                  <Server className="h-4 w-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-content-primary font-medium">
                      {mirror.name}
                    </span>
                    {mirror.enabled && (
                      <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs font-medium text-blue-500">
                        {t('settings.pypi.currentMirror')}
                      </span>
                    )}
                  </div>
                  <div className="text-content-tertiary text-xs">{mirror.url}</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {hoveredMirrorName === mirror.name && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-8 px-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteMirror(mirror.name);
                    }}
                    title={t('settings.pypi.delete')}
                  >
                    <Trash2 className="text-content-tertiary hover:text-error-icon h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
