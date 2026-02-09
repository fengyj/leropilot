import { useState } from 'react';
import { cn } from '../../utils/cn';
import { MotorGauge, MotorGaugeProps } from './motor-gauge';
import { Button } from './button';
import { Maximize2, Minimize2 } from 'lucide-react';

interface MotorGaugeGroupProps {
    title?: string;
    motors: Record<string, MotorGaugeProps>;
    initialMini?: boolean;
}

export function MotorGaugeGroup({
    title,
    motors,
    initialMini = false
}: MotorGaugeGroupProps) {
    const [isMini, setIsMini] = useState(initialMini);

    return (
        <div className="flex flex-col gap-4 p-4 rounded-lg border border-border-default bg-surface-card text-content-primary backdrop-blur-sm shadow-sm transition-all duration-300">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                {title && (
                    <h3 className="text-lg font-semibold text-content-primary">
                        {title}
                    </h3>
                )}
                <div className={cn(!title && "w-full flex justify-end")}>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsMini(!isMini)}
                        className="text-content-secondary hover:text-content-primary p-2"
                        title={isMini ? "Switch to Standard View" : "Switch to Mini View"}
                    >
                        {isMini ? (
                            <Maximize2 className="w-4 h-4" />
                        ) : (
                            <Minimize2 className="w-4 h-4" />
                        )}
                    </Button>
                </div>
            </div>

            {/* Content - "Float" layout using flex wrap */}
            <div className="flex flex-wrap gap-4 items-start justify-start">
                {Object.entries(motors).map(([label, props]) => (
                    <div key={label} className="flex flex-col items-center gap-2">
                        <MotorGauge
                            {...props}
                            size={isMini ? 80 : 200}
                        />
                        <span className="text-sm font-medium text-content-secondary line-clamp-1 max-w-[80px] text-center">
                            {label}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
