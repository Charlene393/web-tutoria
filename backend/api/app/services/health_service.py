from __future__ import annotations

import importlib.util
import platform
from pathlib import Path

from ..core.config import settings
from ..integrations.faster_whisper_client import get_faster_whisper_model
from ..integrations.kokoro_client import get_kokoro_pipeline
from ..schemas.responses import HealthResponse, ReadinessCheck
from .sign_recognizer import (
    default_artifact_path,
    default_label_set_path,
    default_manifest_path,
    project_root,
)


def build_health_response() -> HealthResponse:
    checks = {
        "lesson_catalog": _check_path(
            _lesson_catalog_path(),
            required=True,
            missing_detail=(
                "KSL lesson catalog is missing. Run "
                "`backend/scripts/build_ksl_lesson_catalog.py`."
            ),
        ),
        "sign_recognizer_manifest": _check_path(
            default_manifest_path(),
            required=True,
            missing_detail=(
                "Cleaned sign manifest is missing. Run "
                "`backend/scripts/apply_cleanup_decisions_to_manifest.py`."
            ),
        ),
        "sign_recognizer_label_set": _check_optional_path(
            default_label_set_path(),
            required=True,
            missing_detail="Bundled sign label set file is missing.",
        ),
        "sign_recognizer_artifact": _check_sign_artifact(),
        "kokoro": _check_runtime_dependency(
            get_kokoro_pipeline,
            missing_package="kokoro",
            success_detail="Kokoro pipeline initialized successfully.",
        ),
        "faster_whisper": _check_runtime_dependency(
            get_faster_whisper_model,
            missing_package="faster_whisper",
            success_detail="faster-whisper model initialized successfully.",
        ),
        "sign_video_model": _check_sign_video_model(),
    }

    status = "ok" if all(check.ready for check in checks.values() if check.required) else "partial"
    return HealthResponse(
        status=status,
        app_name=settings.app_name,
        app_version=settings.app_version,
        checks=checks,
    )


def _lesson_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ksl_lesson_catalog.json"


def _resolve_sign_video_model_path() -> Path:
    override = settings.sign_video_mediapipe_model_path
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else project_root() / path
    return Path(__file__).resolve().parents[1] / "data" / "holistic_landmarker.task"


def _check_path(path: Path, *, required: bool, missing_detail: str) -> ReadinessCheck:
    if path.exists():
        return ReadinessCheck(
            ready=True,
            required=required,
            path=_display_path(path),
            detail="Present.",
        )

    return ReadinessCheck(
        ready=False,
        required=required,
        path=_display_path(path),
        detail=missing_detail,
    )


def _check_optional_path(
    path: Path | None,
    *,
    required: bool,
    missing_detail: str,
) -> ReadinessCheck:
    if path is None:
        return ReadinessCheck(
            ready=False,
            required=required,
            path=None,
            detail=missing_detail,
        )
    return _check_path(path, required=required, missing_detail=missing_detail)


def _check_sign_artifact() -> ReadinessCheck:
    artifact_path = default_artifact_path()
    if artifact_path.exists():
        return ReadinessCheck(
            ready=True,
            required=False,
            path=_display_path(artifact_path),
            detail="Recognizer artifact is present.",
        )

    manifest_ready = default_manifest_path().exists()
    label_set_ready = default_label_set_path() is not None and default_label_set_path().exists()
    detail = (
        "Recognizer artifact is missing, but it can be auto-built on first sign recognition "
        "request because the cleaned manifest and label set are present."
        if manifest_ready and label_set_ready
        else "Recognizer artifact is missing and may not be auto-buildable yet."
    )
    return ReadinessCheck(
        ready=manifest_ready and label_set_ready,
        required=False,
        path=_display_path(artifact_path),
        detail=detail,
    )


def _check_runtime_dependency(
    loader,
    *,
    missing_package: str,
    success_detail: str,
) -> ReadinessCheck:
    if not _module_available(missing_package):
        return ReadinessCheck(
            ready=False,
            required=True,
            path=None,
            detail=(
                f"The `{missing_package}` package is not installed in this backend environment."
            ),
        )

    try:
        loader()
    except RuntimeError as exc:
        return ReadinessCheck(
            ready=False,
            required=True,
            path=None,
            detail=str(exc),
        )
    except Exception as exc:
        return ReadinessCheck(
            ready=False,
            required=True,
            path=None,
            detail=f"Unexpected initialization failure: {exc}",
        )

    return ReadinessCheck(
        ready=True,
        required=True,
        path=None,
        detail=success_detail,
    )


def _check_sign_video_model() -> ReadinessCheck:
    model_path = _resolve_sign_video_model_path()
    if platform.system() == "Darwin":
        detail = (
            "Raw MediaPipe sign-video extraction is treated as optional on macOS because the "
            "current task runtime is not stable in this local backend environment."
        )
        if model_path.exists():
            detail = f"{detail} The model file is present if you later test this on Linux."
        return ReadinessCheck(
            ready=model_path.exists(),
            required=False,
            path=_display_path(model_path),
            detail=detail,
        )

    if model_path.exists():
        return ReadinessCheck(
            ready=True,
            required=False,
            path=_display_path(model_path),
            detail="Optional MediaPipe sign-video model is present.",
        )

    return ReadinessCheck(
        ready=False,
        required=False,
        path=_display_path(model_path),
        detail=(
            "Optional MediaPipe sign-video model is missing. Run "
            "`bash download-sign-video-model.sh` if you want sign-video extraction."
        ),
    )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(project_root()))
    except ValueError:
        return str(path)
