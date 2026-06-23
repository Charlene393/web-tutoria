import type {
  LandmarkFrame,
  LandmarkPoint,
  SignLandmarkClip,
} from "../../types/landmarks";

function interpolateNumber(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function easeInOut(t: number) {
  return t * t * (3 - 2 * t);
}

function interpolatePoint(
  a: LandmarkPoint | undefined,
  b: LandmarkPoint | undefined,
  t: number,
): LandmarkPoint {
  const start = a ?? b ?? [0, 0, 0];
  const end = b ?? a ?? [0, 0, 0];

  return [
    interpolateNumber(start[0], end[0], t),
    interpolateNumber(start[1], end[1], t),
    interpolateNumber(start[2], end[2], t),
  ];
}

function interpolateLandmarks(
  current: LandmarkPoint[],
  next: LandmarkPoint[],
  t: number,
) {
  const length = Math.max(current.length, next.length);
  return Array.from({ length }, (_, index) =>
    interpolatePoint(current[index], next[index], t),
  );
}

export function getInterpolatedFrame(
  clip: SignLandmarkClip,
  framePosition: number,
): LandmarkFrame {
  const currentIndex = Math.floor(framePosition);
  const nextIndex = Math.min(currentIndex + 1, clip.frames.length - 1);
  const t = easeInOut(framePosition - currentIndex);
  const current = clip.frames[currentIndex];
  const next = clip.frames[nextIndex];

  return {
    pose: interpolateLandmarks(current.pose, next.pose, t),
    leftHand: interpolateLandmarks(current.leftHand, next.leftHand, t),
    rightHand: interpolateLandmarks(current.rightHand, next.rightHand, t),
  };
}
