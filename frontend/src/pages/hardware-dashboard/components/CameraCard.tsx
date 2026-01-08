import React from 'react';
import { Monitor, Loader2 } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from '../../../components/ui/card';
import { CameraSummary, DeviceStatus } from '../../../types/hardware';
import { StatusIcon } from './StatusIcon';

export const CameraCard: React.FC<{
    camera: CameraSummary;
    isRefreshing?: boolean;
    onPreview: (camera: CameraSummary) => void;
}> = ({ camera, isRefreshing, onPreview }) => {
    const resolution = camera.width && camera.height
        ? `${camera.width} x ${camera.height}`
        : '未知';

    return (
        <Card className={`flex flex-col h-full relative overflow-hidden transition-all duration-300 ${isRefreshing ? 'scale-[0.98] opacity-60' : 'hover:shadow-md'}`}>
            {isRefreshing && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-primary/60 backdrop-blur-[1px]">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
            )}
            <CardHeader>
                <div className="flex items-start justify-between">
                    <div className="flex items-start min-w-0">
                        <div className="min-w-0">
                            <CardTitle className="text-lg leading-tight break-words" title={camera.name}>
                                {camera.name}
                            </CardTitle>
                            <div className="text-content-secondary text-xs mt-1">
                                OpenCV Index: {camera.index}
                            </div>
                        </div>
                    </div>
                    <div className="shrink-0 ml-2">
                        <StatusIcon status={(camera.available ? 'available' : 'offline') as DeviceStatus} />
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-4">
                <div className="space-y-1">
                    <p className="text-content-tertiary text-xs">分辨率</p>
                    <p className="text-content-primary text-sm font-medium">
                        {resolution}
                    </p>
                </div>
            </CardContent>
            <CardFooter className="border-border-default flex items-center justify-between border-t p-4">
                <div className="flex gap-2 w-full">
                    <Button
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                        disabled={!camera.available}
                        onClick={() => onPreview(camera)}
                    >
                        <Monitor className="mr-2 h-3 w-3" />
                        Preview
                    </Button>
                </div>
            </CardFooter>
        </Card>
    );
};
