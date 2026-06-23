from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

EXPECTED_POINT_COUNTS: dict[str, int] = {
    "pose": 33,
    "left_hand": 21,
    "right_hand": 21,
}
POSE_LEFT_SHOULDER = 11
POSE_RIGHT_SHOULDER = 12
POSE_LEFT_HIP = 23
POSE_RIGHT_HIP = 24
SIGN_FEATURE_VERSION = "pose_hands_resampled_v1"


@dataclass(frozen=True)
class SignFeatureStats:
    frame_count: int
    left_hand_frame_pct: float
    right_hand_frame_pct: float
    both_hands_missing_frame_pct: float


def load_landmark_sequence(path: Path) -> np.ndarray:
    return np.load(path, allow_pickle=True)


def extract_sign_feature_vector(
    sequence: np.ndarray,
    *,
    target_frames: int,
) -> tuple[np.ndarray, SignFeatureStats]:
    if target_frames < 2:
        raise ValueError("Sign recognizer target_frames must be at least 2.")

    if len(sequence) == 0:
        raise ValueError("Landmark sequence is empty.")

    frame_vectors: list[np.ndarray] = []
    left_present_frames = 0
    right_present_frames = 0
    both_hands_missing_frames = 0

    for frame in sequence:
        if not isinstance(frame, dict):
            continue

        pose, pose_mask = _extract_group(frame, "pose")
        left_hand, left_mask = _extract_group(frame, "left_hand")
        right_hand, right_mask = _extract_group(frame, "right_hand")

        left_present = float(left_mask.any())
        right_present = float(right_mask.any())

        if left_present:
            left_present_frames += 1
        if right_present:
            right_present_frames += 1
        if not left_present and not right_present:
            both_hands_missing_frames += 1

        center, scale = _pose_center_and_scale(pose, pose_mask)
        normalized_pose = _normalize_points(pose, pose_mask, center, scale)
        normalized_left = _normalize_points(left_hand, left_mask, center, scale)
        normalized_right = _normalize_points(right_hand, right_mask, center, scale)

        frame_meta = np.array(
            [left_present, right_present, float(left_present and right_present)],
            dtype=np.float32,
        )
        frame_vector = np.concatenate(
            [
                normalized_pose.reshape(-1),
                normalized_left.reshape(-1),
                normalized_right.reshape(-1),
                frame_meta,
            ]
        )
        frame_vectors.append(frame_vector.astype(np.float32, copy=False))

    if not frame_vectors:
        raise ValueError("Landmark sequence does not contain any usable frames.")

    frame_matrix = np.stack(frame_vectors, axis=0)
    resampled_frames = _resample_frame_matrix(frame_matrix, target_frames)
    frame_count = frame_matrix.shape[0]
    stats = SignFeatureStats(
        frame_count=frame_count,
        left_hand_frame_pct=left_present_frames / frame_count * 100.0,
        right_hand_frame_pct=right_present_frames / frame_count * 100.0,
        both_hands_missing_frame_pct=both_hands_missing_frames / frame_count * 100.0,
    )
    summary_features = np.array(
        [
            min(frame_count, target_frames * 4) / float(target_frames * 4),
            stats.left_hand_frame_pct / 100.0,
            stats.right_hand_frame_pct / 100.0,
            stats.both_hands_missing_frame_pct / 100.0,
        ],
        dtype=np.float32,
    )
    feature_vector = np.concatenate([resampled_frames.reshape(-1), summary_features]).astype(
        np.float32,
        copy=False,
    )
    norm = float(np.linalg.norm(feature_vector))
    if norm > 0:
        feature_vector = feature_vector / norm

    return feature_vector.astype(np.float32, copy=False), stats


def extract_sign_feature_vector_from_path(
    landmark_path: Path,
    *,
    target_frames: int,
) -> tuple[np.ndarray, SignFeatureStats]:
    return extract_sign_feature_vector(
        load_landmark_sequence(landmark_path),
        target_frames=target_frames,
    )


def _extract_group(frame: dict[str, Any], key: str) -> tuple[np.ndarray, np.ndarray]:
    expected_points = EXPECTED_POINT_COUNTS[key]
    points = np.zeros((expected_points, 3), dtype=np.float32)
    mask = np.zeros((expected_points, 1), dtype=np.float32)
    raw_points = frame.get(key, []) or []

    limit = min(len(raw_points), expected_points)
    for index in range(limit):
        raw_point = raw_points[index]
        if not isinstance(raw_point, (list, tuple, np.ndarray)) or len(raw_point) < 3:
            continue
        points[index] = np.asarray(raw_point[:3], dtype=np.float32)
        mask[index, 0] = 1.0

    return points, mask


def _pose_center_and_scale(pose: np.ndarray, pose_mask: np.ndarray) -> tuple[np.ndarray, float]:
    visible = pose_mask[:, 0] > 0
    if not visible.any():
        return np.zeros(3, dtype=np.float32), 1.0

    center_candidates: list[np.ndarray] = []
    left_shoulder = _masked_point(pose, pose_mask, POSE_LEFT_SHOULDER)
    right_shoulder = _masked_point(pose, pose_mask, POSE_RIGHT_SHOULDER)
    left_hip = _masked_point(pose, pose_mask, POSE_LEFT_HIP)
    right_hip = _masked_point(pose, pose_mask, POSE_RIGHT_HIP)

    if left_shoulder is not None and right_shoulder is not None:
        center_candidates.append((left_shoulder + right_shoulder) / 2.0)
    if left_hip is not None and right_hip is not None:
        center_candidates.append((left_hip + right_hip) / 2.0)

    if center_candidates:
        center = np.mean(np.stack(center_candidates, axis=0), axis=0)
    else:
        center = np.mean(pose[visible], axis=0)

    scale_candidates: list[float] = []
    if left_shoulder is not None and right_shoulder is not None:
        scale_candidates.append(float(np.linalg.norm(left_shoulder[:2] - right_shoulder[:2])))
    if left_hip is not None and right_hip is not None:
        scale_candidates.append(float(np.linalg.norm(left_hip[:2] - right_hip[:2])))
    if left_shoulder is not None and left_hip is not None:
        scale_candidates.append(float(np.linalg.norm(left_shoulder[:2] - left_hip[:2])))
    if right_shoulder is not None and right_hip is not None:
        scale_candidates.append(float(np.linalg.norm(right_shoulder[:2] - right_hip[:2])))

    scale = max(scale_candidates, default=0.0)
    if scale < 1e-4:
        spread = np.std(pose[visible], axis=0)
        scale = float(np.linalg.norm(spread[:2]))
    if scale < 1e-4:
        scale = 1.0

    return center.astype(np.float32, copy=False), float(scale)


def _masked_point(points: np.ndarray, mask: np.ndarray, index: int) -> np.ndarray | None:
    if index >= len(points) or mask[index, 0] <= 0:
        return None
    return points[index]


def _normalize_points(
    points: np.ndarray,
    mask: np.ndarray,
    center: np.ndarray,
    scale: float,
) -> np.ndarray:
    normalized = np.zeros_like(points, dtype=np.float32)
    visible = mask[:, 0] > 0
    if visible.any():
        normalized[visible] = (points[visible] - center) / scale
    return normalized


def _resample_frame_matrix(frame_matrix: np.ndarray, target_frames: int) -> np.ndarray:
    frame_count, feature_width = frame_matrix.shape
    if frame_count == target_frames:
        return frame_matrix.astype(np.float32, copy=False)

    if frame_count == 1:
        return np.repeat(frame_matrix, target_frames, axis=0).astype(np.float32, copy=False)

    source_steps = np.linspace(0.0, 1.0, num=frame_count, dtype=np.float32)
    target_steps = np.linspace(0.0, 1.0, num=target_frames, dtype=np.float32)
    resampled_columns = [
        np.interp(target_steps, source_steps, frame_matrix[:, column_index])
        for column_index in range(feature_width)
    ]
    return np.stack(resampled_columns, axis=1).astype(np.float32, copy=False)
