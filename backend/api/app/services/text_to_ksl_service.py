from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..schemas.requests import TextToKslRequest
from ..schemas.responses import LessonAsset, TextToKslResponse

TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


def _glossary_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ksl_glossary.json"


def _lesson_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ksl_lesson_catalog.json"


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
def _load_lesson_catalog_data() -> dict[str, Any]:
    catalog_path = _lesson_catalog_path()
    if not catalog_path.exists():
        raise RuntimeError(
            f"KSL lesson catalog not found at {catalog_path}. "
            "Run backend/scripts/build_ksl_lesson_catalog.py first."
        )

    with catalog_path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    entries = catalog.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise RuntimeError(f"KSL lesson catalog at {catalog_path} does not contain any entries.")

    labels = [entry.get("label") for entry in entries if entry.get("label")]
    duplicate_labels = sorted(label for label, count in Counter(labels).items() if count > 1)
    if duplicate_labels:
        raise RuntimeError(f"KSL lesson catalog contains duplicate labels: {duplicate_labels}")

    return catalog


@lru_cache(maxsize=1)
def _load_lesson_catalog_assets() -> dict[str, LessonAsset]:
    catalog = _load_lesson_catalog_data()
    assets: dict[str, LessonAsset] = {}

    for entry in catalog["entries"]:
        label = entry["label"]
        assets[label] = LessonAsset(
            asset_id=entry["asset_id"],
            label=label,
            sample_count=int(entry["sample_count"]),
            source=entry.get("source", "cleaned_lesson_catalog"),
            landmark_path=entry.get("landmark_path"),
            stickman_video_path=entry.get("stickman_video_path"),
            batch=entry.get("batch"),
            signer_id=entry.get("signer_id"),
            frame_count=entry.get("frame_count"),
            sample_flags=entry.get("sample_flags") or [],
            quality_score=entry.get("quality_score"),
            selected_from_flagged_sample=entry.get("selected_from_flagged_sample"),
        )

    return assets


@lru_cache(maxsize=1)
def _load_catalog_label_counts() -> Counter[str]:
    return Counter(
        {
            label: asset.sample_count
            for label, asset in _load_lesson_catalog_assets().items()
        }
    )


@lru_cache(maxsize=1)
def _load_catalog_label_lookup() -> dict[str, str]:
    return {_collapse_token(label): label for label in _load_catalog_label_counts()}


@lru_cache(maxsize=1)
def _load_glossary() -> dict[str, object]:
    glossary_path = _glossary_path()
    with glossary_path.open("r", encoding="utf-8") as file:
        glossary = json.load(file)

    label_counts = _load_catalog_label_counts()
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
        raise RuntimeError(f"Glossary references labels missing from cleaned lesson catalog: {message}")

    return glossary


def map_text_to_ksl(request: TextToKslRequest) -> TextToKslResponse:
    glossary = _load_glossary()
    catalog = _load_lesson_catalog_data()
    label_counts = _load_catalog_label_counts()
    label_lookup = _load_catalog_label_lookup()
    lesson_catalog_assets = _load_lesson_catalog_assets()

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
            direct_label = label_lookup.get(_collapse_token(token))
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
    catalog_backed = bool(gloss) and all(label in label_counts for label in gloss)
    dataset_backed = catalog_backed
    lesson_assets = [lesson_catalog_assets[label] for label in gloss if label in lesson_catalog_assets]
    lesson_asset_id = f"dataset-sequence:{'__'.join(gloss).lower()}" if gloss else None
    supported = bool(gloss) and not unmatched_terms

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
        catalog_backed=catalog_backed,
        catalog_name=catalog.get("catalog_name"),
        catalog_generated_at=catalog.get("generated_at"),
        status=status,
    )
