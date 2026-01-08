import React from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';
import { DeviceStatus } from '../../../types/hardware';

export const StatusIcon: React.FC<{ status: DeviceStatus }> = ({ status }) => {
    const { t } = useTranslation();

    const icon = () => {
        switch (status) {
            case 'available':
                return <CheckCircle2 className="text-success-icon h-5 w-5" />;
            case 'occupied':
                return <Clock className="text-warning-icon h-5 w-5" />;
            case 'invalid':
                return <AlertTriangle className="text-error-icon h-5 w-5" />;
            case 'offline':
            default:
                return <div className="h-5 w-5 rounded-full border-2 border-border-default opacity-50" />;
        }
    };

    const statusKey = `hardware.status.${status}` as const;

    return (
        <div className="cursor-help" title={t(statusKey)}>
            {icon()}
        </div>
    );
};
