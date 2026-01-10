import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Play,
    Terminal,
    MoreVertical,
    Trash2,
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

import { StatusBadge } from '../../../components/ui/status-badge';

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
                        <StatusBadge variant="success" title={t('environments.status.ready')}>
                            {t('environments.status.ready')}
                        </StatusBadge>
                    ) : env.status === 'error' ? (
                        <StatusBadge variant="error" pulse="fast" title={t('environments.status.error')}>
                            {t('environments.status.error')}
                        </StatusBadge>
                    ) : (
                        <StatusBadge variant="neutral" icon={<Loader2 className="h-3 w-3 animate-spin" />} title={t('environments.status.installing')}>
                            {t('environments.status.installing')}
                        </StatusBadge>
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
                        <>
                            <MoreVertical className="h-4 w-4" />
                            <span className="sr-only">{t('common.more')}</span>
                        </>
                    }
                    triggerClassName="h-8 w-8 p-0 text-content-tertiary hover:text-content-primary justify-center"
                    items={[
                        {
                            id: 'delete',
                            label: t('environments.delete'),
                            onClick: () => onDelete(env.id, env.display_name),
                            variant: 'danger',
                            icon: <Trash2 className="h-4 w-4" />,
                        },
                    ]}
                    align="right"
                />
            </CardFooter>
        </Card>
    );
};
