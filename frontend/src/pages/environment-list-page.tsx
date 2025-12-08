import {
  Plus,
  Play,
  Terminal,
  MoreVertical,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { Button } from '../components/ui/button';
import { DropdownMenu } from '../components/ui/dropdown-menu';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../components/ui/card';

interface Environment {
  id: string;
  display_name: string;
  ref: string;
  python_version: string;
  torch_version: string;
  status: 'pending' | 'installing' | 'ready' | 'error';
  error_message?: string;
}

export function EnvironmentListPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    isOpen: boolean;
    envId: string | null;
    envName: string | null;
  }>({
    isOpen: false,
    envId: null,
    envName: null,
  });
  const [openingTerminal, setOpeningTerminal] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    const fetchEnvironments = async () => {
      try {
        const response = await fetch('/api/environments', {
          signal: abortController.signal,
        });
        if (response.ok) {
          const data = await response.json();
          // Sort by display_name alphabetically
          data.sort((a: Environment, b: Environment) =>
            a.display_name.localeCompare(b.display_name),
          );
          setEnvironments(data);
        }
      } catch (error) {
        // Ignore AbortError - this is expected when component unmounts
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to fetch environments:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchEnvironments();

    return () => {
      abortController.abort();
    };
  }, []);

  const handleDeleteClick = (envId: string, envName: string) => {
    setDeleteConfirm({
      isOpen: true,
      envId,
      envName,
    });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.envId) return;

    try {
      const response = await fetch(`/api/environments/${deleteConfirm.envId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        // Remove the deleted environment from the list
        setEnvironments((prev) => prev.filter((env) => env.id !== deleteConfirm.envId));
        setDeleteConfirm({ isOpen: false, envId: null, envName: null });
      } else {
        console.error('Failed to delete environment:', response.statusText);
      }
    } catch (error) {
      console.error('Error deleting environment:', error);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirm({ isOpen: false, envId: null, envName: null });
  };

  const handleOpenTerminal = async (envId: string) => {
    setOpeningTerminal(envId);
    try {
      const response = await fetch(`/api/environments/${envId}/open-terminal`, {
        method: 'POST',
      });

      if (response.ok) {
        // Success - terminal opened
        console.log(t('environments.terminalOpenSuccess'));
      } else {
        const error = await response.json();
        console.error(t('environments.terminalOpenError'), error.detail);
        alert(
          `${t('environments.terminalOpenError')}: ${error.detail || 'Unknown error'}`,
        );
      }
    } catch (error) {
      console.error('Error opening terminal:', error);
      alert(t('environments.terminalOpenError'));
    } finally {
      setOpeningTerminal(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-6">
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        title={t('environments.deleteConfirmTitle')}
        message={t('environments.deleteConfirmMessage')}
        confirmText={t('common.delete')}
        cancelText={t('common.cancel')}
        variant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-content-primary text-2xl font-bold tracking-tight">
            {t('environments.title')}
          </h1>
          <p className="text-content-secondary">{t('environments.subtitle')}</p>
        </div>
        <Button onClick={() => navigate('/environments/new')}>
          <Plus className="mr-2 h-4 w-4" />
          {t('environments.createNew')}
        </Button>
      </div>

      {environments.length === 0 ? (
        <div className="border-border-default bg-surface-secondary/50 flex h-64 flex-col items-center justify-center rounded-lg border border-dashed">
          <p className="text-content-secondary mb-4 text-lg">
            {t('environments.noEnvironments')}
          </p>
          <Button onClick={() => navigate('/environments/new')}>
            <Plus className="mr-2 h-4 w-4" />
            {t('environments.createNew')}
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {environments.map((env) => (
            <Card key={env.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle>{env.display_name}</CardTitle>
                    <div className="text-content-secondary flex items-center gap-2 text-sm">
                      <span>{env.ref}</span>
                    </div>
                  </div>
                  {env.status === 'ready' ? (
                    <div title={t('environments.status.ready')}>
                      <CheckCircle2 className="text-success-icon h-5 w-5" />
                    </div>
                  ) : env.status === 'error' ? (
                    <div title={t('environments.status.error')}>
                      <AlertCircle className="text-warning-icon h-5 w-5" />
                    </div>
                  ) : (
                    <div title={t('environments.status.installing')}>
                      <Loader2 className="text-content-tertiary h-5 w-5 animate-spin" />
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-content-tertiary">{t('environments.python')}</p>
                    <p className="text-content-primary font-medium">
                      {env.python_version}
                    </p>
                  </div>
                  <div>
                    <p className="text-content-tertiary">{t('environments.pytorch')}</p>
                    <p className="text-content-primary font-medium">
                      {env.torch_version}
                    </p>
                  </div>
                </div>
                {env.status === 'error' && env.error_message && (
                  <div className="bg-warning-surface text-warning-content rounded-md p-3 text-xs">
                    {env.error_message}
                  </div>
                )}
              </CardContent>
              <CardFooter className="border-border-default flex items-center justify-between border-t p-4">
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="flex-1"
                    disabled={env.status !== 'ready'}
                  >
                    <Play className="mr-2 h-3 w-3" />
                    {t('environments.launch')}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="flex-1"
                    disabled={env.status !== 'ready' || openingTerminal === env.id}
                    onClick={() => handleOpenTerminal(env.id)}
                  >
                    {openingTerminal === env.id ? (
                      <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                    ) : (
                      <Terminal className="mr-2 h-3 w-3" />
                    )}
                    {t('environments.shell')}
                  </Button>
                </div>
                <DropdownMenu
                  trigger={
                    <div className="flex items-center gap-1">
                      <MoreVertical className="h-4 w-4" />
                    </div>
                  }
                  items={[
                    {
                      id: 'delete',
                      label: t('environments.delete'),
                      onClick: () => handleDeleteClick(env.id, env.display_name),
                      variant: 'danger',
                      icon: <Trash2 className="h-4 w-4" />,
                    },
                  ]}
                  align="right"
                />
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
