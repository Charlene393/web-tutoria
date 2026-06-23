#!/usr/bin/env python3
# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_API_ROOT = Path(__file__).resolve().parents[1] / "api"

if str(BACKEND_API_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_ROOT))

from app.services.sign_recognizer import (
    build_sign_recognizer_artifact,
    default_artifact_path,
    default_label_set_path,
    default_manifest_path,
)
from app.core.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the dataset-backed sign recognizer artifact from the cleaned KSL manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_manifest_path(),
        help="Path to the cleaned manifest CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_artifact_path(),
        help="Where to write the recognizer artifact.",
    )
    parser.add_argument(
        "--label-set",
        type=Path,
        default=default_label_set_path(),
        help="Optional JSON file that restricts recognition to a curated label set.",
    )
    parser.add_argument(
        "--min-samples-per-label",
        type=int,
        default=settings.sign_recognizer_min_samples_per_label,
        help="Minimum cleaned samples required for a label to be included.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact = build_sign_recognizer_artifact(
        manifest_path=args.manifest,
        artifact_path=args.output,
        label_set_path=args.label_set,
        min_samples_per_label=args.min_samples_per_label,
    )
    print("Built sign recognizer artifact")
    print(f"model_id: {artifact.model_id}")
    print(f"artifact_path: {artifact.artifact_path}")
    print(f"manifest_path: {artifact.manifest_path}")
    print(f"label_set_name: {artifact.label_set_name}")
    print(f"total_samples: {len(artifact.labels)}")
    print(f"total_labels: {len(artifact.label_counts)}")
    print(f"target_frames: {artifact.target_frames}")
    print(f"feature_version: {artifact.feature_version}")


if __name__ == "__main__":
    main()
