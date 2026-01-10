
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Loader2, XCircle } from 'lucide-react';
import WebTerminal from '../../components/web-terminal';
import { Button } from '../../components/ui/button';
import { PageContainer } from '../../components/ui/page-container';
import { useWizardStore } from '../../stores/environment-wizard-store';
import { useInstallation } from './hooks/useInstallation';
import { InstallationHeader } from './components/InstallationHeader';
import { InstallStepList } from './components/InstallStepList';

export function EnvironmentInstallationPage() {
    const { envId } = useParams<{ envId: string }>();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { reset: resetWizard } = useWizardStore();

    const {
        ptySessionId,
        envName,
        steps,
        installState,
        error,
        handleShellEvent,
    } = useInstallation(envId);

    const handleBackToList = () => {
        // Reset wizard state before navigating back
        resetWizard();
        navigate('/environments');
    };

    const handleRetry = () => {
        window.location.reload();
    };

    const runningStep = steps.find((s) => s.status === 'running');

    return (
        <PageContainer maxWidth="6xl" padded>
            <InstallationHeader
                pageTitle={t('wizard.installation.pageTitle')}
                pageSubtitle={t('wizard.installation.pageSubtitle', { envName: envName || envId })}
            />

            <InstallStepList steps={steps} />

            {/* Terminal Output */}
            <div className="bg-surface-secondary border-border-default overflow-hidden rounded-lg border">
                <div className="border-border-default bg-surface-secondary/50 flex items-center justify-between border-b px-4 py-3">
                    <div className="flex items-center gap-2">
                        <div className="flex gap-1.5">
                            <div className="bg-error-icon h-3 w-3 rounded-full" />
                            <div className="bg-warning-icon h-3 w-3 rounded-full" />
                            <div className="bg-success-icon h-3 w-3 rounded-full" />
                        </div>
                        <span className="text-content-primary ml-2 text-sm font-medium">
                            {t('wizard.installation.terminal')}
                        </span>
                    </div>
                    <div className="flex items-center gap-4">
                        {runningStep && (
                            <span className="text-content-secondary text-xs">
                                {t('wizard.installation.runningStep', { stepName: runningStep.name })}
                            </span>
                        )}
                        {installState.status === 'running' && (
                            <span className="flex items-center gap-1.5 text-xs text-success-icon">
                                <span className="h-2 w-2 rounded-full bg-success-icon" />
                                {t('wizard.installation.running')}
                            </span>
                        )}
                    </div>
                </div>
                <div className="bg-surface-primary h-[500px] w-full">
                    {ptySessionId ? (
                        <WebTerminal
                            sessionId={ptySessionId}
                            apiHost={import.meta.env.VITE_API_BASE_URL || undefined}
                            onShellEvent={handleShellEvent}
                            onConnected={() => {
                                console.log('[Installation] WebTerminal connected');
                            }}
                        />
                    ) : (
                        <div className="flex h-full items-center justify-center">
                            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                        </div>
                    )}
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div className="border-t border-error-border bg-error-surface px-6 py-4">
                    <div className="flex items-start gap-3">
                        <XCircle className="h-5 w-5 flex-shrink-0 text-error-icon" />
                        <div className="flex-1">
                            <h3 className="font-medium text-error-content">
                                {t('wizard.installation.errorTitle')}
                            </h3>
                            <p className="mt-1 text-sm text-error-content/90">{error}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Footer Actions */}
            <div className="border-border-default flex justify-end gap-3 border-t p-6">
                {installState.status === 'success' ? (
                    <Button
                        onClick={handleBackToList}
                        className="bg-success-surface text-success-content hover:bg-success-surface/90"
                    >
                        {t('wizard.installation.done')}
                    </Button>
                ) : installState.status === 'failed' ? (
                    <>
                        <Button variant="secondary" onClick={handleBackToList}>
                            {t('wizard.installation.cancel')}
                        </Button>
                        <Button variant="danger" onClick={handleRetry}>
                            {t('wizard.installation.retry')}
                        </Button>
                    </>
                ) : (
                    <Button variant="secondary" disabled>
                        {t('wizard.installation.installing')}
                    </Button>
                )}
            </div>
        </PageContainer>
    );
}
