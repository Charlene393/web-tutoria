#!/usr/bin/env python3
# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

BACKEND_API_ROOT = Path(__file__).resolve().parents[1] / "api"

if str(BACKEND_API_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_ROOT))

from app.services.sign_features import extract_sign_feature_vector_from_path
from app.services.sign_recognizer import (
    default_label_set_path,
    default_manifest_path,
    load_sign_label_set,
    resolve_project_path,
)
from app.core.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the dataset-backed sign recognizer with a simple holdout-per-label check."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_manifest_path(),
        help="Path to the cleaned manifest CSV.",
    )
    parser.add_argument(
        "--label-set",
        type=Path,
        default=default_label_set_path(),
        help="Optional JSON file that restricts evaluation to a curated label set.",
    )
    parser.add_argument(
        "--min-samples-per-label",
        type=int,
        default=settings.sign_recognizer_min_samples_per_label,
        help="Minimum label count required to participate in evaluation.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/reports/ksl_cleanup/sign_recognizer_eval.json"),
        help="Where to write the evaluation report JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    label_set_name, allowed_labels, _label_set_hash = load_sign_label_set(args.label_set)
    rows = list(_read_manifest_rows(args.manifest))
    if not rows:
        raise RuntimeError(f"No cleaned rows found in manifest {args.manifest}.")

    label_counts = Counter(row["label"] for row in rows)
    eligible_rows = [
        row
        for row in rows
        if label_counts[row["label"]] >= args.min_samples_per_label
        and (allowed_labels is None or row["label"] in allowed_labels)
    ]
    if not eligible_rows:
        raise RuntimeError("No labels meet the requested min_samples_per_label for evaluation.")

    holdout_by_label: dict[str, dict[str, str]] = {}
    training_rows: list[dict[str, str]] = []
    seen_counts = Counter(row["label"] for row in eligible_rows)

    for row in eligible_rows:
        label = row["label"]
        if seen_counts[label] == label_counts[label]:
            holdout_by_label[label] = row
        else:
            training_rows.append(row)
        seen_counts[label] -= 1

    reference_features: list[np.ndarray] = []
    reference_labels: list[str] = []
    for row in training_rows:
        feature_vector, _ = extract_sign_feature_vector_from_path(
            resolve_project_path(row["landmark_path"]),
            target_frames=settings.sign_recognizer_target_frames,
        )
        reference_features.append(feature_vector)
        reference_labels.append(row["label"])

    if not reference_features:
        raise RuntimeError("No reference samples were available for evaluation.")

    feature_matrix = np.stack(reference_features, axis=0).astype(np.float32, copy=False)
    predictions: list[dict[str, object]] = []
    top_k_hits = {1: 0, 3: 0, 5: 0}

    for label, row in sorted(holdout_by_label.items()):
        feature_vector, _ = extract_sign_feature_vector_from_path(
            resolve_project_path(row["landmark_path"]),
            target_frames=settings.sign_recognizer_target_frames,
        )
        similarities = feature_matrix @ feature_vector
        best_by_label: dict[str, float] = {}
        for index, similarity in enumerate(similarities.tolist()):
            candidate_label = reference_labels[index]
            current = best_by_label.get(candidate_label)
            if current is None or similarity > current:
                best_by_label[candidate_label] = float(similarity)

        ranked_candidates = sorted(best_by_label.items(), key=lambda item: item[1], reverse=True)
        predicted_label, predicted_similarity = ranked_candidates[0]
        ranked_labels = [candidate_label for candidate_label, _ in ranked_candidates]

        for top_k in top_k_hits:
            if label in ranked_labels[:top_k]:
                top_k_hits[top_k] += 1

        predictions.append(
            {
                "label": label,
                "predicted_label": predicted_label,
                "correct_top_1": predicted_label == label,
                "correct_top_3": label in ranked_labels[:3],
                "correct_top_5": label in ranked_labels[:5],
                "similarity": round(predicted_similarity, 4),
                "landmark_path": row["landmark_path"],
                "top_5_labels": ranked_labels[:5],
            }
        )

    report = {
        "evaluation_type": "holdout_one_per_label",
        "manifest_path": str(args.manifest),
        "label_set_name": label_set_name,
        "label_set_path": str(args.label_set) if args.label_set else None,
        "min_samples_per_label": args.min_samples_per_label,
        "target_frames": settings.sign_recognizer_target_frames,
        "evaluated_labels": len(predictions),
        "reference_samples": len(reference_labels),
        "top_1_accuracy": round(top_k_hits[1] / len(predictions), 4) if predictions else 0.0,
        "top_3_accuracy": round(top_k_hits[3] / len(predictions), 4) if predictions else 0.0,
        "top_5_accuracy": round(top_k_hits[5] / len(predictions), 4) if predictions else 0.0,
        "predictions": predictions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote evaluation report to {args.output}")
    print(f"label_set_name: {report['label_set_name']}")
    print(f"evaluated_labels: {report['evaluated_labels']}")
    print(f"reference_samples: {report['reference_samples']}")
    print(f"top_1_accuracy: {report['top_1_accuracy']}")
    print(f"top_3_accuracy: {report['top_3_accuracy']}")
    print(f"top_5_accuracy: {report['top_5_accuracy']}")


def _read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as file:
        return [
            {
                "label": (row.get("label") or "").strip(),
                "landmark_path": (row.get("landmark_path") or "").strip(),
            }
            for row in csv.DictReader(file)
            if (row.get("label") or "").strip() and (row.get("landmark_path") or "").strip()
        ]


if __name__ == "__main__":
    main()
