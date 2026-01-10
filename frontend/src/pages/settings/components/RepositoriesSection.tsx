import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Globe, Star } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { RepositoryStatusButton } from '../../../components/repository-status-button';
import { cn } from '../../../utils/cn';
import type { AppConfig, RepositorySource } from '../types';

interface RepositoriesSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
  savedConfig: AppConfig | null;
}

export function RepositoriesSection({
  config,
  setConfig,
  savedConfig,
}: RepositoriesSectionProps) {
  const { t } = useTranslation();
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoUrl, setNewRepoUrl] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [hoveredRepoId, setHoveredRepoId] = useState<string | null>(null);

  const handleAddRepository = () => {
    if (!newRepoName || !newRepoUrl) return;

    const newRepo: RepositorySource = {
      id: uuidv4(),
      name: newRepoName,
      url: newRepoUrl,
      is_default: false,
    };

    setConfig({
      ...config,
      repositories: {
        ...config.repositories,
        lerobot_sources: [...config.repositories.lerobot_sources, newRepo],
      },
    });

    setNewRepoName('');
    setNewRepoUrl('');
    setIsAdding(false);
  };

  const handleDeleteRepository = (id: string) => {
    const repoToDelete = config.repositories.lerobot_sources.find((r) => r.id === id);
    if (
      repoToDelete &&
      window.confirm(
        t('settings.repositories.deleteConfirm', { name: repoToDelete.name }),
      )
    ) {
      setConfig({
        ...config,
        repositories: {
          ...config.repositories,
          lerobot_sources: config.repositories.lerobot_sources.filter(
            (r) => r.id !== id,
          ),
        },
      });
    }
  };

  const handleSetDefault = (id: string) => {
    setConfig({
      ...config,
      repositories: {
        ...config.repositories,
        lerobot_sources: config.repositories.lerobot_sources.map((r) => ({
          ...r,
          is_default: r.id === id,
        })),
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <CardTitle>{t('settings.repositories.title')}</CardTitle>
            <p className="text-content-secondary text-sm">
              {t('settings.repositories.description')}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setIsAdding(!isAdding)}>
            <Plus className="mr-2 h-4 w-4" />
            {t('settings.repositories.addSource')}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add New Repository Form */}
        {isAdding && (
          <div className="bg-surface-secondary mb-4 space-y-3 rounded-lg border p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-content-secondary text-xs font-medium uppercase">
                  {t('settings.repositories.name')}
                </label>
                <input
                  type="text"
                  className="border-border-default bg-surface-primary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={newRepoName}
                  onChange={(e) => setNewRepoName(e.target.value)}
                  placeholder="e.g. Official"
                />
              </div>
              <div className="space-y-2">
                <label className="text-content-secondary text-xs font-medium uppercase">
                  {t('settings.repositories.url')}
                </label>
                <input
                  type="text"
                  className="border-border-default bg-surface-primary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  value={newRepoUrl}
                  onChange={(e) => setNewRepoUrl(e.target.value)}
                  placeholder="https://github.com/..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsAdding(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                size="sm"
                onClick={handleAddRepository}
                disabled={!newRepoName || !newRepoUrl}
              >
                {t('common.confirm')}
              </Button>
            </div>
          </div>
        )}

        {/* Repository List */}
        <div className="space-y-3">
          {config.repositories.lerobot_sources.map((repo) => (
            <div
              key={repo.id}
              className={cn(
                'group flex items-center justify-between rounded-lg border p-3 transition-colors',
                repo.is_default
                  ? 'border-blue-500/30 bg-blue-500/5'
                  : 'border-border-default bg-surface-secondary',
              )}
              onMouseEnter={() => setHoveredRepoId(repo.id)}
              onMouseLeave={() => setHoveredRepoId(null)}
            >
              <div className="flex flex-1 items-center gap-3">
                <div
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-full',
                    repo.is_default
                      ? 'bg-blue-500 text-white'
                      : 'bg-surface-tertiary text-content-tertiary',
                  )}
                >
                  <Globe className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-content-primary font-medium">
                      {repo.name}
                    </span>
                    {repo.is_default && (
                      <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs font-medium text-blue-500">
                        {t('settings.repositories.default')}
                      </span>
                    )}
                  </div>
                  <div className="text-content-tertiary text-xs">{repo.url}</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {hoveredRepoId === repo.id && !repo.is_default && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-8 px-0"
                      onClick={() => handleSetDefault(repo.id)}
                      title={t('settings.repositories.setAsDefault')}
                    >
                      <Star className="text-content-tertiary h-4 w-4 hover:text-blue-500" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-8 px-0"
                      onClick={() => handleDeleteRepository(repo.id)}
                      title={t('settings.repositories.delete')}
                    >
                      <Trash2 className="text-content-tertiary hover:text-error-icon h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>

              <RepositoryStatusButton
                repoId={repo.id}
                repoName={repo.name}
                variant="secondary"
                size="sm"
                showLabel={false}
                disabled={
                  !savedConfig?.repositories.lerobot_sources.some(
                    (r) => r.id === repo.id,
                  )
                }
                disabledTooltip={t('settings.repositories.saveBeforeDownload')}
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}