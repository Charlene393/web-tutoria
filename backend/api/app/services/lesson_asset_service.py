from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


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
