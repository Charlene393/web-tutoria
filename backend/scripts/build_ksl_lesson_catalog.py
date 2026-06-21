#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLEANED_MANIFEST_PATH = PROJECT_ROOT / "backend" / "reports" / "ksl_cleanup" / "cleaned" / "manifest.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "backend" / "api" / "app" / "data" / "ksl_lesson_catalog.json"


def read_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def as_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def as_int(value: str) -> int:
    return int(float(value))


def as_float(value: str) -> float:
    return float(value)


def split_flags(value: str) -> list[str]:
    return [flag for flag in value.split(";") if flag]


def relative_to_project(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def quality_score(row: dict[str, str]) -> float:
    flags = split_flags(row.get("sample_flags", ""))
    score = 0.0

    if as_bool(row.get("has_stickman_video", "")):
        score += 50.0

    score += min(as_int(row["frame_count"]), 60) * 0.35
    score += as_float(row["pose_frame_pct"]) * 0.10
    score += as_float(row["left_hand_frame_pct"]) * 0.45
    score += as_float(row["right_hand_frame_pct"]) * 0.45
    score -= as_float(row["both_hands_missing_frame_pct"]) * 0.35

    if "short_sequence" in flags:
        score -= 15.0
    if "left_hand_missing_all_frames" in flags:
        score -= 25.0
    if "right_hand_missing_all_frames" in flags:
        score -= 25.0
    if "both_hands_missing_all_frames" in flags:
        score -= 120.0
    if "missing_stickman_video" in flags:
        score -= 40.0
    if "pose_missing_all_frames" in flags:
        score -= 120.0

    score -= len(flags) * 3.0
    return round(score, 2)


def selection_key(row: dict[str, str]) -> tuple[Any, ...]:
    flags = split_flags(row.get("sample_flags", ""))
    return (
        as_bool(row.get("has_stickman_video", "")),
        len(flags) == 0,
        "both_hands_missing_all_frames" not in flags,
        "pose_missing_all_frames" not in flags,
        "short_sequence" not in flags,
        quality_score(row),
        as_float(row["left_hand_frame_pct"]) + as_float(row["right_hand_frame_pct"]),
        100.0 - as_float(row["both_hands_missing_frame_pct"]),
        as_int(row["frame_count"]),
        row["landmark_path"],
    )


def build_catalog_entry(label: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    selected_row = max(rows, key=selection_key)
    sample_flags = split_flags(selected_row.get("sample_flags", ""))

    return {
        "asset_id": f"lesson-sign:{label.lower()}",
        "label": label,
        "sample_count": len(rows),
        "source": "cleaned_lesson_catalog",
        "landmark_path": selected_row.get("landmark_path") or None,
        "stickman_video_path": selected_row.get("stickman_video_path") or None,
        "batch": selected_row.get("batch") or None,
        "signer_id": selected_row.get("signer_id") or None,
        "frame_count": as_int(selected_row["frame_count"]),
        "sample_flags": sample_flags,
        "quality_score": quality_score(selected_row),
        "selected_from_flagged_sample": bool(sample_flags),
    }


def build_lesson_catalog(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise RuntimeError(f"Cleaned manifest not found: {manifest_path}")

    manifest_rows = read_manifest_rows(manifest_path)
    if not manifest_rows:
        raise RuntimeError(f"No rows found in cleaned manifest: {manifest_path}")

    rows_by_label: dict[str, list[dict[str, str]]] = {}
    for row in manifest_rows:
        rows_by_label.setdefault(row["label"], []).append(row)

    entries = [
        build_catalog_entry(label=label, rows=rows)
        for label, rows in sorted(rows_by_label.items())
    ]

    catalog = {
        "catalog_name": "ksl_cleaned_lesson_catalog",
        "catalog_version": "v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_path": relative_to_project(manifest_path),
        "selection_strategy": "highest_quality_sample_per_label_from_cleaned_manifest",
        "total_entries": len(entries),
        "total_labels": len(entries),
        "total_samples": len(manifest_rows),
        "entries": entries,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, indent=2)

    return {
        "manifest_path": str(manifest_path),
        "output_path": str(output_path),
        "total_entries": len(entries),
        "total_labels": len(entries),
        "total_samples": len(manifest_rows),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a cleaned KSL lesson catalog JSON from the cleaned manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_CLEANED_MANIFEST_PATH,
        help="Path to the cleaned manifest.csv file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the generated KSL lesson catalog JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_lesson_catalog(args.manifest, args.output)
    print("Built KSL lesson catalog")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
