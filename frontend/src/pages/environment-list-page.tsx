import {
  Plus,
  Play,
  Terminal,
  Settings,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { Button } from '../components/ui/button';
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

  useEffect(() => {
    const abortController = new AbortController();

    const fetchEnvironments = async () => {
      try {
        const response = await fetch('/api/environments', {
          signal: abortController.signal,
        });
        if (response.ok) {
          const data = await response.json();
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

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="text-content-tertiary h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-6">
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
                    <CheckCircle2 className="text-success-icon h-5 w-5" />
                  ) : env.status === 'error' ? (
                    <AlertCircle className="text-warning-icon h-5 w-5" />
                  ) : (
                    <Loader2 className="text-content-tertiary h-5 w-5 animate-spin" />
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
              <CardFooter className="border-border-default grid grid-cols-3 gap-2 border-t p-4">
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  disabled={env.status !== 'ready'}
                >
                  <Play className="mr-2 h-3 w-3" />
                  {t('environments.launch')}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  disabled={env.status !== 'ready'}
                >
                  <Terminal className="mr-2 h-3 w-3" />
                  {t('environments.shell')}
                </Button>
                <Button variant="ghost" size="sm" className="w-full px-0">
                  <Settings className="h-4 w-4" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
