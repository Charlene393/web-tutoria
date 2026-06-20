from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from ..schemas.requests import TextToKslRequest
from ..schemas.responses import LessonAsset, TextToKslResponse

TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _dataset_root() -> Path:
    return _project_root() / "KSL-Dataset" / "Pose Data"


def _glossary_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ksl_glossary.json"


def _relative_to_project(path: Path) -> str:
    return str(path.relative_to(_project_root()))


def _normalize_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9'\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)


def _collapse_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@lru_cache(maxsize=1)
def _load_dataset_label_counts() -> Counter[str]:
    dataset_root = _dataset_root()
    if not dataset_root.exists():
        raise RuntimeError(f"KSL dataset not found at {dataset_root}")

    counts: Counter[str] = Counter()
    for file_path in dataset_root.glob("Batch */*/Extract/Landmarks/*.npy"):
        label = file_path.stem.strip()
        if not label or label.startswith("."):
            continue
        counts[label] += 1

    if not counts:
        raise RuntimeError(f"No landmark labels found under {dataset_root}")

    return counts


@lru_cache(maxsize=1)
def _load_dataset_label_lookup() -> dict[str, str]:
    label_counts = _load_dataset_label_counts()
    return {_collapse_token(label): label for label in label_counts}


@lru_cache(maxsize=1)
def _load_dataset_assets() -> dict[str, LessonAsset]:
    dataset_root = _dataset_root()
    label_counts = _load_dataset_label_counts()
    assets: dict[str, LessonAsset] = {}

    landmark_files = sorted(dataset_root.glob("Batch */*/Extract/Landmarks/*.npy"))

    for landmark_path in landmark_files:
        label = landmark_path.stem.strip()
        if label not in label_counts or label in assets:
            continue

        stickman_path = landmark_path.parents[1] / "Stickmans" / f"{label}.mp4"
        assets[label] = LessonAsset(
            asset_id=f"dataset-sign:{label.lower()}",
            label=label,
            sample_count=label_counts[label],
            source="dataset",
            landmark_path=_relative_to_project(landmark_path),
            stickman_video_path=_relative_to_project(stickman_path) if stickman_path.exists() else None,
        )

    return assets


@lru_cache(maxsize=1)
def _load_glossary() -> dict[str, object]:
    glossary_path = _glossary_path()
    with glossary_path.open("r", encoding="utf-8") as file:
        glossary = json.load(file)

    label_counts = _load_dataset_label_counts()
    invalid_entries: list[str] = []

    for term, labels in glossary.get("aliases", {}).items():
        missing = [label for label in labels if label not in label_counts]
        if missing:
            invalid_entries.append(f"aliases.{term}: {missing}")

    for phrase, labels in glossary.get("phrases", {}).items():
        missing = [label for label in labels if label not in label_counts]
        if missing:
            invalid_entries.append(f"phrases.{phrase}: {missing}")

    if invalid_entries:
        message = ", ".join(invalid_entries)
        raise RuntimeError(f"Glossary references labels missing from dataset: {message}")

    return glossary


def map_text_to_ksl(request: TextToKslRequest) -> TextToKslResponse:
    glossary = _load_glossary()
    label_counts = _load_dataset_label_counts()
    dataset_lookup = _load_dataset_label_lookup()
    dataset_assets = _load_dataset_assets()

    original_text = request.text
    normalized_text = _normalize_text(original_text)
    tokens = _tokenize(normalized_text)

    ignored_terms = set(glossary.get("ignored_terms", []))
    alias_map: dict[str, list[str]] = glossary.get("aliases", {})
    raw_phrase_map: dict[str, list[str]] = glossary.get("phrases", {})
    phrase_map = {tuple(_tokenize(key)): value for key, value in raw_phrase_map.items()}
    max_phrase_length = max((len(key) for key in phrase_map), default=1)

    gloss: list[str] = []
    matched_terms: list[str] = []
    unmatched_terms: list[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]

        if token in ignored_terms:
            index += 1
            continue

        matched_labels: list[str] | None = None
        matched_term = ""
        consumed = 1

        for phrase_length in range(min(max_phrase_length, len(tokens) - index), 1, -1):
            candidate_tokens = tuple(tokens[index : index + phrase_length])
            if candidate_tokens in phrase_map:
                matched_labels = phrase_map[candidate_tokens]
                matched_term = " ".join(candidate_tokens)
                consumed = phrase_length
                break

        if matched_labels is None and token in alias_map:
            matched_labels = alias_map[token]
            matched_term = token

        if matched_labels is None:
            direct_label = dataset_lookup.get(_collapse_token(token))
            if direct_label:
                matched_labels = [direct_label]
                matched_term = token

        if matched_labels:
            gloss.extend(matched_labels)
            matched_terms.append(matched_term)
            index += consumed
            continue

        unmatched_terms.append(token)
        index += 1

    dataset_label_counts = {label: label_counts[label] for label in gloss}
    supported = bool(gloss) and not unmatched_terms
    dataset_backed = bool(gloss) and all(label in label_counts for label in gloss)
    lesson_assets = [dataset_assets[label] for label in gloss if label in dataset_assets]
    lesson_asset_id = f"dataset-sequence:{'__'.join(gloss).lower()}" if gloss else None

    if supported:
        status = "ok"
    elif gloss:
        status = "partial"
    else:
        status = "unsupported"

    return TextToKslResponse(
        original_text=original_text,
        normalized_text=normalized_text,
        gloss=gloss,
        matched_terms=matched_terms,
        unmatched_terms=unmatched_terms,
        supported=supported,
        dataset_backed=dataset_backed,
        dataset_label_counts=dataset_label_counts,
        lesson_assets=lesson_assets,
        lesson_asset_id=lesson_asset_id,
        status=status,
    )
