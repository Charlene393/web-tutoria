from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...schemas.responses import LessonLandmarkClipResponse
from ...services.lesson_asset_service import get_landmark_clip, get_stickman_video_file

router = APIRouter(tags=["lesson-assets"])


@router.get("/lesson-assets/{asset_id}/stickman-video")
def lesson_asset_stickman_video(asset_id: str) -> FileResponse:
    try:
        video_path = get_stickman_video_file(asset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(video_path, media_type="video/mp4", filename=video_path.name)


@router.get("/lesson-assets/{asset_id}/landmark-clip", response_model=LessonLandmarkClipResponse)
def lesson_asset_landmark_clip(asset_id: str) -> LessonLandmarkClipResponse:
    try:
        return get_landmark_clip(asset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
