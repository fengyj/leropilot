import * as React from 'react';
import { cn } from '../../utils/cn';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'ghost-danger';
  size?: 'sm' | 'md' | 'lg';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    const variants = {
      primary: 'bg-primary text-primary-content hover:bg-primary-hover shadow-sm active:bg-primary-active',
      secondary:
        'bg-surface-tertiary text-content-primary hover:bg-border-default dark:hover:bg-zinc-700 border border-border-default active:bg-surface-secondary',
      ghost:
        'text-content-secondary hover:text-content-primary hover:bg-surface-tertiary dark:hover:bg-zinc-700 active:bg-surface-secondary/50',
      danger: 'bg-status-danger text-white hover:bg-status-danger-hover shadow-sm active:bg-status-danger-active',
      'ghost-danger':
        'text-content-tertiary hover:text-status-danger hover:bg-status-danger/10 active:bg-status-danger/20 group',
    };

    const sizes = {
      sm: 'h-8 px-3 text-xs',
      md: 'h-10 px-4 text-sm',
      lg: 'h-12 px-6 text-base',
    };

    return (
      <button
        className={cn(
          'inline-flex items-center justify-center rounded-lg font-medium transition-all active:scale-95 focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
          variants[variant],
          sizes[size],
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { Button };
