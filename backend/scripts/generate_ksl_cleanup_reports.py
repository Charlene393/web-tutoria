#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "KSL-Dataset" / "Pose Data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "reports" / "ksl_cleanup"
LABEL_ALLOWED_PATTERN = re.compile(r"^[A-Z0-9_'-]+$")


def iter_landmark_files(root: Path):
    for file_path in sorted(root.glob("Batch */*/Extract/Landmarks/*.npy")):
        yield file_path


def normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def label_flags(label: str, sample_count: int) -> list[str]:
    flags: list[str] = []

    if label.startswith("."):
        flags.append("starts_with_period")
    if label.lower().endswith((".mp4", ".npy", ".png", ".jpg", ".jpeg")):
        flags.append("looks_like_filename")
    if "." in label:
        flags.append("contains_period")
    if " " in label:
        flags.append("contains_space")
    if label != label.upper():
        flags.append("not_uppercase")
    if not LABEL_ALLOWED_PATTERN.fullmatch(label):
        flags.append("contains_unexpected_characters")
    if sample_count == 1:
        flags.append("single_sample")
    elif sample_count < 3:
        flags.append("low_sample_count")

    return flags


def naming_flags_from_label_flags(flags: list[str]) -> list[str]:
    return [flag for flag in flags if flag not in {"single_sample", "low_sample_count"}]


def support_flags_from_label_flags(flags: list[str]) -> list[str]:
    return [flag for flag in flags if flag in {"single_sample", "low_sample_count"}]


def analyze_landmark_file(file_path: Path, dataset_root: Path, short_sequence_threshold: int) -> dict[str, Any]:
    sequence = np.load(file_path, allow_pickle=True)
    frame_count = int(len(sequence))

    pose_frame_count = 0
    left_hand_frame_count = 0
    right_hand_frame_count = 0
    both_hands_missing_count = 0
    face_frame_count = 0

    first_frame = sequence[0] if frame_count else {}
    first_pose_points = len(first_frame.get("pose", [])) if isinstance(first_frame, dict) else 0
    first_left_hand_points = len(first_frame.get("left_hand", [])) if isinstance(first_frame, dict) else 0
    first_right_hand_points = len(first_frame.get("right_hand", [])) if isinstance(first_frame, dict) else 0
    first_face_points = len(first_frame.get("face", [])) if isinstance(first_frame, dict) else 0

    for frame in sequence:
        if not isinstance(frame, dict):
            continue

        pose_points = len(frame.get("pose", []))
        left_points = len(frame.get("left_hand", []))
        right_points = len(frame.get("right_hand", []))
        face_points = len(frame.get("face", []))

        if pose_points:
            pose_frame_count += 1
        if left_points:
            left_hand_frame_count += 1
        if right_points:
            right_hand_frame_count += 1
        if face_points:
            face_frame_count += 1
        if not left_points and not right_points:
            both_hands_missing_count += 1

    relative_parts = file_path.relative_to(dataset_root).parts
    batch = relative_parts[0]
    signer_id = relative_parts[1]
    label = file_path.stem.strip()
    stickman_path = file_path.parents[1] / "Stickmans" / f"{label}.mp4"

    sample_flags: list[str] = []
    if frame_count < short_sequence_threshold:
        sample_flags.append("short_sequence")
    if left_hand_frame_count == 0:
        sample_flags.append("left_hand_missing_all_frames")
    if right_hand_frame_count == 0:
        sample_flags.append("right_hand_missing_all_frames")
    if both_hands_missing_count == frame_count and frame_count > 0:
        sample_flags.append("both_hands_missing_all_frames")
    if not stickman_path.exists():
        sample_flags.append("missing_stickman_video")
    if pose_frame_count == 0:
        sample_flags.append("pose_missing_all_frames")

    return {
        "batch": batch,
        "signer_id": signer_id,
        "label": label,
        "normalized_label": normalize_label(label),
        "landmark_path": str(file_path.relative_to(PROJECT_ROOT)),
        "stickman_video_path": str(stickman_path.relative_to(PROJECT_ROOT)) if stickman_path.exists() else "",
        "has_stickman_video": stickman_path.exists(),
        "frame_count": frame_count,
        "first_pose_points": first_pose_points,
        "first_left_hand_points": first_left_hand_points,
        "first_right_hand_points": first_right_hand_points,
        "first_face_points": first_face_points,
        "pose_frame_pct": round((pose_frame_count / frame_count) * 100, 2) if frame_count else 0.0,
        "left_hand_frame_pct": round((left_hand_frame_count / frame_count) * 100, 2) if frame_count else 0.0,
        "right_hand_frame_pct": round((right_hand_frame_count / frame_count) * 100, 2) if frame_count else 0.0,
        "face_frame_pct": round((face_frame_count / frame_count) * 100, 2) if frame_count else 0.0,
        "both_hands_missing_frame_pct": round((both_hands_missing_count / frame_count) * 100, 2) if frame_count else 0.0,
        "sample_flags": ";".join(sample_flags),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def generate_reports(
    dataset_root: Path,
    output_dir: Path,
    short_sequence_threshold: int,
    hand_missing_threshold: float,
) -> dict[str, Any]:
    if not dataset_root.exists():
        raise RuntimeError(f"Dataset root not found: {dataset_root}")

    manifest_rows = [
        analyze_landmark_file(file_path, dataset_root, short_sequence_threshold)
        for file_path in iter_landmark_files(dataset_root)
    ]

    if not manifest_rows:
        raise RuntimeError(f"No landmark files found under {dataset_root}")

    label_counter = Counter(row["label"] for row in manifest_rows)
    label_rows: list[dict[str, Any]] = []
    suspicious_label_rows: list[dict[str, Any]] = []
    low_support_label_rows: list[dict[str, Any]] = []
    label_variant_groups: defaultdict[str, list[str]] = defaultdict(list)

    for row in manifest_rows:
        label_variant_groups[row["normalized_label"]].append(row["label"])

    rows_by_label: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        rows_by_label[row["label"]].append(row)

    for label, rows in sorted(rows_by_label.items()):
        sample_count = len(rows)
        flags = label_flags(label, sample_count)
        unique_signers = sorted({row["signer_id"] for row in rows})
        unique_batches = sorted({row["batch"] for row in rows})
        frame_counts = [int(row["frame_count"]) for row in rows]
        left_pcts = [float(row["left_hand_frame_pct"]) for row in rows]
        right_pcts = [float(row["right_hand_frame_pct"]) for row in rows]
        both_missing_pcts = [float(row["both_hands_missing_frame_pct"]) for row in rows]

        label_row = {
            "label": label,
            "normalized_label": normalize_label(label),
            "sample_count": sample_count,
            "unique_signers": len(unique_signers),
            "unique_batches": len(unique_batches),
            "avg_frame_count": round(statistics.mean(frame_counts), 2),
            "median_frame_count": statistics.median(frame_counts),
            "min_frame_count": min(frame_counts),
            "max_frame_count": max(frame_counts),
            "avg_left_hand_frame_pct": round(statistics.mean(left_pcts), 2),
            "avg_right_hand_frame_pct": round(statistics.mean(right_pcts), 2),
            "avg_both_hands_missing_frame_pct": round(statistics.mean(both_missing_pcts), 2),
            "samples_missing_stickman": sum(1 for row in rows if not row["has_stickman_video"]),
            "samples_with_no_left_hand": sum(1 for row in rows if float(row["left_hand_frame_pct"]) == 0.0),
            "samples_with_no_right_hand": sum(1 for row in rows if float(row["right_hand_frame_pct"]) == 0.0),
            "samples_with_no_hands": sum(
                1 for row in rows if float(row["both_hands_missing_frame_pct"]) == 100.0
            ),
            "label_flags": ";".join(flags),
        }
        label_rows.append(label_row)

        if naming_flags_from_label_flags(flags):
            suspicious_label_rows.append(label_row)
        if support_flags_from_label_flags(flags):
            low_support_label_rows.append(label_row)

    missing_hands_rows = [
        row
        for row in manifest_rows
        if float(row["both_hands_missing_frame_pct"]) >= hand_missing_threshold
        or float(row["left_hand_frame_pct"]) == 0.0
        or float(row["right_hand_frame_pct"]) == 0.0
    ]

    review_candidate_rows = [
        row
        for row in manifest_rows
        if row["sample_flags"]
        or any(
            flag
            for flag in label_flags(row["label"], label_counter[row["label"]])
            if flag in {"looks_like_filename", "contains_period", "contains_unexpected_characters"}
        )
    ]

    variant_rows = []
    for normalized, labels in sorted(label_variant_groups.items()):
        distinct_labels = sorted(set(labels))
        if len(distinct_labels) > 1:
            variant_rows.append(
                {
                    "normalized_label": normalized,
                    "labels": ";".join(distinct_labels),
                    "label_count": len(distinct_labels),
                    "total_samples": sum(label_counter[label] for label in distinct_labels),
                }
            )

    summary = {
        "dataset_root": str(dataset_root),
        "output_dir": str(output_dir),
        "total_samples": len(manifest_rows),
        "unique_labels": len(label_counter),
        "unique_signers": len({row["signer_id"] for row in manifest_rows}),
        "unique_batches": len({row["batch"] for row in manifest_rows}),
        "labels_with_1_sample": sum(1 for count in label_counter.values() if count == 1),
        "labels_with_lt_3_samples": sum(1 for count in label_counter.values() if count < 3),
        "samples_missing_stickman": sum(1 for row in manifest_rows if not row["has_stickman_video"]),
        "samples_flagged_for_missing_hands_review": len(missing_hands_rows),
        "labels_flagged_as_suspicious": len(suspicious_label_rows),
        "labels_flagged_as_low_support": len(low_support_label_rows),
        "samples_flagged_for_review": len(review_candidate_rows),
        "label_variant_groups": len(variant_rows),
        "short_sequence_threshold": short_sequence_threshold,
        "hand_missing_threshold": hand_missing_threshold,
    }

    write_csv(
        output_dir / "manifest.csv",
        manifest_rows,
        [
            "batch",
            "signer_id",
            "label",
            "normalized_label",
            "landmark_path",
            "stickman_video_path",
            "has_stickman_video",
            "frame_count",
            "first_pose_points",
            "first_left_hand_points",
            "first_right_hand_points",
            "first_face_points",
            "pose_frame_pct",
            "left_hand_frame_pct",
            "right_hand_frame_pct",
            "face_frame_pct",
            "both_hands_missing_frame_pct",
            "sample_flags",
        ],
    )
    write_csv(
        output_dir / "label_counts.csv",
        label_rows,
        [
            "label",
            "normalized_label",
            "sample_count",
            "unique_signers",
            "unique_batches",
            "avg_frame_count",
            "median_frame_count",
            "min_frame_count",
            "max_frame_count",
            "avg_left_hand_frame_pct",
            "avg_right_hand_frame_pct",
            "avg_both_hands_missing_frame_pct",
            "samples_missing_stickman",
            "samples_with_no_left_hand",
            "samples_with_no_right_hand",
            "samples_with_no_hands",
            "label_flags",
        ],
    )
    write_csv(
        output_dir / "missing_hands_report.csv",
        missing_hands_rows,
        [
            "batch",
            "signer_id",
            "label",
            "landmark_path",
            "stickman_video_path",
            "frame_count",
            "left_hand_frame_pct",
            "right_hand_frame_pct",
            "both_hands_missing_frame_pct",
            "sample_flags",
        ],
    )
    write_csv(
        output_dir / "suspicious_labels.csv",
        suspicious_label_rows,
        [
            "label",
            "normalized_label",
            "sample_count",
            "unique_signers",
            "unique_batches",
            "avg_frame_count",
            "median_frame_count",
            "min_frame_count",
            "max_frame_count",
            "avg_left_hand_frame_pct",
            "avg_right_hand_frame_pct",
            "avg_both_hands_missing_frame_pct",
            "samples_missing_stickman",
            "samples_with_no_left_hand",
            "samples_with_no_right_hand",
            "samples_with_no_hands",
            "label_flags",
        ],
    )
    write_csv(
        output_dir / "low_support_labels.csv",
        low_support_label_rows,
        [
            "label",
            "normalized_label",
            "sample_count",
            "unique_signers",
            "unique_batches",
            "avg_frame_count",
            "median_frame_count",
            "min_frame_count",
            "max_frame_count",
            "avg_left_hand_frame_pct",
            "avg_right_hand_frame_pct",
            "avg_both_hands_missing_frame_pct",
            "samples_missing_stickman",
            "samples_with_no_left_hand",
            "samples_with_no_right_hand",
            "samples_with_no_hands",
            "label_flags",
        ],
    )
    write_csv(
        output_dir / "review_candidates.csv",
        review_candidate_rows,
        [
            "batch",
            "signer_id",
            "label",
            "landmark_path",
            "stickman_video_path",
            "frame_count",
            "left_hand_frame_pct",
            "right_hand_frame_pct",
            "both_hands_missing_frame_pct",
            "sample_flags",
        ],
    )
    write_csv(
        output_dir / "label_variants.csv",
        variant_rows,
        ["normalized_label", "labels", "label_count", "total_samples"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local cleanup reports for the KSL dataset.")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Path to the KSL pose dataset root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where CSV and JSON cleanup reports will be written.",
    )
    parser.add_argument(
        "--short-sequence-threshold",
        type=int,
        default=12,
        help="Flag samples shorter than this frame count.",
    )
    parser.add_argument(
        "--hand-missing-threshold",
        type=float,
        default=50.0,
        help="Flag samples where both hands are missing in at least this percentage of frames.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = generate_reports(
        dataset_root=args.root,
        output_dir=args.output_dir,
        short_sequence_threshold=args.short_sequence_threshold,
        hand_missing_threshold=args.hand_missing_threshold,
    )
    print("Generated cleanup reports")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
