import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
    Activity,
    Settings,
    MoreVertical,
    Edit,
    Loader2,
    Trash2,
} from 'lucide-react';
import { Button } from '../../../components/ui/button';
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from '../../../components/ui/card';
import { DropdownMenu } from '../../../components/ui/dropdown-menu';
import { Robot, DeviceStatus } from '../../../types/hardware';
import { StatusIcon } from './StatusIcon';

export const RobotCard: React.FC<{
    robot: Robot;
    isRefreshing?: boolean;
    onRefresh: (id: string) => void;
    onDelete: (id: string, name: string) => void;
}> = ({ robot, isRefreshing, onRefresh, onDelete }) => {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const interfaces = robot.motor_bus_connections
        ? Object.values(robot.motor_bus_connections)
            .map((conn) => conn.interface)
            .filter(Boolean)
            .join(', ')
        : '';

    return (
        <Card className={`flex flex-col h-full relative overflow-hidden transition-all duration-300 ${isRefreshing ? 'scale-[0.98] opacity-60' : 'hover:shadow-md'}`}>
            {isRefreshing && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-primary/60 backdrop-blur-[1px]">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
            )}
            <CardHeader>
                <div className="flex items-start justify-between">
                    <div className="flex items-start min-w-0">
                        <div className="min-w-0">
                            <div className="flex flex-col gap-1">
                                <CardTitle className="text-lg leading-tight break-words" title={robot.name}>
                                    {robot.name}
                                </CardTitle>
                                {robot.is_transient && (
                                    <div>
                                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-tertiary text-content-secondary border border-border-default">
                                            临时设备
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="shrink-0 ml-2">
                        <StatusIcon status={robot.status as DeviceStatus} />
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-4">
                <div className="space-y-1">
                    <p className="text-content-tertiary text-xs">Interfaces</p>
                    <p className="text-content-primary text-sm font-medium break-all" title={interfaces}>
                        {robot.status !== 'offline' && interfaces ? interfaces : '—'}
                    </p>
                </div>
            </CardContent>
            <CardFooter className="border-border-default flex items-center justify-between border-t p-4">
                <div className="flex gap-2 w-full mr-2">
                    <Button
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                        disabled={robot.status !== 'available'}
                        onClick={() => navigate(`/hardware/${robot.id}/control`)}
                    >
                        <Activity className="mr-2 h-3 w-3" />
                        Control
                    </Button>
                    <Button
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                        onClick={() => navigate(`/hardware/${robot.id}/calibrate`)}
                    >
                        <Settings className="mr-2 h-3 w-3" />
                        Calibrate
                    </Button>
                </div>
                <DropdownMenu
                    trigger={
                        <div className="flex items-center gap-1 cursor-pointer text-content-tertiary hover:text-content-primary p-1">
                            <MoreVertical className="h-4 w-4" />
                        </div>
                    }
                    items={[
                        {
                            id: 'edit',
                            label: 'Edit Configuration',
                            onClick: () => navigate(`/hardware/${robot.id}/settings`),
                            icon: <Edit className="h-4 w-4" />,
                        },
                        {
                            id: 'refresh',
                            label: 'Refresh Status',
                            onClick: () => onRefresh(robot.id),
                            icon: <Loader2 className="h-4 w-4" />,
                        },
                        {
                            id: 'delete',
                            label: t('common.delete'),
                            onClick: () => onDelete(robot.id, robot.name),
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
