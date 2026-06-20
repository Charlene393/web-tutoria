#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "backend" / "reports" / "ksl_cleanup"
DEFAULT_OUTPUT_PATH = DEFAULT_REPORTS_DIR / "cleanup_decisions.csv"

REQUIRED_REPORT_FILES = (
    "manifest.csv",
    "label_counts.csv",
    "suspicious_labels.csv",
    "review_candidates.csv",
)

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
LABEL_NAMING_FLAGS = {
    "starts_with_period",
    "looks_like_filename",
    "contains_period",
    "contains_space",
    "not_uppercase",
    "contains_unexpected_characters",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def split_flags(value: str) -> list[str]:
    return [flag for flag in value.split(";") if flag]


def prefix_flags(flags: list[str], prefix: str) -> list[str]:
    return [f"{prefix}:{flag}" for flag in flags]


def normalize_source_reports(existing_value: str, new_report: str) -> str:
    reports = [item for item in existing_value.split(";") if item]
    if new_report not in reports:
        reports.append(new_report)
    return ";".join(reports)


def recommend_label_action(flags: list[str]) -> tuple[str, str]:
    if any(flag in flags for flag in {"starts_with_period", "looks_like_filename", "contains_period"}):
        return "high", "rename_or_drop_label"
    if any(flag in flags for flag in {"contains_space", "not_uppercase", "contains_unexpected_characters"}):
        return "medium", "rename_label_review"
    if any(flag in flags for flag in {"single_sample", "low_sample_count"}):
        return "low", "keep_or_merge_review"
    return "low", "manual_review"


def recommend_sample_action(label_flags: list[str], sample_flags: list[str]) -> tuple[str, str]:
    naming_flags = [flag for flag in label_flags if flag in LABEL_NAMING_FLAGS]

    if any(flag in naming_flags for flag in {"starts_with_period", "looks_like_filename", "contains_period"}):
        return "high", "rename_label_or_drop_sample"
    if any(flag in naming_flags for flag in {"contains_space", "not_uppercase", "contains_unexpected_characters"}):
        return "medium", "rename_label_review"
    if any(flag in sample_flags for flag in {"missing_stickman_video", "pose_missing_all_frames"}):
        return "high", "drop_or_reextract_sample"
    if "both_hands_missing_all_frames" in sample_flags:
        return "high", "drop_or_reextract_sample"
    if any(flag in sample_flags for flag in {"left_hand_missing_all_frames", "right_hand_missing_all_frames"}):
        return "medium", "review_hand_quality"
    if "short_sequence" in sample_flags:
        return "medium", "review_short_sequence"
    return "low", "manual_review"


def build_label_row(
    label_row: dict[str, str],
    manifest_example: dict[str, str] | None,
    source_report: str,
) -> dict[str, str]:
    flags = split_flags(label_row.get("label_flags", ""))
    priority, recommended_action = recommend_label_action(flags)
    example = manifest_example or {}

    return {
        "decision_id": f"label::{label_row['label']}",
        "scope": "label",
        "source_report": source_report,
        "priority": priority,
        "current_label": label_row["label"],
        "normalized_label": label_row.get("normalized_label", ""),
        "sample_count": label_row.get("sample_count", ""),
        "batch": example.get("batch", ""),
        "signer_id": example.get("signer_id", ""),
        "landmark_path": example.get("landmark_path", ""),
        "stickman_video_path": example.get("stickman_video_path", ""),
        "frame_count": example.get("frame_count", ""),
        "left_hand_frame_pct": example.get("left_hand_frame_pct", ""),
        "right_hand_frame_pct": example.get("right_hand_frame_pct", ""),
        "both_hands_missing_frame_pct": example.get("both_hands_missing_frame_pct", ""),
        "label_flags": ";".join(flags),
        "sample_flags": "",
        "issue_flags": ";".join(prefix_flags(flags, "label")),
        "recommended_action": recommended_action,
        "selected_action": "",
        "target_label": "",
        "review_status": "pending",
        "notes": "",
    }


def build_sample_row(
    sample_row: dict[str, str],
    label_row: dict[str, str] | None,
) -> dict[str, str]:
    label_flags = split_flags(label_row.get("label_flags", "")) if label_row else []
    sample_flags = split_flags(sample_row.get("sample_flags", ""))
    priority, recommended_action = recommend_sample_action(label_flags, sample_flags)
    issue_flags = prefix_flags(sample_flags, "sample") + prefix_flags(label_flags, "label")

    return {
        "decision_id": f"sample::{sample_row['landmark_path']}",
        "scope": "sample",
        "source_report": "review_candidates.csv",
        "priority": priority,
        "current_label": sample_row["label"],
        "normalized_label": label_row.get("normalized_label", "") if label_row else "",
        "sample_count": label_row.get("sample_count", "") if label_row else "",
        "batch": sample_row.get("batch", ""),
        "signer_id": sample_row.get("signer_id", ""),
        "landmark_path": sample_row.get("landmark_path", ""),
        "stickman_video_path": sample_row.get("stickman_video_path", ""),
        "frame_count": sample_row.get("frame_count", ""),
        "left_hand_frame_pct": sample_row.get("left_hand_frame_pct", ""),
        "right_hand_frame_pct": sample_row.get("right_hand_frame_pct", ""),
        "both_hands_missing_frame_pct": sample_row.get("both_hands_missing_frame_pct", ""),
        "label_flags": ";".join(label_flags),
        "sample_flags": ";".join(sample_flags),
        "issue_flags": ";".join(issue_flags),
        "recommended_action": recommended_action,
        "selected_action": "",
        "target_label": "",
        "review_status": "pending",
        "notes": "",
    }


def load_report_inputs(reports_dir: Path) -> dict[str, list[dict[str, str]]]:
    missing_files = [name for name in REQUIRED_REPORT_FILES if not (reports_dir / name).exists()]
    if missing_files:
        missing_text = ", ".join(missing_files)
        raise RuntimeError(
            f"Missing required cleanup reports: {missing_text}. "
            "Run backend/scripts/generate_ksl_cleanup_reports.py first."
        )

    inputs = {name: read_csv_rows(reports_dir / name) for name in REQUIRED_REPORT_FILES}

    low_support_path = reports_dir / "low_support_labels.csv"
    inputs["low_support_labels.csv"] = read_csv_rows(low_support_path) if low_support_path.exists() else []

    return inputs


def sort_decision_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            PRIORITY_RANK.get(row["priority"], 99),
            row["scope"],
            row["current_label"],
            row["landmark_path"],
        ),
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def build_cleanup_decisions(
    reports_dir: Path,
    output_path: Path,
    include_low_support: bool,
    force: bool,
) -> dict[str, Any]:
    if output_path.exists() and not force:
        raise RuntimeError(
            f"{output_path} already exists. "
            "Refusing to overwrite manual review work. Re-run with --force if needed."
        )

    inputs = load_report_inputs(reports_dir)
    manifest_rows = inputs["manifest.csv"]
    label_count_rows = inputs["label_counts.csv"]
    suspicious_label_rows = inputs["suspicious_labels.csv"]
    low_support_label_rows = inputs["low_support_labels.csv"]
    review_candidate_rows = inputs["review_candidates.csv"]

    first_manifest_by_label: dict[str, dict[str, str]] = {}
    for row in manifest_rows:
        first_manifest_by_label.setdefault(row["label"], row)

    label_counts_by_label = {row["label"]: row for row in label_count_rows}
    decision_rows: list[dict[str, str]] = []
    label_decisions_by_label: dict[str, dict[str, str]] = {}

    for label_row in suspicious_label_rows:
        decision_row = build_label_row(
            label_row=label_row,
            manifest_example=first_manifest_by_label.get(label_row["label"]),
            source_report="suspicious_labels.csv",
        )
        label_decisions_by_label[label_row["label"]] = decision_row

    if include_low_support:
        for label_row in low_support_label_rows:
            existing_row = label_decisions_by_label.get(label_row["label"])
            if existing_row:
                existing_row["source_report"] = normalize_source_reports(
                    existing_row["source_report"],
                    "low_support_labels.csv",
                )
                continue

            decision_row = build_label_row(
                label_row=label_row,
                manifest_example=first_manifest_by_label.get(label_row["label"]),
                source_report="low_support_labels.csv",
            )
            label_decisions_by_label[label_row["label"]] = decision_row

    decision_rows.extend(label_decisions_by_label.values())

    for sample_row in review_candidate_rows:
        decision_rows.append(
            build_sample_row(
                sample_row=sample_row,
                label_row=label_counts_by_label.get(sample_row["label"]),
            )
        )

    decision_rows = sort_decision_rows(decision_rows)

    fieldnames = [
        "decision_id",
        "scope",
        "source_report",
        "priority",
        "current_label",
        "normalized_label",
        "sample_count",
        "batch",
        "signer_id",
        "landmark_path",
        "stickman_video_path",
        "frame_count",
        "left_hand_frame_pct",
        "right_hand_frame_pct",
        "both_hands_missing_frame_pct",
        "label_flags",
        "sample_flags",
        "issue_flags",
        "recommended_action",
        "selected_action",
        "target_label",
        "review_status",
        "notes",
    ]
    write_csv(output_path, decision_rows, fieldnames)

    return {
        "reports_dir": str(reports_dir),
        "output_path": str(output_path),
        "label_decision_rows": len(label_decisions_by_label),
        "sample_decision_rows": len(review_candidate_rows),
        "total_rows": len(decision_rows),
        "include_low_support": include_low_support,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manual cleanup decision sheet from KSL dataset review reports."
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory containing generated KSL cleanup report CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the generated cleanup decision CSV.",
    )
    parser.add_argument(
        "--include-low-support",
        action="store_true",
        help="Also add low-support labels from low_support_labels.csv to the decision sheet.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cleanup_decisions.csv file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        summary = build_cleanup_decisions(
            reports_dir=args.reports_dir,
            output_path=args.output,
            include_low_support=args.include_low_support,
            force=args.force,
        )
    except RuntimeError as exc:
        print(f"Did not regenerate cleanup decision template: {exc}")
        print("Open the existing cleanup_decisions.csv file and continue reviewing it.")
        print("Use --force only if you want to rebuild the sheet from scratch.")
        raise SystemExit(1) from exc

    print("Generated cleanup decision template")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
