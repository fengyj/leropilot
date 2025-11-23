import {
  Plus,
  Play,
  Terminal,
  Settings,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  name: string;
  version: string;
  python: string;
  torch: string;
  status: 'ready' | 'error' | 'installing';
  type: 'official' | 'custom';
}

const MOCK_ENVS: Environment[] = [
  {
    id: '1',
    name: 'LeRobot v2.0',
    version: 'v2.0.0',
    python: '3.10',
    torch: '2.1.2+cu121',
    status: 'ready',
    type: 'official',
  },
  {
    id: '2',
    name: 'Experimental Fork',
    version: 'dev-branch',
    python: '3.11',
    torch: '2.4.0',
    status: 'error',
    type: 'custom',
  },
];

export function EnvironmentListPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();

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

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
        {MOCK_ENVS.map((env) => (
          <Card key={env.id} className="flex flex-col">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <CardTitle>{env.name}</CardTitle>
                  <div className="text-content-secondary flex items-center gap-2 text-sm">
                    <span className="capitalize">{t(`environments.${env.type}`)}</span>
                    <span>•</span>
                    <span>{env.version}</span>
                  </div>
                </div>
                {env.status === 'ready' ? (
                  <CheckCircle2 className="text-success-icon h-5 w-5" />
                ) : (
                  <AlertCircle className="text-warning-icon h-5 w-5" />
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-content-tertiary">{t('environments.python')}</p>
                  <p className="text-content-primary font-medium">{env.python}</p>
                </div>
                <div>
                  <p className="text-content-tertiary">{t('environments.pytorch')}</p>
                  <p className="text-content-primary font-medium">{env.torch}</p>
                </div>
              </div>
              {env.status === 'error' && (
                <div className="bg-warning-surface text-warning-content rounded-md p-3 text-xs">
                  {t('environments.errorMessage')}
                </div>
              )}
            </CardContent>
            <CardFooter className="border-border-default grid grid-cols-3 gap-2 border-t p-4">
              <Button variant="secondary" size="sm" className="w-full">
                <Play className="mr-2 h-3 w-3" />
                {t('environments.launch')}
              </Button>
              <Button variant="secondary" size="sm" className="w-full">
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
    </div>
  );
}
