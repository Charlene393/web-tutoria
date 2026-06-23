import { useFrame, useLoader } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTF, GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin } from "@pixiv/three-vrm";
import type { LandmarkFrame } from "../../types/landmarks";
import { createRigFrame, rotationFromDirection } from "./landmarkRig";

type VrmGltf = GLTF & { userData: { vrm?: VRM } };

// Fallback bind-axis directions if rest extraction is unavailable.
const LEFT_UPPER_REST  = new THREE.Vector3(1, -1, 0).normalize();
const RIGHT_UPPER_REST = new THREE.Vector3(-1, -1, 0).normalize();
const LEFT_LOWER_REST  = new THREE.Vector3(1, -1, 0).normalize();
const RIGHT_LOWER_REST = new THREE.Vector3(-1, -1, 0).normalize();
const DOWN_REST        = new THREE.Vector3(0, -1, 0);

// Arms-down resting quaternions (what the character holds when idle)
const REST_POSE: Record<string, THREE.Quaternion> = {
  leftUpperArm:  new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, -Math.PI * 0.42)),
  rightUpperArm: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0,  Math.PI * 0.42)),
  leftLowerArm:  new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, -0.1)),
  rightLowerArm: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0,  0.1)),
  spine:         new THREE.Quaternion(), // upright
};

const LERP_SPEED = 8; // higher = snappier, lower = smoother
const LOWER_ARM_LERP_SPEED = 12;
const FINGER_LERP_SPEED = 14;
const DEFAULT_REST_LOCAL = new THREE.Vector3(0, 1, 0);
const CROSS_BODY_MARGIN = 0.08;

function pushOutsideSphere(
  point: THREE.Vector3,
  center: THREE.Vector3,
  radius: number,
  fallbackDirection: THREE.Vector3,
) {
  const offset = point.clone().sub(center);
  const distance = offset.length();
  if (distance >= radius) {
    return point;
  }

  const direction = distance > 1e-5 ? offset.normalize() : fallbackDirection.clone().normalize();
  return center.clone().add(direction.multiplyScalar(radius));
}

function pushOutsideCapsule(
  point: THREE.Vector3,
  start: THREE.Vector3,
  end: THREE.Vector3,
  radius: number,
  fallbackDirection: THREE.Vector3,
) {
  const axis = end.clone().sub(start);
  const axisLengthSq = axis.lengthSq();
  if (axisLengthSq < 1e-6) {
    return pushOutsideSphere(point, start, radius, fallbackDirection);
  }

  const toPoint = point.clone().sub(start);
  const t = Math.min(1, Math.max(0, toPoint.dot(axis) / axisLengthSq));
  const closest = start.clone().add(axis.multiplyScalar(t));
  return pushOutsideSphere(point, closest, radius, fallbackDirection);
}

type RestDirections = Record<string, THREE.Vector3>;
type HandSide = "left" | "right";
type FingerMapping = {
  side: HandSide;
  start: number;
  end: number;
  boneName: string;
};

const UPPER_TO_LOWER: Record<"leftUpperArm" | "rightUpperArm", "leftLowerArm" | "rightLowerArm"> = {
  leftUpperArm: "leftLowerArm",
  rightUpperArm: "rightLowerArm",
};

const LOWER_TO_HAND: Record<"leftLowerArm" | "rightLowerArm", "leftHand" | "rightHand"> = {
  leftLowerArm: "leftHand",
  rightLowerArm: "rightHand",
};

const FALLBACK_REST_LOCAL: RestDirections = {
  leftUpperArm: LEFT_UPPER_REST.clone(),
  rightUpperArm: RIGHT_UPPER_REST.clone(),
  leftLowerArm: LEFT_LOWER_REST.clone(),
  rightLowerArm: RIGHT_LOWER_REST.clone(),
};

const FINGER_SEGMENTS: Record<HandSide, Array<{ start: number; end: number; candidates: string[] }>> = {
  left: [
    { start: 0, end: 1, candidates: ["leftThumbMetacarpal", "leftThumbProximal"] },
    { start: 1, end: 2, candidates: ["leftThumbProximal", "leftThumbIntermediate"] },
    { start: 2, end: 3, candidates: ["leftThumbDistal"] },
    { start: 5, end: 6, candidates: ["leftIndexProximal"] },
    { start: 6, end: 7, candidates: ["leftIndexIntermediate"] },
    { start: 7, end: 8, candidates: ["leftIndexDistal"] },
    { start: 9, end: 10, candidates: ["leftMiddleProximal"] },
    { start: 10, end: 11, candidates: ["leftMiddleIntermediate"] },
    { start: 11, end: 12, candidates: ["leftMiddleDistal"] },
    { start: 13, end: 14, candidates: ["leftRingProximal"] },
    { start: 14, end: 15, candidates: ["leftRingIntermediate"] },
    { start: 15, end: 16, candidates: ["leftRingDistal"] },
    { start: 17, end: 18, candidates: ["leftLittleProximal"] },
    { start: 18, end: 19, candidates: ["leftLittleIntermediate"] },
    { start: 19, end: 20, candidates: ["leftLittleDistal"] },
  ],
  right: [
    { start: 0, end: 1, candidates: ["rightThumbMetacarpal", "rightThumbProximal"] },
    { start: 1, end: 2, candidates: ["rightThumbProximal", "rightThumbIntermediate"] },
    { start: 2, end: 3, candidates: ["rightThumbDistal"] },
    { start: 5, end: 6, candidates: ["rightIndexProximal"] },
    { start: 6, end: 7, candidates: ["rightIndexIntermediate"] },
    { start: 7, end: 8, candidates: ["rightIndexDistal"] },
    { start: 9, end: 10, candidates: ["rightMiddleProximal"] },
    { start: 10, end: 11, candidates: ["rightMiddleIntermediate"] },
    { start: 11, end: 12, candidates: ["rightMiddleDistal"] },
    { start: 13, end: 14, candidates: ["rightRingProximal"] },
    { start: 14, end: 15, candidates: ["rightRingIntermediate"] },
    { start: 15, end: 16, candidates: ["rightRingDistal"] },
    { start: 17, end: 18, candidates: ["rightLittleProximal"] },
    { start: 18, end: 19, candidates: ["rightLittleIntermediate"] },
    { start: 19, end: 20, candidates: ["rightLittleDistal"] },
  ],
};

export function VrmAvatar({
  frame,
  modelUrl,
  isPlaying,
  hasPlaybackBegun,
}: {
  frame: LandmarkFrame;
  modelUrl: string;
  isPlaying: boolean;
  hasPlaybackBegun: boolean;
}) {
  const gltf = useLoader(GLTFLoader, modelUrl, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  }) as VrmGltf;

  const vrm = gltf.userData.vrm;
  const restDirectionsRef = useRef<RestDirections | null>(null);
  const fingerMappingsRef = useRef<FingerMapping[]>([]);

  const tempVector = useRef(new THREE.Vector3());
  const tempVector2 = useRef(new THREE.Vector3());
  const tempParentQuat = useRef(new THREE.Quaternion());

  function getBoneDirInParentLocal(
    boneName: string,
    childName?: string,
  ) {
    const bone = vrm?.humanoid.getNormalizedBoneNode(boneName as any);
    const child = childName
      ? vrm?.humanoid.getNormalizedBoneNode(childName as any)
      : (bone?.children[0] as THREE.Object3D | undefined);
    if (!bone || !child) {
      return null;
    }

    const bonePos = bone.getWorldPosition(tempVector.current);
    const childPos = child.getWorldPosition(tempVector2.current);
    const worldDir = childPos.clone().sub(bonePos);
    if (worldDir.lengthSq() < 1e-6) {
      return null;
    }

    const parentWorldQuat = bone.parent
      ? bone.parent.getWorldQuaternion(tempParentQuat.current).clone()
      : new THREE.Quaternion();

    return worldDir.normalize().applyQuaternion(parentWorldQuat.invert());
  }

  function getRestDirectionForBone(name: string) {
    return restDirectionsRef.current?.[name] ?? FALLBACK_REST_LOCAL[name] ?? DEFAULT_REST_LOCAL;
  }

  function solveBoneToWorldDirection(
    name: string,
    desiredWorldDirection: THREE.Vector3,
    delta: number,
    speed = LERP_SPEED,
  ) {
    if (!vrm) return;
    if (desiredWorldDirection.lengthSq() < 1e-6) return;

    const bone = vrm.humanoid.getNormalizedBoneNode(name as any);
    if (!bone) return;

    const parentWorldQuat = bone.parent
      ? bone.parent.getWorldQuaternion(tempParentQuat.current).clone()
      : new THREE.Quaternion();
    const targetLocalDir = desiredWorldDirection
      .clone()
      .normalize()
      .applyQuaternion(parentWorldQuat.invert());

    const restLocalDir = getRestDirectionForBone(name);
    const targetQuat = new THREE.Quaternion().setFromUnitVectors(restLocalDir, targetLocalDir);
    bone.quaternion.slerp(targetQuat, Math.min(1, delta * speed));
  }

  useEffect(() => {
    if (!vrm) return;
    vrm.scene.rotation.y = Math.PI;
    vrm.scene.traverse((obj) => { obj.frustumCulled = false; });

    // Capture each arm bone's bind/rest direction in parent local space from this VRM.
    vrm.scene.updateMatrixWorld(true);
    const extracted: RestDirections = {
      leftUpperArm:
        getBoneDirInParentLocal("leftUpperArm", UPPER_TO_LOWER.leftUpperArm) ??
        FALLBACK_REST_LOCAL.leftUpperArm.clone(),
      rightUpperArm:
        getBoneDirInParentLocal("rightUpperArm", UPPER_TO_LOWER.rightUpperArm) ??
        FALLBACK_REST_LOCAL.rightUpperArm.clone(),
      leftLowerArm:
        getBoneDirInParentLocal("leftLowerArm", LOWER_TO_HAND.leftLowerArm) ??
        FALLBACK_REST_LOCAL.leftLowerArm.clone(),
      rightLowerArm:
        getBoneDirInParentLocal("rightLowerArm", LOWER_TO_HAND.rightLowerArm) ??
        FALLBACK_REST_LOCAL.rightLowerArm.clone(),
    };

    const resolvedFingerMappings: FingerMapping[] = [];
    const usedBones = new Set<string>();

    for (const side of ["left", "right"] as const) {
      for (let i = 0; i < FINGER_SEGMENTS[side].length; i += 1) {
        const segment = FINGER_SEGMENTS[side][i];
        const resolvedBone = segment.candidates.find((candidate) => {
          if (usedBones.has(candidate)) {
            return false;
          }
          return Boolean(vrm.humanoid.getNormalizedBoneNode(candidate as any));
        });

        if (!resolvedBone) {
          continue;
        }

        usedBones.add(resolvedBone);
        resolvedFingerMappings.push({
          side,
          start: segment.start,
          end: segment.end,
          boneName: resolvedBone,
        });
      }
    }

    for (const mapping of resolvedFingerMappings) {
      const nextInSameFinger = resolvedFingerMappings.find((candidate) =>
        candidate.side === mapping.side &&
        candidate.start === mapping.end,
      );

      extracted[mapping.boneName] =
        getBoneDirInParentLocal(mapping.boneName, nextInSameFinger?.boneName) ??
        DEFAULT_REST_LOCAL.clone();
    }

    restDirectionsRef.current = extracted;
    fingerMappingsRef.current = resolvedFingerMappings;
  }, [vrm]);

  useFrame((_, delta) => {
    if (!vrm) return;

    const humanoid = vrm.humanoid;
    const rig = createRigFrame(frame);

    // Drive animation only while playback is active.
    const isAnimating = isPlaying && frame.pose.length > 0;

    function setBone(name: string, target: THREE.Quaternion, speed = LERP_SPEED) {
      const node = humanoid.getNormalizedBoneNode(name as any);
      if (!node) return;
      node.quaternion.slerp(target, Math.min(1, delta * speed));
    }

    if (isAnimating) {
      const torsoCenter = rig.chest.clone().lerp(rig.hips, 0.42);
      const headCenter = rig.head.clone().add(new THREE.Vector3(0, 0.08, 0));
      const torsoRadius = Math.max(0.22, rig.shoulderWidth * 0.34);
      const headRadius = Math.max(0.12, rig.shoulderWidth * 0.16);
      const chestCapsuleStart = rig.chest.clone().add(new THREE.Vector3(0, 0.06, 0));
      const chestCapsuleEnd = rig.chest.clone().add(new THREE.Vector3(0, -0.24, 0));
      const chestElbowRadius = Math.max(0.19, rig.shoulderWidth * 0.28);
      const chestWristRadius = Math.max(0.23, rig.shoulderWidth * 0.34);

      let leftElbowPoint = pushOutsideSphere(
        rig.leftElbow,
        torsoCenter,
        torsoRadius,
        new THREE.Vector3(1, 0, 0),
      );
      let rightElbowPoint = pushOutsideSphere(
        rig.rightElbow,
        torsoCenter,
        torsoRadius,
        new THREE.Vector3(-1, 0, 0),
      );

      leftElbowPoint = pushOutsideCapsule(
        leftElbowPoint,
        chestCapsuleStart,
        chestCapsuleEnd,
        chestElbowRadius,
        new THREE.Vector3(1, 0, 0),
      );
      rightElbowPoint = pushOutsideCapsule(
        rightElbowPoint,
        chestCapsuleStart,
        chestCapsuleEnd,
        chestElbowRadius,
        new THREE.Vector3(-1, 0, 0),
      );

      let leftWristPoint = pushOutsideSphere(
        rig.leftWrist,
        torsoCenter,
        torsoRadius + 0.04,
        new THREE.Vector3(1, 0, 0),
      );
      let rightWristPoint = pushOutsideSphere(
        rig.rightWrist,
        torsoCenter,
        torsoRadius + 0.04,
        new THREE.Vector3(-1, 0, 0),
      );

      leftWristPoint = pushOutsideCapsule(
        leftWristPoint,
        chestCapsuleStart,
        chestCapsuleEnd,
        chestWristRadius,
        new THREE.Vector3(1, 0, 0),
      );
      rightWristPoint = pushOutsideCapsule(
        rightWristPoint,
        chestCapsuleStart,
        chestCapsuleEnd,
        chestWristRadius,
        new THREE.Vector3(-1, 0, 0),
      );

      leftWristPoint = pushOutsideSphere(
        leftWristPoint,
        headCenter,
        headRadius,
        new THREE.Vector3(1, -0.2, 0),
      );
      rightWristPoint = pushOutsideSphere(
        rightWristPoint,
        headCenter,
        headRadius,
        new THREE.Vector3(-1, -0.2, 0),
      );

      // Keep wrists from crossing deeply into the opposite torso side.
      leftWristPoint.x = Math.max(leftWristPoint.x, rig.chest.x - CROSS_BODY_MARGIN);
      rightWristPoint.x = Math.min(rightWristPoint.x, rig.chest.x + CROSS_BODY_MARGIN);

      const leftUpperDir = leftElbowPoint.clone().sub(rig.leftShoulder);
      const rightUpperDir = rightElbowPoint.clone().sub(rig.rightShoulder);
      const leftLowerDir = leftWristPoint.clone().sub(leftElbowPoint);
      const rightLowerDir = rightWristPoint.clone().sub(rightElbowPoint);

      // Drive arms by matching desired world segment directions against each bone's
      // extracted bind axis in local parent space.
      solveBoneToWorldDirection("leftUpperArm", leftUpperDir, delta);
      solveBoneToWorldDirection("rightUpperArm", rightUpperDir, delta);
      solveBoneToWorldDirection("leftLowerArm", leftLowerDir, delta, LOWER_ARM_LERP_SPEED);
      solveBoneToWorldDirection("rightLowerArm", rightLowerDir, delta, LOWER_ARM_LERP_SPEED);

      for (const mapping of fingerMappingsRef.current) {
        const points = mapping.side === "left" ? rig.leftHand : rig.rightHand;
        if (points.length <= mapping.end) {
          continue;
        }

        const desiredDirection = points[mapping.end].clone().sub(points[mapping.start]);
        solveBoneToWorldDirection(mapping.boneName, desiredDirection, delta, FINGER_LERP_SPEED);
      }

      setBone("spine",
        rotationFromDirection(DOWN_REST, rig.hips.clone().sub(rig.chest)).slerp(
          new THREE.Quaternion(), 0.72
        )
      );
    } else if (!hasPlaybackBegun) {
      // Keep a neutral arms-down rest pose before first playback.
      for (const [name, q] of Object.entries(REST_POSE)) {
        setBone(name, q);
      }
    }

    vrm.update(delta);
  });

  if (!vrm) return null;
  return <primitive object={vrm.scene} position={[0, -0.95, 0]} />;
}