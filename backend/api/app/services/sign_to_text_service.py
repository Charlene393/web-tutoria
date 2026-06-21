from ..core.config import settings
from ..schemas.requests import SignToTextRequest
from ..schemas.responses import SignMatchCandidate, SignToTextResponse
from .sign_recognizer import (
    _load_lesson_asset_lookup,
    predict_sign_from_landmark_path,
    resolve_project_path,
)

def recognize_sign(request: SignToTextRequest) -> SignToTextResponse:
    if request.video_url:
        raise ValueError(
            "video_url sign recognition is not connected yet. "
            "Use landmark_path or lesson_asset_id for the backend MVP."
        )

    landmark_path_value = _resolve_request_landmark_path(request)
    landmark_path = resolve_project_path(landmark_path_value)
    if landmark_path.suffix.lower() != ".npy":
        raise ValueError("Sign-to-text currently supports only .npy landmark files.")
    if not landmark_path.exists():
        raise ValueError(f"Landmark file not found: {landmark_path_value}")

    prediction = predict_sign_from_landmark_path(
        landmark_path,
        top_k=max(1, request.top_k or settings.sign_recognizer_default_top_k),
    )

    return SignToTextResponse(
        label=prediction.label,
        confidence=prediction.confidence,
        text=prediction.label,
        provider="dataset_knn",
        model_id="dataset-sign-knn-v1",
        source_landmark_path=landmark_path_value,
        matched_landmark_path=prediction.matched_landmark_path,
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
        status="ok",
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
