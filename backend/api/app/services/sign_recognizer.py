from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..core.config import settings
from .sign_features import (
    SIGN_FEATURE_VERSION,
    extract_sign_feature_vector,
    extract_sign_feature_vector_from_path,
)

SIGN_RECOGNIZER_MODEL_ID = "dataset-sign-knn-v1"
ARTIFACT_FILE_NAME = "ksl_sign_recognizer_v1.npz"


@dataclass(frozen=True)
class SignRecognizerArtifact:
    model_id: str
    feature_version: str
    target_frames: int
    label_set_name: str | None
    features: np.ndarray
    labels: tuple[str, ...]
    landmark_paths: tuple[str, ...]
    label_counts: dict[str, int]
    manifest_path: str
    artifact_path: str
    label_set_path: str | None
    generated_at: str


@dataclass(frozen=True)
class SignPredictionCandidate:
    label: str
    confidence: float
    similarity: float
    landmark_path: str
    lesson_asset_id: str | None = None


@dataclass(frozen=True)
class SignPredictionResult:
    label: str
    confidence: float
    matched_landmark_path: str
    lesson_asset_id: str | None
    top_matches: list[SignPredictionCandidate]


def build_sign_recognizer_artifact(
    *,
    manifest_path: Path | None = None,
    artifact_path: Path | None = None,
    label_set_path: Path | None = None,
    min_samples_per_label: int | None = None,
    target_frames: int | None = None,
) -> SignRecognizerArtifact:
    resolved_manifest_path = manifest_path or default_manifest_path()
    resolved_artifact_path = artifact_path or default_artifact_path()
    resolved_label_set_path = label_set_path if label_set_path is not None else default_label_set_path()
    feature_frames = target_frames or settings.sign_recognizer_target_frames
    minimum_samples = (
        min_samples_per_label
        if min_samples_per_label is not None
        else settings.sign_recognizer_min_samples_per_label
    )
    label_set_name, allowed_labels, label_set_hash = load_sign_label_set(resolved_label_set_path)

    if not resolved_manifest_path.exists():
        raise RuntimeError(
            f"Cleaned sign manifest not found at {resolved_manifest_path}. "
            "Run backend/scripts/apply_cleanup_decisions_to_manifest.py first."
        )

    rows = list(_read_manifest_rows(resolved_manifest_path))
    if not rows:
        raise RuntimeError(f"No rows found in cleaned sign manifest at {resolved_manifest_path}.")

    label_counts = Counter(row["label"] for row in rows)
    filtered_rows = [
        row
        for row in rows
        if row["label"]
        and label_counts[row["label"]] >= minimum_samples
        and (allowed_labels is None or row["label"] in allowed_labels)
    ]
    if not filtered_rows:
        raise RuntimeError(
            "No cleaned sign samples remain after applying the min_samples_per_label filter."
        )

    features: list[np.ndarray] = []
    labels: list[str] = []
    landmark_paths: list[str] = []
    skipped_rows = 0

    for row in filtered_rows:
        landmark_path_value = row.get("landmark_path", "").strip()
        if not landmark_path_value:
            skipped_rows += 1
            continue

        landmark_path = resolve_project_path(landmark_path_value)
        if not landmark_path.exists():
            skipped_rows += 1
            continue

        try:
            feature_vector, _ = extract_sign_feature_vector_from_path(
                landmark_path,
                target_frames=feature_frames,
            )
        except ValueError:
            skipped_rows += 1
            continue

        features.append(feature_vector)
        labels.append(row["label"])
        landmark_paths.append(landmark_path_value)

    if not features:
        raise RuntimeError(
            "Unable to build the sign recognizer because no usable landmark sequences were found."
        )

    feature_matrix = np.stack(features, axis=0).astype(np.float32, copy=False)
    resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)

    artifact_label_counts = dict(Counter(labels))
    metadata = {
        "model_id": SIGN_RECOGNIZER_MODEL_ID,
        "feature_version": SIGN_FEATURE_VERSION,
        "target_frames": feature_frames,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": _display_path(resolved_manifest_path),
        "artifact_path": _display_path(resolved_artifact_path),
        "label_set_name": label_set_name,
        "label_set_path": _display_path(resolved_label_set_path) if resolved_label_set_path else None,
        "label_set_hash": label_set_hash,
        "total_samples": int(feature_matrix.shape[0]),
        "total_labels": len(artifact_label_counts),
        "skipped_rows": skipped_rows,
        "min_samples_per_label": minimum_samples,
        "label_counts": artifact_label_counts,
    }
    np.savez_compressed(
        resolved_artifact_path,
        features=feature_matrix,
        labels=np.asarray(labels),
        landmark_paths=np.asarray(landmark_paths),
        metadata_json=np.asarray(json.dumps(metadata)),
    )

    clear_sign_recognizer_cache()
    return load_sign_recognizer(
        artifact_path=resolved_artifact_path,
        manifest_path=resolved_manifest_path,
    )


def load_sign_recognizer(
    *,
    artifact_path: Path | None = None,
    manifest_path: Path | None = None,
) -> SignRecognizerArtifact:
    resolved_artifact_path = artifact_path or default_artifact_path()
    resolved_manifest_path = manifest_path or default_manifest_path()
    return _load_sign_recognizer_cached(
        str(resolved_artifact_path),
        str(resolved_manifest_path),
    )


def clear_sign_recognizer_cache() -> None:
    _load_sign_recognizer_cached.cache_clear()
    _load_lesson_asset_lookup.cache_clear()


def predict_sign_from_landmark_path(
    landmark_path: Path,
    *,
    top_k: int,
    artifact_path: Path | None = None,
    manifest_path: Path | None = None,
) -> SignPredictionResult:
    recognizer = load_sign_recognizer(
        artifact_path=artifact_path,
        manifest_path=manifest_path,
    )
    query_features, _ = extract_sign_feature_vector_from_path(
        landmark_path,
        target_frames=recognizer.target_frames,
    )
    return predict_sign_from_feature_vector(
        query_features,
        top_k=top_k,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
    )


def predict_sign_from_sequence(
    sequence: np.ndarray,
    *,
    top_k: int,
    artifact_path: Path | None = None,
    manifest_path: Path | None = None,
) -> SignPredictionResult:
    recognizer = load_sign_recognizer(
        artifact_path=artifact_path,
        manifest_path=manifest_path,
    )
    query_features, _ = extract_sign_feature_vector(
        sequence,
        target_frames=recognizer.target_frames,
    )
    return predict_sign_from_feature_vector(
        query_features,
        top_k=top_k,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
    )


def predict_sign_from_feature_vector(
    query_features: np.ndarray,
    *,
    top_k: int,
    artifact_path: Path | None = None,
    manifest_path: Path | None = None,
) -> SignPredictionResult:
    recognizer = load_sign_recognizer(
        artifact_path=artifact_path,
        manifest_path=manifest_path,
    )
    similarities = recognizer.features @ query_features
    if similarities.size == 0:
        raise RuntimeError("The sign recognizer artifact is empty.")

    lesson_assets = _load_lesson_asset_lookup()
    best_by_label: dict[str, tuple[float, str]] = {}
    for index, similarity in enumerate(similarities.tolist()):
        label = recognizer.labels[index]
        landmark_path_value = recognizer.landmark_paths[index]
        current = best_by_label.get(label)
        if current is None or similarity > current[0]:
            best_by_label[label] = (float(similarity), landmark_path_value)

    ranked = sorted(best_by_label.items(), key=lambda item: item[1][0], reverse=True)
    limited_matches = ranked[: max(1, top_k)]

    top_matches = [
        SignPredictionCandidate(
            label=label,
            similarity=similarity,
            confidence=_similarity_to_confidence(similarity),
            landmark_path=landmark_path_value,
            lesson_asset_id=lesson_assets.get(label, {}).get("asset_id"),
        )
        for label, (similarity, landmark_path_value) in limited_matches
    ]

    best_match = top_matches[0]
    return SignPredictionResult(
        label=best_match.label,
        confidence=best_match.confidence,
        matched_landmark_path=best_match.landmark_path,
        lesson_asset_id=best_match.lesson_asset_id,
        top_matches=top_matches,
    )


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return project_root() / path


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_manifest_path() -> Path:
    override = settings.sign_recognizer_manifest_path
    if override:
        return resolve_project_path(override)
    return project_root() / "backend/reports/ksl_cleanup/cleaned/manifest.csv"


def default_artifact_path() -> Path:
    override = settings.sign_recognizer_artifact_path
    if override:
        return resolve_project_path(override)
    return Path(__file__).resolve().parents[1] / "data" / ARTIFACT_FILE_NAME


def default_label_set_path() -> Path | None:
    override = settings.sign_recognizer_label_set_path
    if override:
        return resolve_project_path(override)

    bundled_path = Path(__file__).resolve().parents[1] / "data" / "ksl_sign_v1_labels.json"
    if bundled_path.exists():
        return bundled_path
    return None


@lru_cache(maxsize=1)
def _load_lesson_asset_lookup() -> dict[str, dict[str, str]]:
    catalog_path = Path(__file__).resolve().parents[1] / "data" / "ksl_lesson_catalog.json"
    if not catalog_path.exists():
        return {}

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {
        entry["label"]: entry
        for entry in catalog.get("entries", [])
        if entry.get("label")
    }


@lru_cache(maxsize=4)
def _load_sign_recognizer_cached(
    artifact_path_str: str,
    manifest_path_str: str,
) -> SignRecognizerArtifact:
    artifact_path = Path(artifact_path_str)
    manifest_path = Path(manifest_path_str)
    label_set_path = default_label_set_path()
    current_label_set_name, _allowed_labels, current_label_set_hash = load_sign_label_set(label_set_path)

    should_rebuild = not artifact_path.exists()
    if not should_rebuild:
        with np.load(artifact_path, allow_pickle=False) as existing_data:
            existing_metadata = json.loads(str(existing_data["metadata_json"].item()))
        should_rebuild = (
            int(existing_metadata.get("target_frames", settings.sign_recognizer_target_frames))
            != settings.sign_recognizer_target_frames
            or str(existing_metadata.get("label_set_hash", ""))
            != str(current_label_set_hash or "")
            or int(existing_metadata.get("min_samples_per_label", settings.sign_recognizer_min_samples_per_label))
            != settings.sign_recognizer_min_samples_per_label
        )

    if should_rebuild:
        build_sign_recognizer_artifact(
            manifest_path=manifest_path,
            artifact_path=artifact_path,
            label_set_path=label_set_path,
            min_samples_per_label=settings.sign_recognizer_min_samples_per_label,
            target_frames=settings.sign_recognizer_target_frames,
        )

    with np.load(artifact_path, allow_pickle=False) as data:
        features = data["features"].astype(np.float32, copy=False)
        labels = tuple(str(value) for value in data["labels"].tolist())
        landmark_paths = tuple(str(value) for value in data["landmark_paths"].tolist())
        metadata = json.loads(str(data["metadata_json"].item()))

    return SignRecognizerArtifact(
        model_id=str(metadata.get("model_id", SIGN_RECOGNIZER_MODEL_ID)),
        feature_version=str(metadata.get("feature_version", SIGN_FEATURE_VERSION)),
        target_frames=int(metadata.get("target_frames", settings.sign_recognizer_target_frames)),
        label_set_name=str(metadata.get("label_set_name")) if metadata.get("label_set_name") else current_label_set_name,
        features=features,
        labels=labels,
        landmark_paths=landmark_paths,
        label_counts={str(key): int(value) for key, value in metadata.get("label_counts", {}).items()},
        manifest_path=str(metadata.get("manifest_path", _display_path(manifest_path))),
        artifact_path=str(metadata.get("artifact_path", _display_path(artifact_path))),
        label_set_path=str(metadata.get("label_set_path")) if metadata.get("label_set_path") else (_display_path(label_set_path) if label_set_path else None),
        generated_at=str(metadata.get("generated_at", "")),
    )


def load_sign_label_set(label_set_path: Path | None) -> tuple[str | None, set[str] | None, str | None]:
    if label_set_path is None:
        return None, None, None

    if not label_set_path.exists():
        raise RuntimeError(
            f"Configured sign label set file was not found: {label_set_path}"
        )

    data = json.loads(label_set_path.read_text(encoding="utf-8"))
    labels = data.get("labels")
    if not isinstance(labels, list) or not labels:
        raise RuntimeError(
            f"Sign label set at {label_set_path} must define a non-empty `labels` list."
        )

    normalized_labels = [str(label).strip().upper() for label in labels if str(label).strip()]
    if not normalized_labels:
        raise RuntimeError(
            f"Sign label set at {label_set_path} did not contain any usable labels."
        )

    label_set_name = str(data.get("label_set_name") or label_set_path.stem)
    label_set_hash = hashlib.sha256(
        "\n".join(sorted(normalized_labels)).encode("utf-8")
    ).hexdigest()
    return label_set_name, set(normalized_labels), label_set_hash


def _read_manifest_rows(manifest_path: Path):
    with manifest_path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            label = (row.get("label") or "").strip()
            landmark_path = (row.get("landmark_path") or "").strip()
            if not label or not landmark_path:
                continue
            yield {
                "label": label,
                "landmark_path": landmark_path,
            }


def _similarity_to_confidence(similarity: float) -> float:
    base_confidence = float(np.clip((similarity + 1.0) / 2.0, 0.0, 1.0))
    return round(base_confidence, 4)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(project_root()))
    except ValueError:
        return str(path)
