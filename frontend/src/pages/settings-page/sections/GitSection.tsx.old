import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { cn } from '../../../utils/cn';
import { useGitValidation } from '../../../hooks/useGitValidation';
import type { AppConfig } from '../types';

interface GitSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
  loadConfig: () => Promise<void>;
  setMessage: (message: { type: 'success' | 'error'; text: string } | null) => void;
}

export function GitSection({
  config,
  setConfig,
  loadConfig,
  setMessage,
}: GitSectionProps) {
  const { t } = useTranslation();
  const gitValidation = useGitValidation();
  const { validate, clear } = gitValidation;

  const [bundledGitStatus, setBundledGitStatus] = useState<{
    installed: boolean;
    version?: string;
    path?: string;
    message?: string;
    error?: string;
  } | null>(null);

  const [bundledGitDownloadProgress, setBundledGitDownloadProgress] = useState<{
    message: string;
    progress: number;
  } | null>(null);

  // Check bundled git status
  useEffect(() => {
    if (config.tools.git.type !== 'bundled') {
      return;
    }

    const abortController = new AbortController();

    fetch('/api/tools/git/bundled/status', {
      signal: abortController.signal,
    })
      .then((res) => res.json())
      .then((data) => setBundledGitStatus(data))
      .catch((err) => {
        if (err.name === 'AbortError') {
          return;
        }
        console.error('Failed to check bundled git:', err);
      });

    return () => {
      abortController.abort();
    };
  }, [config.tools.git.type]);

  // Validate custom Git path on change
  useEffect(() => {
    if (config.tools.git.type === 'custom' && config.tools.git.custom_path) {
      validate(config.tools.git.custom_path);
    } else {
      clear();
    }
  }, [config.tools.git.type, config.tools.git.custom_path, validate, clear]);

  const handleDownloadBundledGit = async () => {
    setBundledGitDownloadProgress({ message: t('settings.tools.startingDownload'), progress: 0 });
    try {
      const eventSource = new EventSource('/api/tools/git/bundled/download');

      eventSource.onmessage = (event) => {
        if (event.data === 'DONE') {
          eventSource.close();
          setBundledGitDownloadProgress(null);
          // Refresh status
          fetch('/api/tools/git/bundled/status')
            .then((res) => res.json())
            .then((data) => setBundledGitStatus(data));
          // Reload config
          loadConfig();
          return;
        }

        if (event.data.startsWith('ERROR:')) {
          eventSource.close();
          setBundledGitDownloadProgress(null);
          setMessage({ type: 'error', text: event.data.substring(7) });
          return;
        }

        try {
          const data = JSON.parse(event.data);
          setBundledGitDownloadProgress(data);
        } catch (e) {
          console.error('Failed to parse progress:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setBundledGitDownloadProgress(null);
        setMessage({ type: 'error', text: t('settings.tools.connectionLost') });
      };
    } catch (err) {
      console.error('Failed to start download:', err);
      setBundledGitDownloadProgress(null);
      setMessage({ type: 'error', text: t('settings.tools.failedToDownload') });
    }
  };

  const handleAutoDetectGit = async () => {
    try {
      const whichResponse = await fetch('/api/tools/git/which');
      const whichData = await whichResponse.json();
      if (whichData.path) {
        setConfig({
          ...config,
          tools: {
            ...config.tools,
            git: {
              ...config.tools.git,
              custom_path: whichData.path,
            },
          },
        });
        // Validate the detected path
        await gitValidation.validate(whichData.path);
      }
    } catch (err) {
      console.error('Failed to get git path:', err);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="space-y-1.5">
          <CardTitle>{t('settings.tools.title')}</CardTitle>
          <p className="text-content-secondary text-sm">
            {t('settings.tools.description')}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <label htmlFor="git-source-bundled" className="text-content-primary text-sm font-medium">
            {t('settings.tools.source')}
          </label>

          {/* Source selection */}
          <div className="flex gap-3">
            <button
              onClick={() =>
                setConfig({
                  ...config,
                  tools: {
                    ...config.tools,
                    git: { ...config.tools.git, type: 'bundled' },
                  },
                })
              }
              className={cn(
                'flex-1 rounded-md border p-3 transition-all',
                config.tools.git.type === 'bundled'
                  ? 'border-blue-600 bg-blue-600/10 text-blue-500'
                  : 'border-border-default bg-surface-tertiary text-content-secondary hover:border-border-subtle',
              )}
            >
              {t('settings.tools.bundled')}
            </button>
            <button
              onClick={() => {
                setConfig({
                  ...config,
                  tools: {
                    ...config.tools,
                    git: { ...config.tools.git, type: 'custom' },
                  },
                });
                setBundledGitStatus(null);
              }}
              className={cn(
                'flex-1 rounded-md border p-3 transition-all',
                config.tools.git.type === 'custom'
                  ? 'border-blue-600 bg-blue-600/10 text-blue-500'
                  : 'border-border-default bg-surface-tertiary text-content-secondary hover:border-border-subtle',
              )}
            >
              {t('settings.tools.custom')}
            </button>
          </div>

          {/* Bundled Git Status */}
          {config.tools.git.type === 'bundled' && (
            <div className="space-y-2">
              <div className="relative">
                <input
                  id="git-source-bundled"
                  name="git-source-bundled"
                  type="text"
                  readOnly
                  aria-label={t('settings.tools.bundledInstalled')}
                  className={cn(
                    'border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 pr-10 focus:outline-none',
                    bundledGitStatus?.installed
                      ? 'border-green-500'
                      : 'border-amber-500',
                  )}
                  value={
                    bundledGitStatus?.installed
                      ? bundledGitStatus.path ||
                      bundledGitStatus.version ||
                      t('settings.tools.bundledInstalled')
                      : t('settings.tools.notInstalled')
                  }
                />
                {/* Status Icon */}
                <div className="absolute top-1/2 right-3 -translate-y-1/2">
                  {bundledGitStatus?.installed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                  )}
                </div>
              </div>

              {/* Download Button */}
              {!bundledGitStatus?.installed && (
                <button
                  type="button"
                  onClick={handleDownloadBundledGit}
                  disabled={!!bundledGitDownloadProgress}
                  className="mt-2 flex items-center gap-2 text-sm text-blue-500 hover:underline disabled:opacity-50"
                >
                  {bundledGitDownloadProgress ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {bundledGitDownloadProgress.message}
                    </>
                  ) : (
                    t('settings.tools.downloadAndInstall')
                  )}
                </button>
              )}

              {/* Error Message */}
              {bundledGitStatus?.error && (
                <p className="text-error-content mt-1 text-xs">
                  {bundledGitStatus.error}
                </p>
              )}
            </div>
          )}

          {/* Custom path input */}
          {config.tools.git.type === 'custom' && (
            <div className="space-y-2">
              <div className="relative">
                <input
                  id="git-source-custom"
                  name="git-source-custom"
                  type="text"
                  aria-label={t('settings.tools.gitPathPlaceholder')}
                  placeholder={t('settings.tools.gitPathPlaceholder')}
                  className={cn(
                    'border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 pr-10 focus:border-blue-500 focus:outline-none',
                    gitValidation.error &&
                    'border-error-border focus:border-error-border',
                    !gitValidation.error &&
                    gitValidation.validation &&
                    'border-green-500',
                  )}
                  value={config.tools.git.custom_path || ''}
                  onChange={(e) => {
                    setConfig({
                      ...config,
                      tools: {
                        ...config.tools,
                        git: { ...config.tools.git, custom_path: e.target.value },
                      },
                    });
                    gitValidation.clear();
                  }}
                  onBlur={(e) => {
                    const path = e.target.value;
                    if (path) {
                      gitValidation.validate(path);
                    }
                  }}
                />
                {/* Validation icon */}
                <div className="absolute top-1/2 right-3 -translate-y-1/2">
                  {gitValidation.isValidating ? (
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  ) : gitValidation.error ? (
                    <div className="group relative">
                      <XCircle className="h-4 w-4 text-red-500" />
                      <div className="absolute top-6 right-0 z-10 hidden w-64 rounded-md bg-gray-900 px-3 py-2 text-xs text-white shadow-lg group-hover:block">
                        {gitValidation.error}
                      </div>
                    </div>
                  ) : gitValidation.validation ? (
                    <div className="group relative">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <div className="absolute top-6 right-0 z-10 hidden rounded-md bg-gray-900 px-3 py-2 text-xs whitespace-nowrap text-white shadow-lg group-hover:block">
                        {gitValidation.validation}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
              {/* Auto-detect button */}
              {!config.tools.git.custom_path && (
                <button
                  type="button"
                  onClick={handleAutoDetectGit}
                  disabled={gitValidation.isValidating}
                  className="mt-2 flex items-center gap-2 text-sm text-blue-500 hover:underline disabled:opacity-50"
                >
                  {t('settings.tools.autoDetect')}
                </button>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
