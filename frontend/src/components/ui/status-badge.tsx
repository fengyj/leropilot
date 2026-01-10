import React from 'react';
import { cn } from '../../utils/cn';

export type StatusVariant = 'success' | 'warning' | 'error' | 'neutral' | 'info';
export type PulseSpeed = 'none' | 'slow' | 'normal' | 'fast';

interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    variant?: StatusVariant;
    pulse?: PulseSpeed;
    icon?: React.ReactNode;
    children: React.ReactNode;
}

const variantConfig = {
    success: {
        container: "bg-success-surface text-success-content border-success-border",
        dot: "bg-success-icon",
    },
    warning: {
        container: "bg-warning-surface text-warning-content border-warning-border",
        dot: "bg-warning-icon",
    },
    error: {
        container: "bg-error-surface text-error-content border-error-border",
        dot: "bg-error-icon",
    },
    neutral: {
        container: "bg-surface-tertiary text-content-secondary border-border-default",
        dot: "bg-content-tertiary",
    },
    info: {
        container: "bg-info-surface text-info-content border-info-border",
        dot: "bg-info-icon",
    }
};

const pulseAnimations = {
    none: "",
    slow: "animate-ping-slow",
    normal: "animate-ping",
    fast: "animate-ping-fast",
};

const defaultPulseMap: Record<StatusVariant, PulseSpeed> = {
    success: 'slow',
    warning: 'normal',
    error: 'fast',
    neutral: 'none',
    info: 'none',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
    variant = 'neutral',
    pulse,
    icon,
    children,
    className,
    ...props
}) => {
    const config = variantConfig[variant];
    // If pulse is explicitly provided, use it. Otherwise use the default for the variant.
    const effectivePulse = pulse ?? defaultPulseMap[variant];
    const animationClass = pulseAnimations[effectivePulse];

    return (
        <span 
            className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border select-none transition-colors",
                config.container,
                className
            )} 
            {...props}
        >
            {icon ? (
                // If icon is provided, wrap it and ensure it has consistent sizing if not explicitly sized
                <span className="relative flex items-center justify-center shrink-0">
                    {icon}
                </span>
            ) : (
                // Default dot implementation
                <span className="relative flex h-2 w-2 shrink-0">
                    {effectivePulse !== 'none' && (
                        <span className={cn(
                            "absolute inline-flex h-full w-full rounded-full opacity-75",
                            animationClass,
                            config.dot
                        )}></span>
                    )}
                    <span className={cn(
                        "relative inline-flex rounded-full h-2 w-2",
                        config.dot
                    )}></span>
                </span>
            )}
            <span className="uppercase">{children}</span>
        </span>
    );
};
