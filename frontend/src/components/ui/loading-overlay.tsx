import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

interface LoadingOverlayProps {
    /** Primary message to display */
    message: string;
    /** Optional secondary/subtitle message */
    subtitle?: string;
    /** Size variant affecting spinner and text sizes */
    size?: 'sm' | 'md' | 'lg';
    /** Whether to show the fancy dual-ring animation */
    fancy?: boolean;
    /** Additional CSS classes for the container */
    className?: string;
}

const sizeConfig = {
    sm: {
        outer: 'h-8 w-8',
        inner: 'h-5 w-5',
        spinner: 'h-3 w-3',
        message: 'text-xs',
        subtitle: 'text-[9px]',
        gap: 'gap-2',
    },
    md: {
        outer: 'h-12 w-12',
        inner: 'h-8 w-8',
        spinner: 'h-5 w-5',
        message: 'text-sm',
        subtitle: 'text-[10px]',
        gap: 'gap-4',
    },
    lg: {
        outer: 'h-16 w-16',
        inner: 'h-10 w-10',
        spinner: 'h-6 w-6',
        message: 'text-base',
        subtitle: 'text-xs',
        gap: 'gap-5',
    },
};

/**
 * A reusable loading overlay component with customizable appearance.
 * Can be used as a full-screen overlay or within a container.
 */
export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
    message,
    subtitle,
    size = 'md',
    fancy = true,
    className,
}) => {
    const config = sizeConfig[size];

    return (
        <div
            className={cn(
                'absolute inset-0 z-20 flex flex-col items-center justify-center',
                'bg-surface-primary/40 backdrop-blur-[2px] rounded-xl transition-all duration-500',
                className,
            )}
        >
            <div className={cn('flex flex-col items-center', config.gap)}>
                {fancy ? (
                    <div className="relative flex items-center justify-center">
                        {/* Outer spinning ring */}
                        <div
                            className={cn(
                                'absolute rounded-full border-t-2 border-l-2 border-primary animate-spin',
                                config.outer,
                            )}
                        />
                        {/* Inner pulsing circle */}
                        <div
                            className={cn(
                                'rounded-full bg-primary/20 animate-pulse flex items-center justify-center',
                                config.inner,
                            )}
                        >
                            <Loader2 className={cn('animate-spin text-primary', config.spinner)} />
                        </div>
                    </div>
                ) : (
                    <Loader2 className={cn('animate-spin text-content-tertiary', config.spinner)} />
                )}
                <div className="flex flex-col items-center gap-1">
                    <span
                        className={cn(
                            'font-semibold text-content-primary tracking-wide',
                            config.message,
                        )}
                    >
                        {message}
                    </span>
                    {subtitle && (
                        <span
                            className={cn(
                                'text-content-tertiary uppercase tracking-widest animate-pulse',
                                config.subtitle,
                            )}
                        >
                            {subtitle}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
};
