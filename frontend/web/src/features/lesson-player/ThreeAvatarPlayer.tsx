import { Canvas } from "@react-three/fiber";
import { lazy, Suspense, useEffect, useState } from "react";
import type { ReactElement } from "react";
import * as THREE from "three";
import { RenderErrorBoundary } from "../../components/RenderErrorBoundary";
import type { LandmarkFrame } from "../../types/landmarks";

const DEFAULT_MODEL_URL = "/models/avatar.vrm";
type VrmAvatarProps = {
  frame: LandmarkFrame;
  modelUrl: string;
  isPlaying: boolean;
  hasPlaybackBegun: boolean;
};

const LazyVrmAvatar = lazy(() =>
  import("./VrmAvatar").then((module) => ({
    default: module.VrmAvatar as (props: VrmAvatarProps) => ReactElement | null,
  })),
);

function useWebGlAvailable() {
  const [isAvailable, setIsAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ??
      canvas.getContext("webgl") ??
      canvas.getContext("experimental-webgl");
    setIsAvailable(Boolean(gl));
  }, []);

  return isAvailable;
}

function StageLights() {
  return (
    <>
      <ambientLight intensity={0.45} />
      <directionalLight
        intensity={1.1}
        position={[2.8, 4.2, 4.5]}
      />
      <hemisphereLight args={["#cad2db", "#171a1b", 0.35]} />
    </>
  );
}

function Backdrop() {
  return (
    <mesh position={[0, 0.92, -1.1]}>
      <circleGeometry args={[2.15, 64]} />
      <meshBasicMaterial color="#181818" transparent opacity={0.4} />
    </mesh>
  );
}

export function ThreeAvatarPlayer({
  frame,
  isPlaying,
  hasPlaybackBegun,
}: {
  frame: LandmarkFrame;
  isPlaying: boolean;
  hasPlaybackBegun: boolean;
}) {
  const modelUrl = DEFAULT_MODEL_URL;
  const webGlAvailable = useWebGlAvailable();

  if (webGlAvailable === null) {
    return (
      <div className="three-stage three-stage-error">
        <strong>Preparing 3D preview...</strong>
      </div>
    );
  }

  if (!webGlAvailable) {
    return (
      <div className="three-stage three-stage-error" role="alert">
        <strong>WebGL is not available.</strong>
        <span>This browser cannot start the 3D avatar renderer.</span>
      </div>
    );
  }

  return (
    <RenderErrorBoundary
      fallback={(error) => (
        <div className="three-stage three-stage-error" role="alert">
          <strong>3D preview could not start.</strong>
          <span>{error.message}</span>
        </div>
      )}
      resetKey={modelUrl}
    >
      <div className="three-stage">
        <Canvas
          camera={{ fov: 15, position: [0, 1.52, 3.35] }}
          dpr={[1, 1.2]}
          gl={{ antialias: false, powerPreference: "high-performance" }}
          onCreated={({ gl, camera }) => {
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 0.78;
            camera.lookAt(0, 0.35, -0.9);
          }}
        >
          <color attach="background" args={["#000000"]} />
          <StageLights />
          <Backdrop />
          <group position={[0, 0, -0.9]}>
            <Suspense fallback={null}>
              <LazyVrmAvatar
                frame={frame}
                modelUrl={modelUrl}
                isPlaying={isPlaying}
                hasPlaybackBegun={hasPlaybackBegun}
              />
            </Suspense>
          </group>
        </Canvas>
      </div>
    </RenderErrorBoundary>
  );
}
