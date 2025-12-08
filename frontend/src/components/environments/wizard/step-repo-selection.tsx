import { Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useWizardStore } from '../../../stores/environment-wizard-store';
import { cn } from '../../../utils/cn';
import { RepositoryStatusButton } from '../../repository-status-button';
import { useEffect, useState } from 'react';

interface Repository {
  id: string;
  name: string;
  url: string;
  is_default: boolean;
}

export function StepRepoSelection() {
  const { t } = useTranslation();
  const { config, updateConfig } = useWizardStore();
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const response = await fetch('/api/repositories');
        if (response.ok) {
          const data = await response.json();
          setRepos(data);
          // Set default repo if none selected
          if (!config.repositoryId && data.length > 0) {
            const defaultRepo = data.find((r: Repository) => r.is_default) || data[0];
            updateConfig({
              repositoryId: defaultRepo.id,
              repositoryName: defaultRepo.name,
              repositoryUrl: defaultRepo.url,
            });
          }
        }
      } catch (error) {
        console.error('Failed to fetch repositories:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchRepos();
  }, [config.repositoryId, updateConfig]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-content-primary text-lg font-medium">
          {t('wizard.repoSelection.title')}
        </h3>
        <p className="text-content-secondary text-sm">
          {t('wizard.repoSelection.subtitle')}
        </p>
      </div>

      <div className="grid gap-4">
        {repos.map((repo) => (
          <div
            key={repo.id}
            onClick={() =>
              updateConfig({
                repositoryId: repo.id,
                repositoryName: repo.name,
                repositoryUrl: repo.url,
              })
            }
            onKeyDown={(e) =>
              e.key === 'Enter' &&
              updateConfig({
                repositoryId: repo.id,
                repositoryName: repo.name,
                repositoryUrl: repo.url,
              })
            }
            role="button"
            tabIndex={0}
            className={cn(
              'relative flex cursor-pointer items-start gap-4 rounded-lg border p-4 transition-all',
              config.repositoryId === repo.id
                ? 'border-blue-600 bg-blue-600/5 dark:bg-blue-600/10'
                : 'border-border-default bg-surface-secondary hover:border-border-subtle',
            )}
          >
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-content-primary font-medium">{repo.name}</span>
                {repo.is_default && (
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 uppercase dark:bg-blue-900/30 dark:text-blue-300">
                    {t('wizard.repoSelection.official')}
                  </span>
                )}
              </div>
              <p className="text-content-tertiary text-sm">{repo.url}</p>

              <div className="pt-2">
                <RepositoryStatusButton
                  repoId={repo.id}
                  repoName={repo.name}
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 text-xs hover:bg-transparent"
                  showLabel={true}
                />
              </div>
            </div>

            {config.repositoryId === repo.id && (
              <div className="absolute top-4 right-4">
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
                  <Check className="h-3 w-3" />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="bg-surface-tertiary rounded-lg p-4 text-sm">
        <p className="text-content-secondary">
          {t('wizard.repoSelection.addCustom')}{' '}
          <Link
            to="/settings?section=repositories"
            className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
          >
            {t('wizard.repoSelection.settingsLink')}
          </Link>
        </p>
      </div>
    </div>
  );
}
