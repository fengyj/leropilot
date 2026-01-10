import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { EmptyState } from '../../components/ui/empty-state';
import { PageContainer } from '../../components/ui/page-container';
import { LoadingOverlay } from '../../components/ui/loading-overlay';
import { Environment } from './types';
import { EnvironmentCard } from './components/EnvironmentCard';

export function EnvironmentListPage() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleteConfirm, setDeleteConfirm] = useState<{
        isOpen: boolean;
        envId: string | null;
        envName: string | null;
    }>({
        isOpen: false,
        envId: null,
        envName: null,
    });
    const [openingTerminal, setOpeningTerminal] = useState<string | null>(null);
    const [errorDialog, setErrorDialog] = useState<{ isOpen: boolean; message: string }>(
        { isOpen: false, message: '' },
    );

    useEffect(() => {
        const abortController = new AbortController();

        const fetchEnvironments = async () => {
            try {
                const response = await fetch('/api/environments', {
                    signal: abortController.signal,
                });
                if (response.ok) {
                    const data = await response.json();
                    // Sort by display_name alphabetically
                    data.sort((a: Environment, b: Environment) =>
                        a.display_name.localeCompare(b.display_name),
                    );
                    setEnvironments(data);
                }
            } catch (error) {
                // Ignore AbortError - this is expected when component unmounts
                if (error instanceof Error && error.name === 'AbortError') {
                    return;
                }
                console.error('Failed to fetch environments:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchEnvironments();

        return () => {
            abortController.abort();
        };
    }, []);

    const handleDeleteClick = (envId: string, envName: string) => {
        setDeleteConfirm({
            isOpen: true,
            envId,
            envName,
        });
    };

    const handleDeleteConfirm = async () => {
        if (!deleteConfirm.envId) return;

        try {
            const response = await fetch(`/api/environments/${deleteConfirm.envId}`, {
                method: 'DELETE',
            });

            if (response.ok) {
                // Remove the deleted environment from the list
                setEnvironments((prev) => prev.filter((env) => env.id !== deleteConfirm.envId));
                setDeleteConfirm({ isOpen: false, envId: null, envName: null });
            } else {
                console.error('Failed to delete environment:', response.statusText);
            }
        } catch (error) {
            console.error('Error deleting environment:', error);
        }
    };

    const handleDeleteCancel = () => {
        setDeleteConfirm({ isOpen: false, envId: null, envName: null });
    };

    const handleOpenTerminal = async (envId: string) => {
        setOpeningTerminal(envId);
        try {
            const response = await fetch(`/api/environments/${envId}/open-terminal`, {
                method: 'POST',
            });

            if (response.ok) {
                // Success - terminal opened
                console.log(t('environments.terminalOpenSuccess'));
            } else {
                const error = await response.json();
                console.error(t('environments.terminalOpenError'), error.detail);
                setErrorDialog({ isOpen: true, message: `${t('environments.terminalOpenError')}: ${error.detail || t('common.unknownError')}` });
            }
        } catch (error) {
            console.error('Error opening terminal:', error);
            setErrorDialog({ isOpen: true, message: t('environments.terminalOpenError') });
        } finally {
            setOpeningTerminal(null);
        }
    };

    if (loading) {
        return (
            <PageContainer>
                <div className="relative flex h-[calc(100vh-theme(spacing.32))] w-full items-center justify-center">
                    <LoadingOverlay message={t('environments.loading')} size="lg" fancy className="rounded-lg" />
                </div>
            </PageContainer>
        );
    }

    return (
        <PageContainer>
            <ConfirmDialog
                isOpen={deleteConfirm.isOpen}
                title={t('environments.deleteConfirmTitle')}
                message={t('environments.deleteConfirmMessage')}
                confirmText={t('common.delete')}
                cancelText={t('common.cancel')}
                variant="danger"
                onConfirm={handleDeleteConfirm}
                onCancel={handleDeleteCancel}
            />

            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-content-primary text-2xl font-bold tracking-tight">
                        {t('environments.title')}
                    </h1>
                    <p className="text-content-secondary">{t('environments.subtitle')}</p>
                </div>
                <Button onClick={() => navigate('/environments/new')}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t('environments.createNew')}
                </Button>
            </div>

            {environments.length === 0 ? (
                <EmptyState
                    icon={<Plus className="h-10 w-10" />}
                    message={t('environments.noEnvironments')}
                    size="lg"
                    action={{
                        label: t('environments.createNew'),
                        icon: <Plus className="mr-2 h-4 w-4" />,
                        onClick: () => navigate('/environments/new'),
                    }}
                />
            ) : (
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                    {environments.map((env) => (
                        <EnvironmentCard
                            key={env.id}
                            env={env}
                            openingTerminal={openingTerminal}
                            onOpenTerminal={handleOpenTerminal}
                            onDelete={handleDeleteClick}
                        />
                    ))}
                </div>
            )}

            {/* Error dialog for terminal open failures */}
            <ConfirmDialog
                isOpen={errorDialog.isOpen}
                title={t('environments.terminalOpenError')}
                message={errorDialog.message}
                confirmText={t('common.ok')}
                onConfirm={() => setErrorDialog({ isOpen: false, message: '' })}
                onCancel={() => setErrorDialog({ isOpen: false, message: '' })}
            />
        </PageContainer>
    );
}
