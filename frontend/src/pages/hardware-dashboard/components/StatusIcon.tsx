import React from 'react';
import { useTranslation } from 'react-i18next';
import { DeviceStatus } from '../../../types/hardware';
import { StatusBadge, StatusVariant, PulseSpeed } from '../../../components/ui/status-badge';

export const StatusIcon: React.FC<{ status: DeviceStatus }> = ({ status }) => {
    const { t } = useTranslation();

    const getStatusConfig = (s: DeviceStatus): { variant: StatusVariant; pulse?: PulseSpeed } => {
        switch (s) {
            case 'available':
                // Use default 'slow' pulse for success
                return { variant: 'success' };
            case 'occupied':
                return { variant: 'warning' };
            case 'invalid':
                return { variant: 'error', pulse: 'fast' };
            case 'offline':
            default:
                return { variant: 'neutral', pulse: 'none' };
        }
    };

    const config = getStatusConfig(status);
    const statusKey = `hardware.status.${status}`;

    return (
        <StatusBadge 
            variant={config.variant} 
            pulse={config.pulse} 
            title={t(statusKey)}
        >
            {t(statusKey)}
        </StatusBadge>
    );
};
