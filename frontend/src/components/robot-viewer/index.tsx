/**
 * RobotViewer — public-facing component for 3D URDF robot visualisation.
 *
 * The Three.js canvas is lazy-loaded to keep it out of the initial bundle.
 * Provide `telemetry` from an existing WebSocket session to see live joint
 * positions reflected in the 3D model.
 *
 * @example
 * // Observe mode (pass live telemetry from useRobotTelemetry)
 * <RobotViewer robotId="so100-follower" telemetry={telemetry} className="h-[400px]" />
 *
 * // Static preview (no live data)
 * <RobotViewer robotId="so100-follower" className="h-64" />
 */

import { lazy, Suspense } from 'react';
import { Box } from 'lucide-react';
import { cn } from '../../utils/cn';
import type { RobotTelemetryFrame } from '../../types/hardware';

// Heavy Three.js bundle — loaded on demand
const RobotCanvas = lazy(() => import('./robot-canvas'));

// ---------------------------------------------------------------------------
// Public Props
// ---------------------------------------------------------------------------

export interface RobotViewerProps {
  /** Robot ID used to resolve URDF and mesh resources from the backend API. */
  robotId: string;
  /**
   * Live telemetry frame from an existing WebSocket session.
   * When provided, joint positions are synchronised in real-time.
   */
  telemetry?: RobotTelemetryFrame | null;
  /**
   * Additional Tailwind / CSS classes for the container.
   * Use height utilities here (e.g. `h-64`, `h-[400px]`, `min-h-[300px]`).
   * @default "h-[400px]"
   */
  className?: string;
}

// ---------------------------------------------------------------------------
// Loading skeleton shown while the Three.js bundle is being fetched
// ---------------------------------------------------------------------------

function ViewerSkeleton() {
  return (
    <div className="bg-surface-secondary flex h-full w-full animate-pulse flex-col items-center justify-center gap-3 rounded-lg">
      <Box className="text-content-tertiary h-10 w-10 opacity-30" />
      <span className="text-content-tertiary text-xs">Loading 3D viewer…</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RobotViewer
// ---------------------------------------------------------------------------

export function RobotViewer({ robotId, telemetry, className }: RobotViewerProps) {
  return (
    <div className={cn('relative h-[400px] w-full', className)}>
      <Suspense fallback={<ViewerSkeleton />}>
        <RobotCanvas robotId={robotId} telemetry={telemetry} />
      </Suspense>
    </div>
  );
}
