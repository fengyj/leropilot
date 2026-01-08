import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Plus,
    Bot,
    Camera,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Modal } from '../../components/ui/modal';
import { AddRobotModal } from '../../components/add-robot-modal';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { EmptyState } from '../../components/ui/empty-state';
import { PageContainer } from '../../components/ui/page-container';
import { Robot, CameraSummary } from '../../types/hardware';

import { RobotCard } from './components/RobotCard';
import { CameraCard } from './components/CameraCard';
import { CameraPreview } from './components/CameraPreview';
import { LoadingSkeleton } from './components/LoadingSkeleton';

export function HardwareDashboard() {
    const { t } = useTranslation();
    const [robots, setRobots] = useState<Robot[]>([]);
    const [cameras, setCameras] = useState<CameraSummary[]>([]);
    const [loadingRobots, setLoadingRobots] = useState(true);
    const [loadingCameras, setLoadingCameras] = useState(true);
    const [refreshing, setRefreshing] = useState<string | null>(null); // robot id
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

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-content-primary text-2xl font-bold tracking-tight">
                        {t('nav.devices')}
                    </h1>
                    <p className="text-content-secondary">
                        管理您连接的机器人、手臂、相机及其他辅助硬件。
                    </p>
                </div>
                <div>
                    <Button onClick={() => setIsAddRobotOpen(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        添加机器人
                    </Button>
                </div>
            </div>

            {/* Robots Group */}
            <section className="space-y-4">
                <div className="flex items-center gap-2">
                    <Bot className="h-5 w-5 text-primary" />
                    <h2 className="text-lg font-semibold text-content-primary">
                        Robots & Arms
                    </h2>
                    <span className="ml-2 rounded-full bg-surface-secondary px-2.5 py-0.5 text-xs font-medium text-content-secondary border border-border-default">
                        {robots.length}
                    </span>
                </div>

                <div className="min-h-[200px]">
                    {robots.length > 0 ? (
                        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                            {robots.map((robot) => (
                                <RobotCard
                                    key={robot.id}
                                    robot={robot}
                                    isRefreshing={refreshing === robot.id || refreshing === 'all'}
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
                                label: '添加机器人',
                                icon: <Plus className="mr-2 h-4 w-4" />,
                                onClick: () => setIsAddRobotOpen(true),
                            }}
                        />
                    ) : (
                        <LoadingSkeleton />
                    )}
                </div>
            </section>

            {/* Cameras Group */}
            <section className="space-y-4 pt-4 border-t border-border-default">
                <div className="flex items-center gap-2">
                    <Camera className="h-5 w-5 text-primary" />
                    <h2 className="text-lg font-semibold text-content-primary">
                        Cameras
                    </h2>
                    <span className="ml-2 rounded-full bg-surface-secondary px-2.5 py-0.5 text-xs font-medium text-content-secondary border border-border-default">
                        {cameras.length}
                    </span>
                </div>

                <div className="min-h-[200px]">
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
                    ) : (
                        <LoadingSkeleton />
                    )}
                </div>
            </section>

            {/* Camera Preview Modal */}
            <Modal
                isOpen={!!previewCamera}
                onClose={() => setPreviewCamera(null)}
                title={previewCamera ? `Preview: ${previewCamera.name}` : ''}
                className="max-w-4xl border-zinc-700 shadow-2xl ring-1 ring-white/10"
            >
                {previewCamera && (
                    <div className="flex flex-col">
                        <CameraPreview camera={previewCamera} />
                        <div className="p-4 bg-surface-secondary border-t border-border-subtle flex justify-end items-center gap-4">
                            <div className="mr-auto text-xs text-content-tertiary">
                                {previewCamera.available ? '● Streaming' : '○ Offline'}
                            </div>
                            <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => setPreviewCamera(null)}
                                className="px-6"
                            >
                                关闭 (Close)
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
