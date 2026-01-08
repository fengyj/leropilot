import React from 'react';
import { cn } from '../../utils/cn';

interface PageContainerProps {
    children: React.ReactNode;
    /** Maximum width constraint. Default: none (full width) */
    maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | '6xl' | '7xl' | 'full';
    /** Vertical spacing between children. Default: '6' (1.5rem) */
    spacing?: '4' | '6' | '8';
    /** Add horizontal and vertical padding. Default: false */
    padded?: boolean;
    /** Center the container horizontally. Default: true when maxWidth is set */
    centered?: boolean;
    /** Additional CSS classes */
    className?: string;
}

const maxWidthClasses: Record<NonNullable<PageContainerProps['maxWidth']>, string> = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '3xl': 'max-w-3xl',
    '4xl': 'max-w-4xl',
    '5xl': 'max-w-5xl',
    '6xl': 'max-w-6xl',
    '7xl': 'max-w-7xl',
    full: 'max-w-full',
};

const spacingClasses: Record<NonNullable<PageContainerProps['spacing']>, string> = {
    '4': 'space-y-4',
    '6': 'space-y-6',
    '8': 'space-y-8',
};

/**
 * A consistent page container component for unified layout across pages.
 * Provides configurable max-width, vertical spacing, and optional padding.
 */
export const PageContainer: React.FC<PageContainerProps> = ({
    children,
    maxWidth,
    spacing = '6',
    padded = false,
    centered,
    className,
}) => {
    // Default centered to true when maxWidth is set
    const shouldCenter = centered ?? !!maxWidth;

    return (
        <div
            className={cn(
                'flex flex-col',
                spacingClasses[spacing],
                maxWidth && maxWidthClasses[maxWidth],
                shouldCenter && 'mx-auto',
                padded && 'px-4 py-8',
                className,
            )}
        >
            {children}
        </div>
    );
};
