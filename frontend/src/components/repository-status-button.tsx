import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, RefreshCw, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '../utils/cn';

interface RepositoryStatus {
  repo_id: string;
  is_downloaded: boolean;
  last_updated: string | null;
  cache_path: string | null;
  has_updates?: boolean;
}

interface RepositoryStatusButtonProps {
  repoId: string;
  repoName: string;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'link';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showLabel?: boolean;
  disabled?: boolean;
  disabledTooltip?: string;
  onStatusChange?: (status: RepositoryStatus) => void;
  onDownloadComplete?: () => void;
  // If true, the download/update control will be hidden until the initial status check completes (useful for wizard UX)
  hideUntilChecked?: boolean;
}

export function RepositoryStatusButton({
  repoId,
  repoName,
  variant = 'secondary',
  size = 'sm',
  className,
  showLabel = true,
  disabled = false,
  disabledTooltip,
  onStatusChange,
  onDownloadComplete,
  hideUntilChecked = false,
}: RepositoryStatusButtonProps) {
  const { t } = useTranslation();
  const [isDownloaded, setIsDownloaded] = useState(false);
  const [lastUpdatedTime, setLastUpdatedTime] = useState<string | null>(null);
  const [hasUpdates, setHasUpdates] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [isChecking, setIsChecking] = useState(true);
  const [checkedOnce, setCheckedOnce] = useState(false); // whether initial check has completed


  const checkStatus = useCallback(
    async (signal?: AbortSignal) => {
      if (!repoId) return;
      setIsChecking(true);
      try {
        const normalizedId = repoId.toLowerCase().replace(/ /g, '_');
        const response = await fetch(`/api/repositories/${normalizedId}/status`, {
          signal,
        });
        if (response.ok) {
          const data: RepositoryStatus = await response.json();
          setIsDownloaded(data.is_downloaded);
          setLastUpdatedTime(data.last_updated);
          setHasUpdates(data.has_updates || false);
          onStatusChange?.(data);
        }
        setCheckedOnce(true);
        setIsChecking(false);
      } catch (err) {
        // Ignore AbortError - this is expected when component unmounts
        if (err instanceof Error && err.name === 'AbortError') {
          // Don't set isChecking to false here - the component may be remounting (React StrictMode)
          return;
        }
        console.error('Failed to check repository status:', err);
        setCheckedOnce(true);
        setIsChecking(false);
      }
    },
    [repoId, onStatusChange],
  );

  useEffect(() => {
    const abortController = new AbortController();

    // Create a wrapper to handle initial checking
    const initializeStatus = async () => {
      if (!repoId) return;
      try {
        const normalizedId = repoId.toLowerCase().replace(/ /g, '_');
        const response = await fetch(`/api/repositories/${normalizedId}/status`, {
          signal: abortController.signal,
        });
        if (response.ok) {
          const data: RepositoryStatus = await response.json();
          setIsDownloaded(data.is_downloaded);
          setLastUpdatedTime(data.last_updated);
          setHasUpdates(data.has_updates || false);
          onStatusChange?.(data);
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Failed to check repository status:', err);
        }
      } finally {
        // Mark that initial check completed (so callers that hideUntilChecked know we finished)
        setCheckedOnce(true);
        setIsChecking(false);
      }
    };

    initializeStatus();

    return () => {
      abortController.abort();
    };
  }, [repoId, onStatusChange]);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering parent click events (e.g. in selection cards)
    if (loading || disabled) return;

    setLoading(true);
    setError(null);
    setDownloadProgress(null);
    setProgressPercent(0);

    const normalizedId = repoId.toLowerCase().replace(/ /g, '_');

    // Use EventSource for streaming
    const eventSource = new EventSource(`/api/repositories/${normalizedId}/download`);

    eventSource.onmessage = (event) => {
      const data = event.data;
      if (data === 'DONE') {
        eventSource.close();
        setLoading(false);
        setDownloadProgress(null);
        setProgressPercent(100);
        checkStatus();
        if (onDownloadComplete) onDownloadComplete();
        return;
      }

      if (data.startsWith('ERROR:')) {
        eventSource.close();
        setLoading(false);
        setDownloadProgress(null);
        setProgressPercent(0);
        setError(data.substring(7));
        return;
      }

      // Parse percentage from Git output
      const percentMatch = data.match(/(\d+)%/);
      if (percentMatch) {
        setProgressPercent(parseInt(percentMatch[1]));
      }

      // Update progress text
      // Truncate long lines
      setDownloadProgress(data.length > 30 ? data.substring(0, 27) + '...' : data);
    };

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      eventSource.close();
      setLoading(false);
      setDownloadProgress(null);
      setProgressPercent(0);
      setError('Connection failed');
    };
  };

  if (error) {
    return (
      <div className="text-error-icon flex items-center gap-2" title={error}>
        <AlertCircle className="h-4 w-4" />
        {showLabel && <span className="text-xs">{t('repositoryStatus.error')}</span>}
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={handleDownload}
          title={t('repositoryStatus.retry')}
        >
          <RefreshCw className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  // Show loading indicator while checking status OR until initial check completes when hideUntilChecked is used
  if (isChecking || (!checkedOnce && hideUntilChecked)) {
    return (
      <div className="text-content-tertiary flex items-center gap-2">
        <Loader2 className="h-3 w-3 animate-spin" />
        {showLabel && <span className="text-xs">{t('repositoryStatus.checking')}</span>}
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {/* Show button only if initial check completed (if requested) and (not downloaded or has updates) */}
      {!isChecking && (!hideUntilChecked || checkedOnce) && (!isDownloaded || hasUpdates) && (
        <>
          {variant === 'link' ? (
            <button
              type="button"
              onClick={handleDownload}
              disabled={loading}
              className="text-info-icon text-sm hover:underline disabled:opacity-50"
              title={
                isDownloaded
                  ? `${t('repositoryStatus.update')} ${repoName}`
                  : `${t('repositoryStatus.download')} ${repoName}`
              }
            >
              {loading
                ? downloadProgress ||
                  (isDownloaded
                    ? t('repositoryStatus.updating')
                    : t('repositoryStatus.downloading'))
                : isDownloaded
                  ? showLabel && t('repositoryStatus.update')
                  : showLabel && t('repositoryStatus.download')}
            </button>
          ) : (
            <div className="group relative">
              <Button
                variant={variant as 'primary' | 'secondary' | 'ghost' | 'danger'}
                size={size}
                onClick={handleDownload}
                disabled={loading || disabled}
                className={cn(
                  'relative gap-2 overflow-hidden transition-all',
                  isDownloaded && !loading
                    ? 'text-content-secondary hover:text-content-primary hover:border-content-secondary'
                    : 'border-info-border bg-info-surface text-info-icon hover:brightness-95 dark:hover:brightness-125',
                )}
                style={
                  loading && progressPercent > 0
                    ? {
                        background: `linear-gradient(to right, rgba(59, 130, 246, 0.3) ${progressPercent}%, transparent ${progressPercent}%)`,
                      }
                    : undefined
                }
                title={
                  disabled
                    ? disabledTooltip
                    : isDownloaded
                      ? `${t('repositoryStatus.update')} ${repoName}`
                      : `${t('repositoryStatus.download')} ${repoName}`
                }
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {showLabel && (
                      <span className="max-w-[150px] truncate">
                        {downloadProgress ||
                          (isDownloaded
                            ? t('repositoryStatus.updating')
                            : t('repositoryStatus.downloading'))}
                      </span>
                    )}
                  </>
                ) : isDownloaded ? (
                  <>
                    <RefreshCw className="h-4 w-4" />
                    {showLabel && <span>{t('repositoryStatus.update')}</span>}
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    {showLabel && <span>{t('repositoryStatus.download')}</span>}
                  </>
                )}
              </Button>
              {disabled && disabledTooltip && (
                <div className="bg-surface-inverse text-content-inverse absolute top-full left-1/2 z-10 mt-1 hidden -translate-x-1/2 rounded-md px-3 py-2 text-xs whitespace-nowrap shadow-lg group-hover:block">
                  {disabledTooltip}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Show status icon only if not checking, downloaded, not loading, and up-to-date (no updates) */}
      {!isChecking && isDownloaded && !loading && !hasUpdates && (
        <div className="group relative">
          <CheckCircle2 className="text-success-icon h-4 w-4" />
          <div className="bg-surface-inverse text-content-inverse absolute top-6 left-1/2 z-10 hidden -translate-x-1/2 rounded-md px-3 py-2 text-xs whitespace-nowrap shadow-lg group-hover:block">
            {lastUpdatedTime
              ? t('repositoryStatus.updatedAt', {
                  date: new Date(parseInt(lastUpdatedTime)).toLocaleDateString(),
                })
              : t('repositoryStatus.upToDate')}
          </div>
        </div>
      )}
    </div>
  );
}
