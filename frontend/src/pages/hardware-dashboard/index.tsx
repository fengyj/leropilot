import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Plus,
    Bot,
    Camera,
    RefreshCw,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Modal } from '../../components/ui/modal';
import { AddRobotModal } from './components/add-robot-modal';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { EmptyState } from '../../components/ui/empty-state';
import { PageContainer } from '../../components/ui/page-container';
import { Robot, CameraSummary } from '../../types/hardware';
import { LoadingOverlay } from '../../components/ui/loading-overlay';

import { RobotCard } from './components/RobotCard';
import { CameraCard } from './components/CameraCard';
import { CameraPreview } from './components/CameraPreview';

export function HardwareDashboard() {
    const { t } = useTranslation();
    const [robots, setRobots] = useState<Robot[]>([]);
    const [cameras, setCameras] = useState<CameraSummary[]>([]);
    const [loadingRobots, setLoadingRobots] = useState(true);
    const [loadingCameras, setLoadingCameras] = useState(true);
    const [refreshing, setRefreshing] = useState<string | null>(null); // robot id or 'all'
    const [refreshingCameras, setRefreshingCameras] = useState(false);
    const [previewCamera, setPreviewCamera] = useState<CameraSummary | null>(null);
    const [isAddRobotOpen, setIsAddRobotOpen] = useState(false);
    const [deleteConfirm, setDeleteConfirm] = useState<{
        isOpen: boolean;
        robotId: string | null;
        robotName: string | null;
    }>({
        isOpen: false,
        robotId: null,
        robotName: null,
    });

    const fetchRobots = async (refreshStatus = false) => {
        try {
            const url = refreshStatus
                ? '/api/hardware/robots?refresh_status=true'
                : '/api/hardware/robots';
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                setRobots(data);
            }
        } catch (error) {
            console.error('Failed to fetch robots:', error);
        } finally {
            setLoadingRobots(false);
        }
    };

    const handleRefreshAllRobots = async () => {
        try {
            setRefreshing('all');
            await fetch('/api/hardware/robots?refresh_status=true');
            await fetchRobots();
        } catch (error) {
            console.error('Failed to refresh robots:', error);
        } finally {
            setRefreshing(null);
        }
    };

    const fetchCameras = async () => {
        try {
            const response = await fetch('/api/hardware/cameras');
            if (response.ok) {
                setCameras(await response.json());
            }
        } catch (error) {
            console.error('Failed to fetch cameras:', error);
        } finally {
            setLoadingCameras(false);
        }
    };

    const handleRefreshAllCameras = async () => {
        try {
            setRefreshingCameras(true);
            await fetchCameras();
        } catch (error) {
            console.error('Failed to refresh cameras:', error);
        } finally {
            setRefreshingCameras(false);
        }
    };

    const handleRefreshRobot = async (id: string) => {
        setRefreshing(id);
        try {
            const response = await fetch(`/api/hardware/robots/${id}?refresh_status=true`);
            if (response.ok) {
                const updatedRobot = await response.json();
                setRobots(prev => prev.map(r => r.id === id ? updatedRobot : r));
            }
        } catch (error) {
            console.error('Failed to refresh robot:', error);
        } finally {
            setRefreshing(null);
        }
    };

    const handleDeleteRobot = (id: string, name: string) => {
        setDeleteConfirm({
            isOpen: true,
            robotId: id,
            robotName: name,
        });
    };

    const handleDeleteConfirm = async () => {
        if (!deleteConfirm.robotId) return;

        try {
            const response = await fetch(`/api/hardware/robots/${deleteConfirm.robotId}`, {
                method: 'DELETE',
            });

            if (response.ok) {
                setRobots(prev => prev.filter(r => r.id !== deleteConfirm.robotId));
                setDeleteConfirm({ isOpen: false, robotId: null, robotName: null });
            } else {
                console.error('Failed to delete robot:', response.statusText);
            }
        } catch (error) {
            console.error('Error deleting robot:', error);
        }
    };

    const handleDeleteCancel = () => {
        setDeleteConfirm({ isOpen: false, robotId: null, robotName: null });
    };

    useEffect(() => {
        fetchRobots(true);
        fetchCameras();
    }, []);

    return (
        <PageContainer>
            <ConfirmDialog
                isOpen={deleteConfirm.isOpen}
                title={t('hardware.deleteConfirmTitle')}
                message={t('hardware.deleteConfirmMessage')}
                confirmText={t('common.delete')}
                cancelText={t('common.cancel')}
                variant="danger"
                onConfirm={handleDeleteConfirm}
                onCancel={handleDeleteCancel}
            />

            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-content-primary text-2xl font-bold tracking-tight">
                        {t('hardware.dashboard.title')}
                    </h1>
                    <p className="text-content-secondary">
                        {t('hardware.dashboard.subtitle')}
                    </p>
                </div>
            </div>

            {/* Robots Group */}
            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Bot className="h-5 w-5 text-primary" />
                        <h2 className="text-lg font-semibold text-content-primary">
                            {t('hardware.dashboard.robotsTitle')}
                        </h2>
                        <span className="ml-2 rounded-full bg-surface-secondary px-2.5 py-0.5 text-xs font-medium text-content-secondary border border-border-default">
                            {robots.length}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={() => setIsAddRobotOpen(true)}
                            className={`h-10 px-4 py-2 ${loadingRobots || refreshing === 'all' ? 'opacity-60 cursor-not-allowed' : ''}`}
                            disabled={loadingRobots || refreshing === 'all'}
                            aria-disabled={loadingRobots || refreshing === 'all'}
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            {t('hardware.dashboard.addRobot')}
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleRefreshAllRobots}
                            disabled={loadingRobots || refreshing === 'all'}
                            className="h-10 w-10 flex items-center justify-center rounded-md hover:bg-surface-secondary/10"
                            title={t('hardware.dashboard.refreshRobots')}
                            aria-label={t('hardware.dashboard.refreshRobots')}
                        >
                            <RefreshCw className={`h-4 w-4 ${refreshing === 'all' ? 'animate-spin' : ''}`} />
                            <span className="sr-only">{t('hardware.dashboard.refreshRobots')}</span>
                        </Button>
                    </div>
                </div>

                <div className="min-h-[200px] relative">
                    {robots.length > 0 ? (
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                            {robots.map((robot) => (
                                <RobotCard
                                    key={robot.id}
                                    robot={robot}
                                    isRefreshing={refreshing === robot.id}
                                    onRefresh={handleRefreshRobot}
                                    onDelete={handleDeleteRobot}
                                />
                            ))}
                        </div>
                    ) : !loadingRobots ? (
                        <EmptyState
                            icon={<Bot className="h-8 w-8" />}
                            message={t('hardware.noRobots')}
                            size="md"
                            action={{
                                label: t('hardware.dashboard.addRobot'),
                                icon: <Plus className="mr-2 h-4 w-4" />,
                                onClick: () => setIsAddRobotOpen(true),
                            }}
                        />
                    ) : null}

                    {/* Group / page-level loading overlay */}
                    {(loadingRobots || refreshing === 'all') && (
                        <LoadingOverlay
                            message={loadingRobots ? t('hardware.dashboard.loadingDevices') : t('hardware.dashboard.refreshing')}
                            subtitle={loadingRobots ? undefined : t('hardware.dashboard.refreshingRobotsStatus')}
                            size="lg"
                            fancy
                            className="rounded-lg"
                        />
                    )}
                </div>
            </section>

            {/* Cameras Group */}
            <section className="space-y-4 pt-4 border-t border-border-default">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Camera className="h-5 w-5 text-primary" />
                        <h2 className="text-lg font-semibold text-content-primary">
                            {t('hardware.dashboard.camerasTitle')}
                        </h2>
                        <span className="ml-2 rounded-full bg-surface-secondary px-2.5 py-0.5 text-xs font-medium text-content-secondary border border-border-default">
                            {cameras.length}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleRefreshAllCameras}
                            disabled={loadingCameras || refreshingCameras}
                            className="h-10 w-10 flex items-center justify-center rounded-md hover:bg-surface-secondary/10 disabled:opacity-60 disabled:cursor-not-allowed"
                            title={t('hardware.dashboard.refreshCameras')}
                            aria-label={t('hardware.dashboard.refreshCameras')}
                        >
                            <RefreshCw className={`h-4 w-4 ${refreshingCameras ? 'animate-spin' : ''}`} />
                            <span className="sr-only">{t('hardware.dashboard.refreshCameras')}</span>
                        </Button>
                    </div>
                </div>

                <div className="min-h-[200px] relative">
                    {cameras.length > 0 ? (
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                            {cameras.map((camera) => (
                                <CameraCard
                                    key={camera.index}
                                    camera={camera}
                                    onPreview={(cam) => setPreviewCamera(cam)}
                                />
                            ))}
                        </div>
                    ) : !loadingCameras ? (
                        <EmptyState
                            icon={<Camera className="h-8 w-8" />}
                            message={t('hardware.noCameras')}
                            size="md"
                        />
                    ) : null}

                    {(loadingCameras || refreshingCameras) && (
                        <LoadingOverlay
                            message={loadingCameras ? t('hardware.dashboard.loadingCameras') : t('hardware.dashboard.refreshing')}
                            subtitle={loadingCameras ? undefined : t('hardware.dashboard.refreshingCamerasStatus')}
                            size="lg"
                            fancy
                            className="rounded-lg"
                        />
                    )}
                </div>
            </section>

            {/* Camera Preview Modal */}
            <Modal
                isOpen={!!previewCamera}
                onClose={() => setPreviewCamera(null)}
                title={previewCamera ? t('hardware.dashboard.previewCameraTitle', { name: previewCamera.name }) : ''}
                className="max-w-4xl border-border-default shadow-2xl ring-1 ring-border-subtle/50"
            >
                {previewCamera && (
                    <div className="flex flex-col">
                        <CameraPreview camera={previewCamera} />
                        <div className="p-4 bg-surface-secondary border-t border-border-subtle flex justify-end items-center gap-4">
                            <div className="mr-auto text-xs text-content-tertiary">
                                {previewCamera.available ? t('hardware.dashboard.streaming') : t('hardware.dashboard.offline')}
                            </div>
                            <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => setPreviewCamera(null)}
                                className="px-6"
                            >
                                {t('common.close')}
                            </Button>
                        </div>
                    </div>
                )}
            </Modal>

            <AddRobotModal
                isOpen={isAddRobotOpen}
                onClose={() => setIsAddRobotOpen(false)}
                onSuccess={() => {
                    setIsAddRobotOpen(false);
                    fetchRobots(true);
                }}
            />
        </PageContainer>
    );
}
