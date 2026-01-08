import React from 'react';
import { cn } from '../../utils/cn';
import { Button } from './button';

interface EmptyStateProps {
    /** Icon to display (should be a Lucide icon component) */
    icon?: React.ReactNode;
    /** Primary message */
    message: string;
    /** Optional description text */
    description?: string;
    /** Optional action button */
    action?: {
        label: string;
        icon?: React.ReactNode;
        onClick: () => void;
    };
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Additional CSS classes */
    className?: string;
}

const sizeConfig = {
    sm: {
        container: 'h-24 py-4',
        icon: 'h-6 w-6',
        message: 'text-sm',
        description: 'text-xs',
        gap: 'gap-2',
    },
    md: {
        container: 'h-32 py-6',
        icon: 'h-8 w-8',
        message: 'text-base',
        description: 'text-sm',
        gap: 'gap-3',
    },
    lg: {
        container: 'h-64 py-8',
        icon: 'h-12 w-12',
        message: 'text-lg',
        description: 'text-base',
        gap: 'gap-4',
    },
};

/**
 * A reusable empty state component for displaying when no data is available.
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
    icon,
    message,
    description,
    action,
    size = 'md',
    className,
}) => {
    const config = sizeConfig[size];

    return (
        <div
            className={cn(
                'flex flex-col items-center justify-center rounded-lg border border-dashed',
                'border-border-default bg-surface-secondary/50',
                config.container,
                config.gap,
                className,
            )}
        >
            {icon && (
                <div className={cn('text-content-tertiary', config.icon)}>
                    {icon}
                </div>
            )}
            <p className={cn('text-content-secondary', config.message)}>{message}</p>
            {description && (
                <p className={cn('text-content-tertiary', config.description)}>
                    {description}
                </p>
            )}
            {action && (
                <Button onClick={action.onClick}>
                    {action.icon}
                    {action.label}
                </Button>
            )}
        </div>
    );
};
