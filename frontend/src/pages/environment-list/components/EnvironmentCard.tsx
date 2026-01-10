import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Play,
    Terminal,
    MoreVertical,
    Trash2,
    AlertCircle,
    CheckCircle2,
    Loader2,
} from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { DropdownMenu } from '../../../components/ui/dropdown-menu';
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from '../../../components/ui/card';
import { Environment } from '../types';

interface EnvironmentCardProps {
    env: Environment;
    openingTerminal: string | null;
    onOpenTerminal: (envId: string) => void;
    onDelete: (envId: string, envName: string) => void;
}

export const EnvironmentCard: React.FC<EnvironmentCardProps> = ({
    env,
    openingTerminal,
    onOpenTerminal,
    onDelete,
}) => {
    const { t } = useTranslation();

    return (
        <Card className="flex flex-col max-w-[480px] w-full">
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
                        onClick={() => onOpenTerminal(env.id)}
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
                            onClick: () => onDelete(env.id, env.display_name),
                            variant: 'danger',
                            icon: <Trash2 className="text-content-tertiary hover:text-error-icon h-4 w-4" />,
                        },
                    ]}
                    align="right"
                />
            </CardFooter>
        </Card>
    );
};
