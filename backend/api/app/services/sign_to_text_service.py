from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np

from ..core.config import settings
from ..integrations.mediapipe_sign_client import (
    extract_landmark_sequence_from_video_bytes,
    is_supported_sign_video_filename,
)
from ..schemas.requests import (
    SignSequenceToTextRequest,
    SignToTextRequest,
    SignUploadToTextRequest,
    TextToKslRequest,
    TextToSpeechRequest,
)
from ..schemas.responses import (
    SignMatchCandidate,
    SignSequenceItemResponse,
    SignSequenceToTextResponse,
    SignToTextResponse,
    TextToSpeechResponse,
)
from .sign_recognizer import (
    SIGN_RECOGNIZER_MODEL_ID,
    SignPredictionResult,
    _load_lesson_asset_lookup,
    predict_sign_from_landmark_path,
    predict_sign_from_sequence,
    resolve_project_path,
)
from .speech_service import synthesize_speech
from .text_to_ksl_service import map_text_to_ksl


@dataclass(frozen=True)
class PreparedSignSource:
    source_kind: str
    source_landmark_path: str | None = None
    source_upload_filename: str | None = None
    extracted_frame_count: int | None = None


def recognize_sign(request: SignToTextRequest) -> SignToTextResponse:
    if request.video_url:
        raise ValueError(
            "Remote video_url sign recognition is not connected yet. "
            "Upload a video file to `/api/v1/sign-to-text-upload` or provide "
            "`landmark_path` or `lesson_asset_id`."
        )

    landmark_path_value = _resolve_request_landmark_path(request)
    landmark_path = resolve_project_path(landmark_path_value)
    if landmark_path.suffix.lower() != ".npy":
        raise ValueError("Sign-to-text currently supports only .npy landmark files.")
    if not landmark_path.exists():
        raise ValueError(f"Landmark file not found: {landmark_path_value}")

    prediction = predict_sign_from_landmark_path(
        landmark_path,
        top_k=_resolve_top_k(request.top_k),
    )
    source_kind = "lesson_asset_id" if request.lesson_asset_id else "landmark_path"
    return _build_sign_response(
        prediction,
        source=PreparedSignSource(
            source_kind=source_kind,
            source_landmark_path=landmark_path_value,
        ),
        include_speech=request.include_speech,
        voice_id=request.voice_id,
        output_format=request.output_format,
        session_id=request.session_id,
    )


def recognize_uploaded_sign(request: SignUploadToTextRequest) -> SignToTextResponse:
    if not request.file_bytes:
        raise ValueError("Uploaded sign file is empty.")

    sequence, source = _load_uploaded_sign_sequence(request)
    prediction = predict_sign_from_sequence(
        sequence,
        top_k=_resolve_top_k(request.top_k),
    )
    return _build_sign_response(
        prediction,
        source=source,
        include_speech=request.include_speech,
        voice_id=request.voice_id,
        output_format=request.output_format,
        session_id=request.session_id,
    )


def recognize_sign_sequence(request: SignSequenceToTextRequest) -> SignSequenceToTextResponse:
    if not request.items:
        raise ValueError("Provide at least one sign item for sign-sequence-to-text recognition.")

    item_results: list[SignToTextResponse] = []

    for item in request.items:
        item_result = recognize_sign(
            SignToTextRequest(
                landmark_path=item.landmark_path,
                lesson_asset_id=item.lesson_asset_id,
                top_k=request.top_k,
                include_speech=False,
                session_id=request.session_id,
            )
        )
        item_results.append(item_result)

    return _build_sign_sequence_response(
        item_results,
        include_ksl=request.include_ksl,
        include_speech=request.include_speech,
        voice_id=request.voice_id,
        output_format=request.output_format,
        session_id=request.session_id,
    )


def recognize_uploaded_sign_sequence(
    requests: list[SignUploadToTextRequest],
    *,
    include_ksl: bool,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
) -> SignSequenceToTextResponse:
    if not requests:
        raise ValueError("Provide at least one uploaded sign file for sign-sequence-to-text.")

    item_results: list[SignToTextResponse] = []
    for request in requests:
        item_results.append(recognize_uploaded_sign(request))

    return _build_sign_sequence_response(
        item_results,
        include_ksl=include_ksl,
        include_speech=include_speech,
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )


def _build_sign_sequence_response(
    item_results: list[SignToTextResponse],
    *,
    include_ksl: bool,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
) -> SignSequenceToTextResponse:
    labels = [item_result.label for item_result in item_results if item_result.label]
    sequence_text = " ".join(labels).strip()
    normalized_text = sequence_text.lower()
    text_to_ksl = (
        map_text_to_ksl(TextToKslRequest(text=sequence_text))
        if include_ksl and sequence_text
        else None
    )
    speech = _maybe_synthesize_sign_speech(
        sequence_text,
        include_speech=include_speech and bool(sequence_text),
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )

    if text_to_ksl is None or text_to_ksl.status == "ok":
        status = "ok"
    else:
        status = "partial"

    return SignSequenceToTextResponse(
        text=sequence_text,
        normalized_text=normalized_text,
        sign_count=len(item_results),
        items=[
            SignSequenceItemResponse(
                index=index,
                label=item_result.label,
                confidence=item_result.confidence,
                text=item_result.text,
                source_kind=item_result.source_kind,
                source_landmark_path=item_result.source_landmark_path,
                matched_landmark_path=item_result.matched_landmark_path,
                lesson_asset_id=item_result.lesson_asset_id,
                top_matches=item_result.top_matches,
                status=item_result.status,
            )
            for index, item_result in enumerate(item_results)
        ],
        provider="dataset_knn",
        model_id="dataset-sign-sequence-v1",
        text_to_ksl=text_to_ksl,
        speech=speech,
        status=status,
    )


def _load_uploaded_sign_sequence(
    request: SignUploadToTextRequest,
) -> tuple[np.ndarray, PreparedSignSource]:
    filename = (request.filename or "").strip() or None
    content_type = (request.content_type or "").strip().lower()

    if _is_npy_upload(filename, content_type):
        sequence = _load_uploaded_landmark_sequence(request.file_bytes)
        return sequence, PreparedSignSource(
            source_kind="uploaded_landmark_file",
            source_upload_filename=filename,
            extracted_frame_count=int(len(sequence)),
        )

    if _is_video_upload(filename, content_type):
        sequence = extract_landmark_sequence_from_video_bytes(
            request.file_bytes,
            filename=filename,
        )
        return sequence, PreparedSignSource(
            source_kind="uploaded_video",
            source_upload_filename=filename,
            extracted_frame_count=int(len(sequence)),
        )

    raise ValueError(
        "Unsupported uploaded sign file. Use a `.npy` landmark file or a video file "
        "such as `.mp4`, `.mov`, `.webm`, `.m4v`, `.mkv`, or `.avi`."
    )


def _load_uploaded_landmark_sequence(file_bytes: bytes) -> np.ndarray:
    try:
        sequence = np.load(BytesIO(file_bytes), allow_pickle=True)
    except Exception as exc:
        raise ValueError(f"Unable to load the uploaded landmark .npy file: {exc}") from exc

    normalized_sequence = np.asarray(sequence, dtype=object)
    if normalized_sequence.ndim == 0:
        raise ValueError("Uploaded landmark file did not contain a frame sequence.")
    if len(normalized_sequence) == 0:
        raise ValueError("Uploaded landmark file is empty.")
    return normalized_sequence


def _build_sign_response(
    prediction: SignPredictionResult,
    *,
    source: PreparedSignSource,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
) -> SignToTextResponse:
    recognized_text = prediction.label
    speech = _maybe_synthesize_sign_speech(
        recognized_text,
        include_speech=include_speech,
        voice_id=voice_id,
        output_format=output_format,
        session_id=session_id,
    )

    return SignToTextResponse(
        label=prediction.label,
        confidence=prediction.confidence,
        text=recognized_text,
        provider="dataset_knn",
        model_id=SIGN_RECOGNIZER_MODEL_ID,
        source_kind=source.source_kind,
        source_landmark_path=source.source_landmark_path,
        source_upload_filename=source.source_upload_filename,
        matched_landmark_path=prediction.matched_landmark_path,
        extracted_frame_count=source.extracted_frame_count,
        lesson_asset_id=prediction.lesson_asset_id,
        dataset_backed=True,
        top_matches=[
            SignMatchCandidate(
                label=match.label,
                confidence=match.confidence,
                landmark_path=match.landmark_path,
                lesson_asset_id=match.lesson_asset_id,
            )
            for match in prediction.top_matches
        ],
        speech=speech,
        status="ok",
    )


def _maybe_synthesize_sign_speech(
    text: str,
    *,
    include_speech: bool,
    voice_id: str | None,
    output_format: str | None,
    session_id: str | None,
) -> TextToSpeechResponse | None:
    if not include_speech:
        return None

    return synthesize_speech(
        TextToSpeechRequest(
            text=text,
            voice_id=voice_id,
            output_format=output_format,
            include_ksl=False,
            session_id=session_id,
        )
    )


def _resolve_request_landmark_path(request: SignToTextRequest) -> str:
    if request.landmark_path:
        return request.landmark_path

    if request.lesson_asset_id:
        lesson_assets = _load_lesson_asset_lookup()
        for asset in lesson_assets.values():
            if asset.get("asset_id") == request.lesson_asset_id:
                landmark_path = asset.get("landmark_path")
                if landmark_path:
                    return str(landmark_path)
                break
        raise ValueError(f"lesson_asset_id not found in lesson catalog: {request.lesson_asset_id}")

    raise ValueError("Provide landmark_path or lesson_asset_id for sign-to-text recognition.")


def _resolve_top_k(top_k: int | None) -> int:
    return max(1, top_k or settings.sign_recognizer_default_top_k)


def _is_npy_upload(filename: str | None, content_type: str) -> bool:
    if filename and filename.lower().endswith(".npy"):
        return True
    return content_type in {"application/x-npy", "application/npy"}


def _is_video_upload(filename: str | None, content_type: str) -> bool:
    if content_type.startswith("video/"):
        return True
    return is_supported_sign_video_filename(filename)
