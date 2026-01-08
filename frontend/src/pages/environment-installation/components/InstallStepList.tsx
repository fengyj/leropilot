import { useTranslation } from 'react-i18next';
import { Loader2, Circle, CheckCircle2, XCircle } from 'lucide-react';
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
                        <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
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
                                            isRunning && 'border-blue-600 bg-blue-50 dark:bg-blue-950',
                                            isSuccess && 'border-green-600 bg-green-50 dark:bg-green-950',
                                            isError && 'border-red-600 bg-red-50 dark:bg-red-950',
                                        )}
                                    >
                                        {isPending && (
                                            <Circle className="text-content-tertiary h-5 w-5" />
                                        )}
                                        {isRunning && (
                                            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                                        )}
                                        {isSuccess && (
                                            <CheckCircle2 className="text-success-icon h-5 w-5" />
                                        )}
                                        {isError && <XCircle className="text-error-icon h-5 w-5" />}
                                    </div>
                                    <div className="text-center">
                                        <div
                                            className={cn(
                                                'max-w-[120px] truncate text-xs font-medium',
                                                isPending && 'text-content-tertiary',
                                                isRunning && 'text-blue-600',
                                                isSuccess && 'text-green-600',
                                                isError && 'text-red-600',
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
                                            isSuccess ? 'bg-green-600' : 'bg-border-default',
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
