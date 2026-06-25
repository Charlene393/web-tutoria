from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from ..schemas.responses import LandmarkFrameResponse, LessonLandmarkClipResponse
from .sign_features import load_landmark_sequence


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _lesson_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ksl_lesson_catalog.json"


@lru_cache(maxsize=1)
def _load_catalog_entries() -> dict[str, dict]:
    catalog_path = _lesson_catalog_path()
    with catalog_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return {
        entry["asset_id"]: entry
        for entry in payload.get("entries", [])
        if entry.get("asset_id")
    }


def build_stickman_video_url(asset_id: str | None) -> str | None:
    if not asset_id:
        return None

    return f"/api/v1/lesson-assets/{quote(asset_id, safe='')}/stickman-video"


def get_stickman_video_file(asset_id: str) -> Path:
    entry = _load_catalog_entries().get(asset_id)
    if not entry:
        raise FileNotFoundError(f"Lesson asset {asset_id!r} was not found in the lesson catalog.")

    relative_path = entry.get("stickman_video_path")
    if not relative_path:
        raise FileNotFoundError(f"Lesson asset {asset_id!r} does not have a stickman video path.")

    video_path = (_repo_root() / relative_path).resolve()
    repo_root = _repo_root().resolve()

    if repo_root not in video_path.parents and video_path != repo_root:
        raise FileNotFoundError(f"Resolved stickman video path for {asset_id!r} is outside the repository.")

    if not video_path.exists():
        raise FileNotFoundError(f"Stickman video file not found for {asset_id!r}: {video_path}")

    return video_path


def get_landmark_clip(asset_id: str, *, fps: float = 8.0) -> LessonLandmarkClipResponse:
    entry = _load_catalog_entries().get(asset_id)
    if not entry:
        raise FileNotFoundError(f"Lesson asset {asset_id!r} was not found in the lesson catalog.")

    relative_path = entry.get("landmark_path")
    if not relative_path:
        raise FileNotFoundError(f"Lesson asset {asset_id!r} does not have a landmark path.")

    landmark_path = (_repo_root() / relative_path).resolve()
    repo_root = _repo_root().resolve()
    if repo_root not in landmark_path.parents and landmark_path != repo_root:
        raise FileNotFoundError(f"Resolved landmark path for {asset_id!r} is outside the repository.")
    if not landmark_path.exists():
        raise FileNotFoundError(f"Landmark file not found for {asset_id!r}: {landmark_path}")

    raw_sequence = load_landmark_sequence(landmark_path)
    frames: list[LandmarkFrameResponse] = []
    for raw_frame in raw_sequence:
        if not isinstance(raw_frame, dict):
            continue

        pose = _normalize_frame_points(raw_frame.get("pose"))
        left_hand = _normalize_frame_points(raw_frame.get("left_hand"))
        right_hand = _normalize_frame_points(raw_frame.get("right_hand"))
        frames.append(
            LandmarkFrameResponse(
                pose=pose,
                leftHand=left_hand,
                rightHand=right_hand,
            )
        )

    if not frames:
        raise FileNotFoundError(f"Landmark file for {asset_id!r} did not contain any usable frames.")

    return LessonLandmarkClipResponse(
        asset_id=asset_id,
        label=entry.get("label", asset_id),
        fps=fps,
        source=entry.get("source", "cleaned_lesson_catalog"),
        frame_count=len(frames),
        landmark_path=relative_path,
        frames=frames,
    )


def _normalize_frame_points(raw_points: object) -> list[list[float]]:
    normalized: list[list[float]] = []
    if isinstance(raw_points, tuple):
        raw_points = list(raw_points)
    if hasattr(raw_points, "tolist") and not isinstance(raw_points, list):
        raw_points = raw_points.tolist()
    if not isinstance(raw_points, list):
        return normalized

    for point in raw_points:
        if isinstance(point, tuple):
            point = list(point)
        if hasattr(point, "tolist") and not isinstance(point, list):
            point = point.tolist()
        if not isinstance(point, list) or len(point) < 3:
            continue
        normalized.append([float(point[0]), float(point[1]), float(point[2])])

    return normalized
