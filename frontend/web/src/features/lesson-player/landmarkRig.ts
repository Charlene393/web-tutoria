import * as THREE from "three";
import type { LandmarkFrame, LandmarkPoint } from "../../types/landmarks";

const POSE = {
  nose: 0,
  leftShoulder: 11,
  rightShoulder: 12,
  leftElbow: 13,
  rightElbow: 14,
  leftWrist: 15,
  rightWrist: 16,
  leftHip: 23,
  rightHip: 24,
  leftKnee: 25,
  rightKnee: 26,
  leftAnkle: 27,
  rightAnkle: 28,
} as const;

export type RigFrame = {
  head: THREE.Vector3;
  neck: THREE.Vector3;
  chest: THREE.Vector3;
  hips: THREE.Vector3;
  leftShoulder: THREE.Vector3;
  rightShoulder: THREE.Vector3;
  leftElbow: THREE.Vector3;
  rightElbow: THREE.Vector3;
  leftWrist: THREE.Vector3;
  rightWrist: THREE.Vector3;
  leftHip: THREE.Vector3;
  rightHip: THREE.Vector3;
  leftKnee: THREE.Vector3;
  rightKnee: THREE.Vector3;
  leftAnkle: THREE.Vector3;
  rightAnkle: THREE.Vector3;
  leftHand: THREE.Vector3[];
  rightHand: THREE.Vector3[];
  shoulderWidth: number;
  torsoHeight: number;
};

function midpoint(a: LandmarkPoint, b: LandmarkPoint): LandmarkPoint {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
}

function pointOr(point: LandmarkPoint | undefined, fallback: LandmarkPoint) {
  return point ?? fallback;
}

function landmarkToVector(
  point: LandmarkPoint,
  origin: LandmarkPoint,
  scale: number,
) {
  return new THREE.Vector3(
    (point[0] - origin[0]) * scale,
    (origin[1] - point[1]) * scale + 1.05,
    (origin[2] - point[2]) * scale * 0.65,
  );
}

function distance2d(a: LandmarkPoint, b: LandmarkPoint) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function createRigFrame(frame: LandmarkFrame): RigFrame {
  const leftShoulderRaw = pointOr(frame.pose[POSE.leftShoulder], [0.58, 0.42, 0]);
  const rightShoulderRaw = pointOr(frame.pose[POSE.rightShoulder], [0.42, 0.42, 0]);
  const leftHipRaw = pointOr(frame.pose[POSE.leftHip], [0.55, 0.72, 0]);
  const rightHipRaw = pointOr(frame.pose[POSE.rightHip], [0.45, 0.72, 0]);
  const shoulderCenterRaw = midpoint(leftShoulderRaw, rightShoulderRaw);
  const hipCenterRaw = midpoint(leftHipRaw, rightHipRaw);
  const torsoRawHeight = Math.max(distance2d(shoulderCenterRaw, hipCenterRaw), 0.08);
  const scale = 1.35 / torsoRawHeight;
  const origin = hipCenterRaw;

  const toVector = (point: LandmarkPoint) => landmarkToVector(point, origin, scale);
  const shoulderCenter = toVector(shoulderCenterRaw);
  const hips = toVector(hipCenterRaw);
  const head = toVector(pointOr(frame.pose[POSE.nose], [shoulderCenterRaw[0], shoulderCenterRaw[1] - 0.18, 0]));
  const neck = shoulderCenter.clone().lerp(head, 0.18);

  return {
    head,
    neck,
    chest: shoulderCenter,
    hips,
    leftShoulder: toVector(leftShoulderRaw),
    rightShoulder: toVector(rightShoulderRaw),
    leftElbow: toVector(pointOr(frame.pose[POSE.leftElbow], leftShoulderRaw)),
    rightElbow: toVector(pointOr(frame.pose[POSE.rightElbow], rightShoulderRaw)),
    leftWrist: toVector(pointOr(frame.pose[POSE.leftWrist], leftShoulderRaw)),
    rightWrist: toVector(pointOr(frame.pose[POSE.rightWrist], rightShoulderRaw)),
    leftHip: toVector(leftHipRaw),
    rightHip: toVector(rightHipRaw),
    leftKnee: toVector(pointOr(frame.pose[POSE.leftKnee], leftHipRaw)),
    rightKnee: toVector(pointOr(frame.pose[POSE.rightKnee], rightHipRaw)),
    leftAnkle: toVector(pointOr(frame.pose[POSE.leftAnkle], leftHipRaw)),
    rightAnkle: toVector(pointOr(frame.pose[POSE.rightAnkle], rightHipRaw)),
    leftHand: frame.leftHand.map(toVector),
    rightHand: frame.rightHand.map(toVector),
    shoulderWidth: distance2d(leftShoulderRaw, rightShoulderRaw) * scale,
    torsoHeight: torsoRawHeight * scale,
  };
}

export function rotationFromDirection(
  restDirection: THREE.Vector3,
  currentDirection: THREE.Vector3,
) {
  const from = restDirection.clone().normalize();
  const to = currentDirection.clone().normalize();
  if (to.lengthSq() < 0.0001) {
    return new THREE.Quaternion();
  }
  return new THREE.Quaternion().setFromUnitVectors(from, to);
}

export function quaternionTuple(quaternion: THREE.Quaternion) {
  return [quaternion.x, quaternion.y, quaternion.z, quaternion.w] as [
    number,
    number,
    number,
    number,
  ];
}
