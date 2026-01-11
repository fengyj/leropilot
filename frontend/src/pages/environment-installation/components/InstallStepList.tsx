import { useTranslation } from 'react-i18next';
import { Loader2, Circle, XCircle } from 'lucide-react';
import { cn } from '../../../utils/cn';
import { InstallStep } from '../types';

interface InstallStepListProps {
    steps: InstallStep[];
}

export const InstallStepList = ({ steps }: InstallStepListProps) => {
    const { t } = useTranslation();

    return (
        <div className="bg-surface-secondary border-border-default overflow-x-auto rounded-lg border p-6">
            {steps.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                    <div className="flex items-center gap-3">
                        <Loader2 className="text-primary h-5 w-5 animate-spin" />
                        <span className="text-content-secondary">
                            {t('wizard.installation.preparingSteps')}
                        </span>
                    </div>
                </div>
            ) : (
                <div className="flex items-center justify-between gap-2">
                    {steps.map((step, index) => {
                        const isPending = step.status === 'pending';
                        const isRunning = step.status === 'running';
                        const isSuccess = step.status === 'success';
                        const isError = step.status === 'error';

                        return (
                            <div key={step.id} className="flex items-center">
                                {/* Step indicator */}
                                <div className="flex flex-col items-center gap-2">
                                    <div
                                        className={cn(
                                            'flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all',
                                            isPending && 'border-border-default bg-surface-primary',
                                            isRunning && 'border-primary bg-primary/10',
                                            isSuccess && 'border-success-icon bg-success-surface',
                                            isError && 'border-error-icon bg-error-surface',
                                        )}
                                    >
                                        {isPending && (
                                            <Circle className="text-content-tertiary h-5 w-5" />
                                        )}
                                        {isRunning && (
                                            <Loader2 className="text-primary h-5 w-5 animate-spin" />
                                        )}
                                        {isSuccess && (
                                            <div className="h-2 w-2 rounded-full bg-success-icon" />
                                        )}
                                        {isError && <XCircle className="text-error-icon h-5 w-5" />}
                                    </div>
                                    <div className="text-center">
                                        <div
                                            className={cn(
                                                'max-w-[120px] truncate text-xs font-medium',
                                                isPending && 'text-content-tertiary',
                                                isRunning && 'text-primary',
                                                isSuccess && 'text-success-icon',
                                                isError && 'text-error-icon',
                                            )}
                                            title={step.name}
                                        >
                                            {step.name}
                                        </div>
                                    </div>
                                </div>

                                {/* Connector line */}
                                {index < steps.length - 1 && (
                                    <div
                                        className={cn(
                                            'mx-2 h-0.5 w-8 flex-shrink-0 transition-all lg:w-16',
                                            isSuccess ? 'bg-success-icon' : 'bg-border-default',
                                        )}
                                    />
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
