from __future__ import annotations

import os
import platform
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir
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
HOLISTIC_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "holistic_landmarker/holistic_landmarker/float16/latest/holistic_landmarker.task"
)


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

            if _has_legacy_mediapipe_solutions(mp):
                sequence = _extract_sequence_with_legacy_solutions(
                    mp,
                    container=container,
                    video_stream=video_stream,
                    frame_step=frame_step,
                )
            elif _has_tasks_holistic_landmarker(mp):
                sequence = _extract_sequence_with_tasks_api(
                    mp,
                    container=container,
                    video_stream=video_stream,
                    frame_step=frame_step,
                )
            else:
                raise RuntimeError(
                    "The installed MediaPipe package does not expose either the legacy "
                    "`solutions.holistic` API or the newer `tasks.vision.HolisticLandmarker` API."
                )
        finally:
            container.close()
    except (RuntimeError, ValueError):
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


def _extract_sequence_with_legacy_solutions(
    mp: Any,
    *,
    container: Any,
    video_stream: Any,
    frame_step: int,
) -> list[dict[str, list[list[float]]]]:
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
                "pose": _legacy_landmark_list_to_points(getattr(results, "pose_landmarks", None)),
                "left_hand": _legacy_landmark_list_to_points(
                    getattr(results, "left_hand_landmarks", None)
                ),
                "right_hand": _legacy_landmark_list_to_points(
                    getattr(results, "right_hand_landmarks", None)
                ),
                "face": [],
            }
            if _frame_has_sign_signal(sequence_frame):
                sequence.append(sequence_frame)

            sampled_frame_index += 1
            if sampled_frame_index >= settings.sign_video_max_frames:
                break

    return sequence


def _extract_sequence_with_tasks_api(
    mp: Any,
    *,
    container: Any,
    video_stream: Any,
    frame_step: int,
) -> list[dict[str, list[list[float]]]]:
    if platform.system() == "Darwin":
        raise RuntimeError(
            "The current MediaPipe tasks runtime is not stable for sign-video extraction "
            "in this macOS backend environment. It attempts to initialize a Metal-based "
            "graphics service and can crash the process. Use uploaded `.npy` landmark files "
            "on macOS for now, or run sign-video landmark extraction on Linux or another "
            "non-macOS environment."
        )

    model_path = _resolve_holistic_landmarker_model_path()
    vision = mp.tasks.vision
    base_options = mp.tasks.BaseOptions(
        model_asset_path=str(model_path),
        delegate=mp.tasks.BaseOptions.Delegate.CPU,
    )
    options = vision.HolisticLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        min_face_detection_confidence=settings.sign_video_min_detection_confidence,
        min_face_landmarks_confidence=settings.sign_video_min_tracking_confidence,
        min_pose_detection_confidence=settings.sign_video_min_detection_confidence,
        min_pose_landmarks_confidence=settings.sign_video_min_tracking_confidence,
        min_hand_landmarks_confidence=settings.sign_video_min_tracking_confidence,
    )

    sequence: list[dict[str, list[list[float]]]] = []
    sampled_frame_index = 0
    video_fps = _resolve_video_fps(video_stream)
    last_timestamp_ms = -1

    with vision.HolisticLandmarker.create_from_options(options) as holistic:
        for decoded_index, frame in enumerate(container.decode(video=video_stream.index)):
            if decoded_index % frame_step != 0:
                continue

            rgb_frame = frame.to_ndarray(format="rgb24")
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = _resolve_frame_timestamp_ms(
                frame=frame,
                decoded_index=decoded_index,
                sampled_frame_index=sampled_frame_index,
                video_fps=video_fps,
            )
            if timestamp_ms <= last_timestamp_ms:
                timestamp_ms = last_timestamp_ms + 1
            last_timestamp_ms = timestamp_ms

            results = holistic.detect_for_video(mp_image, timestamp_ms)
            sequence_frame = {
                "pose": _task_landmarks_to_points(getattr(results, "pose_landmarks", None)),
                "left_hand": _task_landmarks_to_points(
                    getattr(results, "left_hand_landmarks", None)
                ),
                "right_hand": _task_landmarks_to_points(
                    getattr(results, "right_hand_landmarks", None)
                ),
                "face": [],
            }
            if _frame_has_sign_signal(sequence_frame):
                sequence.append(sequence_frame)

            sampled_frame_index += 1
            if sampled_frame_index >= settings.sign_video_max_frames:
                break

    return sequence


def _resolve_frame_step(video_stream: Any) -> int:
    fps = _resolve_video_fps(video_stream)
    if fps is None:
        return 1

    target_fps = max(settings.sign_video_target_fps, 1.0)
    return max(1, int(round(fps / target_fps)))


def _resolve_video_fps(video_stream: Any) -> float | None:
    average_rate = getattr(video_stream, "average_rate", None)
    if average_rate is None:
        return None

    try:
        fps = float(average_rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    return fps if fps > 0 else None


def _resolve_frame_timestamp_ms(
    *,
    frame: Any,
    decoded_index: int,
    sampled_frame_index: int,
    video_fps: float | None,
) -> int:
    frame_time = getattr(frame, "time", None)
    if frame_time is not None:
        try:
            frame_time_ms = int(round(float(frame_time) * 1000.0))
            if frame_time_ms >= 0:
                return frame_time_ms
        except (TypeError, ValueError):
            pass

    if video_fps and video_fps > 0:
        return int(round(decoded_index / video_fps * 1000.0))

    fallback_fps = max(settings.sign_video_target_fps, 1.0)
    return int(round(sampled_frame_index / fallback_fps * 1000.0))


def _legacy_landmark_list_to_points(landmark_list: Any) -> list[list[float]]:
    if landmark_list is None or getattr(landmark_list, "landmark", None) is None:
        return []

    return [
        [float(point.x), float(point.y), float(point.z)]
        for point in landmark_list.landmark
    ]


def _task_landmarks_to_points(landmarks: Any) -> list[list[float]]:
    if not landmarks:
        return []

    return [
        [float(point.x), float(point.y), float(point.z)]
        for point in landmarks
    ]


def _frame_has_sign_signal(frame: dict[str, list[list[float]]]) -> bool:
    return bool(frame["pose"] or frame["left_hand"] or frame["right_hand"])


def _has_legacy_mediapipe_solutions(mp: Any) -> bool:
    return bool(
        hasattr(mp, "solutions")
        and getattr(mp, "solutions", None) is not None
        and hasattr(mp.solutions, "holistic")
    )


def _has_tasks_holistic_landmarker(mp: Any) -> bool:
    tasks = getattr(mp, "tasks", None)
    vision = getattr(tasks, "vision", None) if tasks is not None else None
    return bool(vision is not None and hasattr(vision, "HolisticLandmarker"))


def _resolve_holistic_landmarker_model_path() -> Path:
    configured_path = settings.sign_video_mediapipe_model_path
    if configured_path:
        model_path = _resolve_project_path(configured_path)
    else:
        model_path = Path(__file__).resolve().parents[1] / "data" / "holistic_landmarker.task"

    if model_path.exists():
        return model_path

    raise RuntimeError(
        "MediaPipe is installed, but the Holistic Landmarker model file is missing. "
        f"Expected it at: {model_path}. "
        "Download the official `holistic_landmarker.task` file and place it there, "
        "or set SIGN_VIDEO_MEDIAPIPE_MODEL_PATH in backend/api/.env. "
        "Example download command: "
        f'curl -L "{HOLISTIC_LANDMARKER_MODEL_URL}" -o "{model_path}"'
    )


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return _project_root() / path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


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
    matplotlib_cache_dir = Path(gettempdir()) / "matplotlib"
    matplotlib_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache_dir))

    try:
        import mediapipe as mp
    except (ModuleNotFoundError, ImportError) as exc:
        raise RuntimeError(
            "MediaPipe is not installed in this backend environment. "
            "Activate backend/api/.venv and run `pip install -r requirements-sign-video.txt`."
        ) from exc

    return mp
