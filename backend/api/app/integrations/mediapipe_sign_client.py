from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from ..core.config import settings

SUPPORTED_SIGN_VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
}


def is_supported_sign_video_filename(filename: str | None) -> bool:
    if not filename:
        return False
    return Path(filename).suffix.lower() in SUPPORTED_SIGN_VIDEO_EXTENSIONS


def extract_landmark_sequence_from_video_bytes(
    video_bytes: bytes,
    *,
    filename: str | None = None,
) -> np.ndarray:
    if not video_bytes:
        raise ValueError("Uploaded sign video is empty.")

    av = _import_av_module()
    mp = _import_mediapipe_module()

    suffix = Path(filename or "sign-video.mp4").suffix or ".mp4"
    temp_path: str | None = None

    try:
        with NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_file.write(video_bytes)
            temp_path = temp_file.name

        container = av.open(temp_path)
        try:
            video_stream = next((stream for stream in container.streams if stream.type == "video"), None)
            if video_stream is None:
                raise ValueError("Uploaded file does not contain a readable video stream.")

            frame_step = _resolve_frame_step(video_stream)
            sequence: list[dict[str, list[list[float]]]] = []
            sampled_frame_index = 0

            with mp.solutions.holistic.Holistic(
                static_image_mode=False,
                model_complexity=settings.sign_video_model_complexity,
                smooth_landmarks=True,
                min_detection_confidence=settings.sign_video_min_detection_confidence,
                min_tracking_confidence=settings.sign_video_min_tracking_confidence,
            ) as holistic:
                for decoded_index, frame in enumerate(container.decode(video=video_stream.index)):
                    if decoded_index % frame_step != 0:
                        continue

                    rgb_frame = frame.to_ndarray(format="rgb24")
                    results = holistic.process(rgb_frame)
                    sequence_frame = {
                        "pose": _landmark_list_to_points(getattr(results, "pose_landmarks", None)),
                        "left_hand": _landmark_list_to_points(
                            getattr(results, "left_hand_landmarks", None)
                        ),
                        "right_hand": _landmark_list_to_points(
                            getattr(results, "right_hand_landmarks", None)
                        ),
                        "face": [],
                    }
                    if _frame_has_sign_signal(sequence_frame):
                        sequence.append(sequence_frame)

                    sampled_frame_index += 1
                    if sampled_frame_index >= settings.sign_video_max_frames:
                        break
        finally:
            container.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Unable to read the uploaded sign video: {exc}") from exc
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)

    if not sequence:
        raise ValueError(
            "No pose or hand landmarks were detected in the uploaded video. "
            "Record a clearer clip with the signer centered and both hands visible."
        )

    return np.asarray(sequence, dtype=object)


def _resolve_frame_step(video_stream: Any) -> int:
    average_rate = getattr(video_stream, "average_rate", None)
    if average_rate is None:
        return 1

    try:
        fps = float(average_rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return 1

    if fps <= 0:
        return 1

    target_fps = max(settings.sign_video_target_fps, 1.0)
    return max(1, int(round(fps / target_fps)))


def _landmark_list_to_points(landmark_list: Any) -> list[list[float]]:
    if landmark_list is None or getattr(landmark_list, "landmark", None) is None:
        return []

    return [
        [float(point.x), float(point.y), float(point.z)]
        for point in landmark_list.landmark
    ]


def _frame_has_sign_signal(frame: dict[str, list[list[float]]]) -> bool:
    return bool(frame["pose"] or frame["left_hand"] or frame["right_hand"])


def _import_av_module():
    try:
        import av
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The `av` package is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-sign-video.txt`."
        ) from exc

    return av


def _import_mediapipe_module():
    try:
        import mediapipe as mp
    except (ModuleNotFoundError, ImportError) as exc:
        raise RuntimeError(
            "MediaPipe is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-sign-video.txt`."
        ) from exc

    return mp
