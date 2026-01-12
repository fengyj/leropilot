import React, { useState } from 'react';
import { Camera } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { CameraSummary } from '../../../types/hardware';

export const CameraPreview: React.FC<{ camera: CameraSummary }> = ({ camera }) => {
    const [error, setError] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const { t } = useTranslation();

    return (
        <div className="flex flex-col items-center justify-center p-6 bg-black min-h-[400px] relative">
            {!error ? (
                <div className="relative group w-full flex justify-center">
                    {isLoading && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black z-10">
                            <div className="relative flex items-center justify-center mb-4">
                                <div className="absolute h-16 w-16 rounded-full border-t-2 border-primary animate-spin" />
                                <Camera className="h-8 w-8 text-primary/40 animate-pulse" />
                            </div>
                            <p className="text-sm text-content-tertiary animate-pulse tracking-wide">
                                {t('hardware.cameraPreview.establishing')}
                            </p>
                        </div>
                    )}
                    <img
                        src={`/api/hardware/cameras/${camera.index}/mjpeg?t=${Date.now()}`}
                        alt="Camera Preview"
                        className={`w-full h-auto max-h-[70vh] object-contain rounded shadow-2xl border border-white/5 transition-opacity duration-700 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
                        onLoad={() => setIsLoading(false)}
                        onError={() => {
                            setError(true);
                            setIsLoading(false);
                        }}
                    />
                    {!isLoading && (
                        <div className="absolute top-2 right-2 px-2 py-1 bg-black/50 backdrop-blur-md rounded text-[10px] text-white opacity-0 group-hover:opacity-100 transition-opacity">
                            {t('hardware.cameraPreview.live')} • {camera.width}x{camera.height}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col items-center gap-4 py-20 text-content-tertiary">
                    <Camera className="h-16 w-16 opacity-20" />
                    <p>{t('hardware.cameraCard.failedToConnect')}</p>
                </div>
            )}
        </div>
    );
};
