export type LandmarkPoint = [number, number, number];

export type LandmarkFrame = {
  pose: LandmarkPoint[];
  leftHand: LandmarkPoint[];
  rightHand: LandmarkPoint[];
};

export type SignLandmarkClip = {
  label: string;
  fps: number;
  source: string;
  frames: LandmarkFrame[];
};
