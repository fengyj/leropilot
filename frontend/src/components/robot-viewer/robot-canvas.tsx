/**
 * RobotCanvas — lazily-loaded Three.js canvas that visualises a URDF robot.
 *
 * Loaded as a dynamic import from RobotViewer/index.tsx to keep the heavy
 * Three.js bundle out of the initial chunk.
 */

// @react-three/fiber uses Three.js–specific JSX props (intensity, castShadow,
// args, position, etc.) that are not standard HTML attributes. The rule
// react/no-unknown-property is intentionally disabled for this file.
/* eslint-disable react/no-unknown-property */
import { useRef, useEffect, useState, useCallback } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { ChevronDown, ChevronUp } from 'lucide-react';
import * as THREE from 'three';
import URDFLoader, { URDFRobot } from 'urdf-loader';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import type { RobotTelemetryFrame } from '../../types/hardware';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RobotCanvasProps {
  robotId: string;
  /** Live telemetry from an existing WebSocket session (optional). */
  telemetry?: RobotTelemetryFrame | null;
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error';

/** Info about a single controllable joint extracted from the URDF. */
interface JointInfo {
  name: string;
  lower: number;
  upper: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * URDF robots use a Z-up coordinate system (robotics convention).
 * Three.js uses Y-up. Rotating −90° around X converts between them.
 */
const URDF_TO_THREEJS_ROTATION = new THREE.Euler(-Math.PI / 2, 0, 0);

const INITIAL_CAMERA_POSITION: [number, number, number] = [0.6, 0.5, 0.6];

const MESH_MATERIAL = new THREE.MeshPhongMaterial({
  color: 0xbbbbbb,
  specular: 0x444444,
  shininess: 60,
});

// ---------------------------------------------------------------------------
// Mesh loader
// ---------------------------------------------------------------------------

/**
 * Build a mesh-load callback for urdf-loader that:
 *  - loads .stl files via Three.js STLLoader
 *  - silently handles unsupported formats
 *  - calls `onAllMeshesLoaded` once every mesh that was started has finished
 *    (success OR failure), enabling the ready-state signal to fire reliably
 *    even for URDFs that contain no meshes at all.
 *
 * @param onAllMeshesLoaded called when pending count drops to 0 after parse
 */
function createMeshLoader(onAllMeshesLoaded: () => void) {
  let pending = 0;
  let parseFinished = false;

  const tryComplete = (): void => {
    if (parseFinished && pending === 0) onAllMeshesLoaded();
  };

  const loader = (
    url: string,
    _mgr: THREE.LoadingManager,
    done: (mesh: THREE.Object3D, err?: Error) => void,
  ): void => {
    pending++;
    const ext = url.split('.').pop()?.toLowerCase();

    const finish = (mesh: THREE.Object3D): void => {
      done(mesh);
      pending--;
      tryComplete();
    };

    if (ext === 'stl') {
      new STLLoader().load(
        url,
        (geometry) => {
          geometry.computeVertexNormals();
          finish(new THREE.Mesh(geometry, MESH_MATERIAL.clone()));
        },
        undefined,
        (err) => {
          console.warn(`[RobotViewer] Failed to load STL: ${url}`, err);
          finish(new THREE.Object3D()); // Silent degraded fallback
        },
      );
    } else {
      console.warn(`[RobotViewer] Unsupported mesh format "${ext}" at ${url}`);
      finish(new THREE.Object3D());
    }
  };

  /** Call this after loader.parse() returns to trigger completion check. */
  const markParseFinished = (): void => {
    parseFinished = true;
    tryComplete(); // Handles URDFs with zero mesh references
  };

  return { loader, markParseFinished };
}

// ---------------------------------------------------------------------------
// URDFModel — inner Three.js component (rendered inside Canvas)
// ---------------------------------------------------------------------------

interface URDFModelProps {
  robotId: string;
  telemetry?: RobotTelemetryFrame | null;
  onLoadStateChange: (state: LoadState) => void;
  /** Called once the URDF is parsed; provides ordered joint info for the panel. */
  onJointsLoaded: (joints: JointInfo[]) => void;
}

function URDFModel({
  robotId,
  telemetry,
  onLoadStateChange,
  onJointsLoaded,
}: URDFModelProps) {
  const { scene } = useThree();
  const robotRef = useRef<URDFRobot | null>(null);

  // ------------------------------------------------------------------
  // Load URDF and add to scene
  // ------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    onLoadStateChange('loading');

    (async () => {
      try {
        // 1. Fetch the URDF text from the backend
        const res = await fetch(`/api/hardware/robots/${robotId}/urdf`);
        if (!res.ok) throw new Error(`URDF fetch failed: ${res.status}`);
        const urdfText = await res.text();

        if (cancelled) return;

        // 2. Build a mesh loader with a completion callback.
        //    onAllMeshesLoaded fires once every mesh (if any) has finished.
        const { loader: meshLoadCb, markParseFinished } = createMeshLoader(() => {
          if (!cancelled) onLoadStateChange('ready');
        });

        // 3. Configure the URDF loader.
        //    workingPath resolves relative mesh paths against the backend asset API.
        //    e.g. "meshes/Base.stl" → "/api/hardware/robots/{id}/urdf/meshes/Base.stl"
        const loader = new URDFLoader();
        loader.workingPath = `/api/hardware/robots/${robotId}/urdf/`;
        loader.loadMeshCb = meshLoadCb;

        // 4. Parse URDF (synchronous; mesh loads are kicked off asynchronously)
        const robot = loader.parse(urdfText);
        if (cancelled) return;

        robot.rotation.copy(URDF_TO_THREEJS_ROTATION);
        scene.add(robot);
        robotRef.current = robot;

        // Extract non-fixed joints in URDF declaration order for the panel
        const joints: JointInfo[] = Object.values(robot.joints)
          .filter(
            (j) =>
              j.jointType === 'revolute' ||
              j.jointType === 'continuous' ||
              j.jointType === 'prismatic',
          )
          .map((j) => ({
            name: j.urdfName,
            lower: j.limit?.lower ?? -Math.PI,
            upper: j.limit?.upper ?? Math.PI,
          }));
        onJointsLoaded(joints);

        // 5. Signal that parsing is done — fires ready immediately if there
        //    were no mesh references, otherwise waits for all STL downloads.
        markParseFinished();
      } catch (err) {
        console.error('[RobotViewer] Failed to load URDF:', err);
        if (!cancelled) onLoadStateChange('error');
      }
    })();

    return () => {
      cancelled = true;
      if (robotRef.current) {
        scene.remove(robotRef.current);
        robotRef.current = null;
      }
    };
  }, [robotId, scene, onLoadStateChange, onJointsLoaded]);

  // ------------------------------------------------------------------
  // Synchronise joint positions from telemetry
  // ------------------------------------------------------------------
  useEffect(() => {
    const robot = robotRef.current;
    if (!robot || !telemetry) return;

    const values: Record<string, number> = {};
    for (const busData of Object.values(telemetry.motor_buses)) {
      for (const [motorName, motorTelemetry] of Object.entries(busData.motors)) {
        if (motorTelemetry.position !== null) {
          values[motorName] = motorTelemetry.position;
        }
      }
    }
    robot.setJointValues(values);
  }, [telemetry]);

  // This component manages Three.js objects imperatively; no JSX output needed.
  return null;
}

// ---------------------------------------------------------------------------
// Lights
// ---------------------------------------------------------------------------

function SceneLights() {
  return (
    <>
      {/* Soft fill light */}
      <ambientLight intensity={0.5} />
      {/* Main directional light from above-front-right */}
      <directionalLight position={[2, 4, 2]} intensity={1.0} castShadow />
      {/* Back fill to reduce harsh shadows */}
      <directionalLight position={[-2, 2, -2]} intensity={0.3} />
    </>
  );
}

// ---------------------------------------------------------------------------
// JointPanel — collapsible overlay listing live joint positions
// ---------------------------------------------------------------------------

interface JointPanelProps {
  joints: JointInfo[];
  /** Current positions keyed by joint name (radians). */
  positions: Record<string, number>;
}

function JointPanel({ joints, positions }: JointPanelProps) {
  const [expanded, setExpanded] = useState(true);

  if (joints.length === 0) return null;

  return (
    <div className="bg-surface-card/85 border-border-default absolute top-2 left-2 z-10 w-52 overflow-hidden rounded-xl border text-xs shadow-lg backdrop-blur-md select-none">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="hover:bg-surface-secondary/50 flex w-full items-center justify-between px-3 py-2 transition-colors"
      >
        <span className="text-content-primary font-semibold">关节</span>
        {expanded ? (
          <ChevronUp className="text-content-tertiary h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="text-content-tertiary h-3.5 w-3.5" />
        )}
      </button>

      {/* Joint list */}
      {expanded && (
        <div className="border-border-subtle flex flex-col gap-2 border-t px-3 py-2">
          {joints.map((joint) => {
            const value = positions[joint.name] ?? 0;

            return (
              <div key={joint.name} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between gap-1">
                  <span className="text-content-primary truncate font-medium">
                    {joint.name}
                  </span>
                  <span className="text-content-secondary shrink-0 font-mono tabular-nums">
                    {value.toFixed(2)}&nbsp;rad
                  </span>
                </div>
                {/* Read-only range input — shows joint position on the limit track */}
                <input
                  type="range"
                  aria-label={`${joint.name} position`}
                  readOnly
                  tabIndex={-1}
                  min={joint.lower}
                  max={joint.upper}
                  step="any"
                  value={value}
                  onChange={() => undefined}
                  className="accent-primary h-1.5 w-full cursor-default opacity-80"
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RobotCanvas (default export — lazy-loaded)
// ---------------------------------------------------------------------------

export default function RobotCanvas({ robotId, telemetry }: RobotCanvasProps) {
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [joints, setJoints] = useState<JointInfo[]>([]);

  const handleJointsLoaded = useCallback((j: JointInfo[]) => setJoints(j), []);

  // Derive current joint positions from the latest telemetry frame
  const jointPositions: Record<string, number> = {};
  if (telemetry) {
    for (const busData of Object.values(telemetry.motor_buses)) {
      for (const [name, m] of Object.entries(busData.motors)) {
        if (m.position !== null) jointPositions[name] = m.position;
      }
    }
  }

  return (
    <div className="bg-surface-secondary relative h-full w-full overflow-hidden rounded-lg">
      {/* Joint panel overlay (outside Canvas to avoid WebGL context issues) */}
      {loadState === 'ready' && (
        <JointPanel joints={joints} positions={jointPositions} />
      )}

      <Canvas
        camera={{ position: INITIAL_CAMERA_POSITION, fov: 45, near: 0.01, far: 50 }}
        shadows
        style={{ width: '100%', height: '100%' }}
        gl={{ antialias: true }}
      >
        <SceneLights />

        {/* Floor grid */}
        <gridHelper args={[2, 20, '#444444', '#333333']} position={[0, -0.001, 0]} />

        {/* URDF robot */}
        <URDFModel
          robotId={robotId}
          telemetry={telemetry}
          onLoadStateChange={setLoadState}
          onJointsLoaded={handleJointsLoaded}
        />

        {/* Camera controls */}
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={0.1}
          maxDistance={10}
          target={[0, 0.15, 0]}
        />

        {/* Inline loading / error overlay (renders inside the WebGL canvas) */}
        {loadState === 'loading' && (
          <Html center>
            <div className="text-content-secondary bg-surface-card/80 rounded-lg px-3 py-1.5 text-sm backdrop-blur-sm">
              Loading 3D model…
            </div>
          </Html>
        )}
        {loadState === 'error' && (
          <Html center>
            <div className="bg-surface-card/80 rounded-lg px-3 py-1.5 text-sm text-red-400 backdrop-blur-sm">
              Failed to load URDF
            </div>
          </Html>
        )}
      </Canvas>

      {/* Telemetry indicator badge */}
      <div className="bg-surface-card/70 text-content-secondary absolute right-2 bottom-2 flex items-center gap-1.5 rounded px-2 py-1 text-xs backdrop-blur-sm">
        <div
          className={[
            'h-1.5 w-1.5 rounded-full',
            telemetry ? 'animate-pulse bg-green-500' : 'bg-content-tertiary',
          ].join(' ')}
        />
        {telemetry ? 'Live' : 'No telemetry'}
      </div>
    </div>
  );
}
