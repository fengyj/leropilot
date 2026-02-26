import React, { useEffect, useRef } from 'react';
import { cn } from '../../utils/cn';

export interface MotorGaugeProps {
    /** Current speed in rad/s */
    speed: number;
    /** Current mechanical angle in radians */
    angle: number;
    /** Safe speed limit in rad/s — arc is drawn symmetrically from -safeSpeed to +safeSpeed */
    rangeMax?: number;
    /** Max physical limit for the gauge scale (RPM) - used for scale calculation (default 120) */
    limitMax?: number;
    /** Offset for the angle zero point (radians) */
    zeroOffset?: number;
    /** Exponent for non-linear scaling (default 0.6) */
    nonLinearExp?: number;
    /** Damping factor for needle animation (default 0.1) */
    damping?: number;
    /** Size of the gauge in pixels */
    size?: number;
    /** Minimum physical limit angle in radians */
    limitAngleMin?: number;
    /** Maximum physical limit angle in radians */
    limitAngleMax?: number;
    /** Explicitly force mini mode style */
    mini?: boolean;
    className?: string;
}

export function MotorGauge({
    speed,
    angle,
    rangeMax,
    limitMax = 120,
    zeroOffset = 0,
    nonLinearExp = 0.6,
    damping = 0.1,
    size = 200,
    limitAngleMin,
    limitAngleMax,
    mini,
    className
}: MotorGaugeProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Constants for unit conversion
    const RPM_TO_RAD_S = (2 * Math.PI) / 60;
    const RAD_S_TO_RPM = 60 / (2 * Math.PI);

    // Internally convert limitMax (RPM) to rad/s for coordinate mapping
    const limitMaxRadS = limitMax * RPM_TO_RAD_S;

    // Store current displayed value for damping (in rad/s)
    const currentSpeedRef = useRef<number>(speed);


    // CSS variable values cache
    const stylesRef = useRef({
        bgTrack: '#1e293b',
        safeRange: '#3b82f6',
        warning: '#ef4444',
        needle: '#ef4444',
        markerStatic: '#94a3b8',
        markerDynamic: '#ffffff',
        textPrimary: '#f8fafc',
        textSecondary: '#94a3b8',
    });

    // Safe speed arc is always symmetric: -rMax to +rMax.
    // Default to 80% of limitMax if not provided.
    const rMax = rangeMax !== undefined ? rangeMax : limitMaxRadS * 0.8;
    const rMin = -rMax;

    // Helper: Update styles from CSS variables
    const updateStyles = () => {
        if (!canvasRef.current) return;
        const styles = getComputedStyle(canvasRef.current);
        stylesRef.current = {
            bgTrack: styles.getPropertyValue('--motor-gauge-bg-track').trim() || '#1e293b',
            safeRange: styles.getPropertyValue('--motor-gauge-safe-range').trim() || '#3b82f6',
            warning: styles.getPropertyValue('--motor-gauge-warning').trim() || '#ef4444',
            needle: styles.getPropertyValue('--motor-gauge-needle').trim() || '#ef4444',
            markerStatic: styles.getPropertyValue('--motor-gauge-marker-static').trim() || '#94a3b8',
            markerDynamic: styles.getPropertyValue('--motor-gauge-marker-dynamic').trim() || '#ffffff',
            textPrimary: styles.getPropertyValue('--motor-gauge-text-primary').trim() || '#f8fafc',
            textSecondary: styles.getPropertyValue('--motor-gauge-text-secondary').trim() || '#94a3b8',
        };
    };

    /**
     * Non-linear mapping from Value (RPM) to Angle (Radians)
     * Maps [-limitMax, limitMax] to a certain arc range.
     * 12 o'clock is 0 RPM.
     * CW is positive RPM, CCW is negative RPM.
     */
    const valueToAngle = (val: number, maxVal: number, exponent: number): number => {
        // Clamp value
        const clampedVal = Math.max(-maxVal, Math.min(maxVal, val));

        // Normalize 0..1 based on absolute value
        const absNorm = Math.pow(Math.abs(clampedVal) / maxVal, exponent);

        // Map to angle. Let's say max range covers +/- 135 degrees (Total 270 deg span)
        // 0 deg is North ( -PI/2 in canvas arc if 0 is East)
        // We want North = 0 RPM.
        // Canvas: 0 is East (3 o'clock). North is -PI/2.

        const MAX_ANGLE_OFFSET = Math.PI * 0.75; // 135 degrees in radians

        const deflection = absNorm * MAX_ANGLE_OFFSET * Math.sign(clampedVal);

        // Base angle is North (-PI/2)
        return -Math.PI / 2 + deflection;
    };

    const draw = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const width = size;
        const height = size;

        // Handle High DPI
        if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
            canvas.width = width * dpr;
            canvas.height = height * dpr;
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
            // Re-read styles when size changes/init
            updateStyles();
        }

        ctx.resetTransform();
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, width, height);

        const cx = width / 2;
        const cy = height / 2;
        const radius = Math.min(width, height) / 2 - 8; // Padding

        // Determine LOD
        const isMini = mini ?? size <= 120;

        // --- Layer 1: Range Ring / Tracks ---
        // Mini mode has slightly thicker track relative to size for visual weight
        const trackWidth = isMini ? radius * 0.22 : 8;
        const trackRadius = isMini ? radius * 0.85 : radius - 15;

        // Max range angles
        const angleStart = valueToAngle(-limitMaxRadS, limitMaxRadS, nonLinearExp);
        const angleEnd = valueToAngle(limitMaxRadS, limitMaxRadS, nonLinearExp);

        // Draw full track
        ctx.beginPath();
        ctx.arc(cx, cy, trackRadius, angleStart, angleEnd);
        ctx.strokeStyle = stylesRef.current.bgTrack;
        ctx.lineWidth = trackWidth;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Draw active safe range
        const safeStart = valueToAngle(rMin, limitMaxRadS, nonLinearExp);
        const safeEnd = valueToAngle(rMax, limitMaxRadS, nonLinearExp);

        ctx.beginPath();
        ctx.arc(cx, cy, trackRadius, safeStart, safeEnd);
        ctx.strokeStyle = stylesRef.current.safeRange;
        ctx.lineWidth = trackWidth;
        ctx.lineCap = 'butt'; // clean cut for range
        ctx.stroke();


        // --- Layer 2: Scale (Ticks & Labels) ---
        if (!isMini) {
            ctx.fillStyle = stylesRef.current.textSecondary;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.font = '10px Inter, sans-serif';

            const steps = 6; // Use 6 steps for 0, 500, 1000, 1500, 2000, 2500, 3000


            for (let i = 0; i <= steps; i++) {
                const val = (limitMaxRadS / steps) * i;

                [val, -val].forEach(v => {
                    if (v === 0 && i !== 0) return; // Skip duplicate 0

                    const a = valueToAngle(v, limitMaxRadS, nonLinearExp);
                    const tickInner = trackRadius - 8;
                    const tickOuter = trackRadius - 2;

                    // Tick
                    ctx.beginPath();
                    ctx.moveTo(cx + Math.cos(a) * tickInner, cy + Math.sin(a) * tickInner);
                    ctx.lineTo(cx + Math.cos(a) * tickOuter, cy + Math.sin(a) * tickOuter);
                    ctx.strokeStyle = stylesRef.current.markerStatic; // Ticks use text-secondary
                    ctx.lineWidth = 1.5;
                    ctx.stroke();

                    // Label (Still show in RPM for display)
                    const vInRPM = Math.abs(v * RAD_S_TO_RPM);
                    const labelValuesRPM = [0, limitMax, Math.round(limitMax / 3)];

                    if (labelValuesRPM.some(lv => Math.abs(lv - vInRPM) < 1)) {
                        const labelRadius = tickInner - 12;
                        const lx = cx + Math.cos(a) * labelRadius;
                        const ly = cy + Math.sin(a) * labelRadius;
                        ctx.fillText(Math.round(vInRPM).toString(), lx, ly);
                    }
                });
            }
        }

        // --- Layer 3: Position Markers (Outer Circle, Ticks, Limits) ---
        // Mini Mode: Simple casing concentric circles, no ticks
        if (isMini) {
            ctx.strokeStyle = stylesRef.current.bgTrack;
            ctx.lineWidth = 1;

            ctx.beginPath();
            ctx.arc(cx, cy, trackRadius - trackWidth / 2, 0, Math.PI * 2);
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(cx, cy, trackRadius + trackWidth / 2, 0, Math.PI * 2);
            ctx.stroke();
        } else {
            // Large Mode: Outer Circle and 12 clock-like ticks
            const posRingRadius = radius;
            ctx.beginPath();
            ctx.arc(cx, cy, posRingRadius, 0, Math.PI * 2);
            ctx.strokeStyle = stylesRef.current.bgTrack;
            ctx.lineWidth = 1;
            ctx.stroke();

            // 12 ticks
            for (let i = 0; i < 12; i++) {
                const a = (-Math.PI / 2) + (i * Math.PI) / 6;
                const isCardinal = i % 3 === 0;
                const tickLen = isCardinal ? 6 : 3;
                const pInner = posRingRadius - tickLen;
                const pOuter = posRingRadius;

                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(a) * pInner, cy + Math.sin(a) * pInner);
                ctx.lineTo(cx + Math.cos(a) * pOuter, cy + Math.sin(a) * pOuter);
                ctx.strokeStyle = stylesRef.current.markerStatic;
                ctx.lineWidth = isCardinal ? 2 : 1;
                ctx.stroke();
            }
        }

        // Limit & Zero Markers - Show in both modes
        const posRingRadius = radius; // reuse for large logic
        const targetRingRadius = isMini ? (trackRadius + trackWidth / 2) : posRingRadius;
        const northRad = -Math.PI / 2;

        const limits = [limitAngleMin, limitAngleMax];

        limits.forEach((val) => {
            if (val !== undefined) {
                // ctx.rotate(θ) + draw at (0,-r) → tip at (cx + r·sin(θ), cy - r·cos(θ))
                // This matches the ball's polar position when θ = val directly (no northRad offset needed)
                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(val);
                ctx.beginPath();

                // Triangle: tip on the ring edge, base 7px toward center — fully within canvas
                ctx.moveTo(0, -targetRingRadius);        // tip: exactly at ring edge
                ctx.lineTo(-4, -targetRingRadius + 7);   // left base: 7px inward
                ctx.lineTo(4, -targetRingRadius + 7);    // right base: 7px inward

                ctx.closePath();
                ctx.fillStyle = stylesRef.current.warning;
                ctx.fill();
                ctx.restore();
            }
        });

        // Zero Marker Triangle (Original Mechanical 0)
        ctx.save();
        ctx.translate(cx, cy);
        // Same coordinate system as limit markers: rotate(val) → tip matches ball at angle=val
        // zeroOffset is the calibrated angle of the mechanical zero; negate to point at that position
        ctx.rotate(-zeroOffset);
        ctx.beginPath();
        ctx.moveTo(0, -targetRingRadius);        // tip: exactly at ring edge
        ctx.lineTo(-3, -targetRingRadius + 6);   // left base: 6px inward
        ctx.lineTo(3, -targetRingRadius + 6);    // right base: 6px inward
        ctx.closePath();
        ctx.fillStyle = stylesRef.current.markerStatic;
        ctx.fill();
        ctx.restore();

        // --- Layer 4 & 5: Internal Displays (Text & Needle) ---
        ctx.save();
        ctx.translate(cx, cy);

        // Dynamic Rotor Marker (Bearing Ball)
        let ballRadius, centerRadius;
        if (isMini) {
            // Centered ON the track arc (like a bead)
            ballRadius = 4.5;
            centerRadius = trackRadius;
        } else {
            // Centered in gap between rings
            const innerBound = trackRadius + trackWidth / 2;
            const outerBound = posRingRadius - 0.5;
            const gap = Math.max(4, outerBound - innerBound);
            const ballLineWidth = 1.5;
            ballRadius = Math.max(1, (gap - ballLineWidth - 1) / 2);
            centerRadius = innerBound + (gap / 2);
        }

        // Angle is already calibrated by caller, display directly (now in radians)
        const rotorAngleRad = northRad + angle;
        const markerX = Math.cos(rotorAngleRad) * centerRadius;
        const markerY = Math.sin(rotorAngleRad) * centerRadius;

        ctx.beginPath();
        ctx.arc(markerX, markerY, ballRadius, 0, Math.PI * 2);
        ctx.strokeStyle = stylesRef.current.markerDynamic; // text-secondary
        ctx.lineWidth = 1.5; // matching needle-like precision
        ctx.stroke();

        if (!isMini) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Speed Display
            ctx.font = 'bold 16px Inter, sans-serif';
            ctx.fillStyle = stylesRef.current.textPrimary;
            ctx.fillText(Math.round(currentSpeedRef.current * RAD_S_TO_RPM).toString(), 0, 20);
            ctx.font = '10px Inter, sans-serif';
            ctx.fillStyle = stylesRef.current.textSecondary;
            ctx.fillText('RPM', 0, 32);

            // Angle Display (Rad)
            ctx.font = 'bold 14px Inter, sans-serif';
            ctx.fillStyle = stylesRef.current.textPrimary;
            ctx.fillText(angle.toFixed(2), 0, 52);
            ctx.font = '10px Inter, sans-serif';
            ctx.fillStyle = stylesRef.current.textSecondary;
            ctx.fillText('RAD', 0, 64);
        }

        // Damping / Needle Animation
        const diff = speed - currentSpeedRef.current;
        currentSpeedRef.current += diff * damping;

        const needleAngle = valueToAngle(currentSpeedRef.current, limitMaxRadS, nonLinearExp);
        const needleLen = isMini ? trackRadius : (trackRadius - 5);

        ctx.rotate(needleAngle);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(needleLen, 0);
        ctx.strokeStyle = stylesRef.current.needle;
        ctx.lineWidth = isMini ? 1.5 : 2;
        ctx.lineCap = 'round';
        ctx.stroke();

        ctx.restore(); // pop translate(cx, cy)

        // Center Pivot Dot (Center Pin)
        // Red dot always present to give it a "mechanical" feel
        ctx.beginPath();
        ctx.arc(cx, cy, isMini ? 2.5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = stylesRef.current.needle;
        ctx.fill();

        // Optional: White inner dot for extra "premium" look if large
        if (!isMini) {
            ctx.beginPath();
            ctx.arc(cx, cy, 1.2, 0, Math.PI * 2);
            ctx.fillStyle = '#ffffff';
            ctx.fill();
        }

        ctx.resetTransform();
    };

    useEffect(() => {
        let animationFrameId: number;

        const animate = () => {
            draw();
            animationFrameId = window.requestAnimationFrame(animate);
        };

        // Check if styles need initial update (on mount)
        updateStyles();

        animate();

        return () => {
            window.cancelAnimationFrame(animationFrameId);
        };
    }, [speed, angle, size, limitMax, rangeMax, nonLinearExp, damping, limitAngleMin, limitAngleMax, zeroOffset]);

    // Listen for theme changes to update colors
    useEffect(() => {
        const handleThemeChange = () => {
            updateStyles();
        };

        const observer = new MutationObserver(handleThemeChange);
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class', 'style', 'data-theme'],
        });

        return () => observer.disconnect();
    }, []);
    // Actually, `currentSpeedRef` handles smooth transition, but `draw` uses it.
    // If we only dep on `speed`, `draw` runs once per prop change? 
    // We want continuous animation for damping.
    // So `animate` loop runs constantly.

    return (
        <div
            className={cn("relative inline-block", className)}
            style={{ width: size, height: size } as React.CSSProperties}
        >
            <canvas ref={canvasRef} />
        </div>
    );
}
