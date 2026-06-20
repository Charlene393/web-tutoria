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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "backend" / "reports" / "ksl_cleanup"
DEFAULT_MANIFEST_PATH = DEFAULT_REPORTS_DIR / "manifest.csv"
DEFAULT_DECISIONS_PATH = DEFAULT_REPORTS_DIR / "cleanup_decisions.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_REPORTS_DIR / "cleaned"

DROP_ACTIONS = {"drop_sample", "drop_label"}
BLOCKED_REVIEW_STATUSES = {"hold", "needs_review", "reject", "rejected", "skip", "skipped"}
LABEL_ALLOWED_PATTERN = re.compile(r"^[A-Z0-9_'-]+$")


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


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if reader.fieldnames is None:
            raise RuntimeError(f"No CSV header found in {path}")
        return reader.fieldnames, rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def as_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def as_int(value: str) -> int:
    return int(float(value))


def as_float(value: str) -> float:
    return float(value)


def is_applicable_drop_decision(row: dict[str, str]) -> bool:
    selected_action = row.get("selected_action", "").strip().lower()
    if selected_action not in DROP_ACTIONS:
        return False

    review_status = row.get("review_status", "").strip().lower()
    return review_status not in BLOCKED_REVIEW_STATUSES


def build_clean_label_counts(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows_by_label: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_label[row["label"]].append(row)

    label_rows: list[dict[str, Any]] = []
    for label, label_rows_raw in sorted(rows_by_label.items()):
        sample_count = len(label_rows_raw)
        frame_counts = [as_int(row["frame_count"]) for row in label_rows_raw]
        left_pcts = [as_float(row["left_hand_frame_pct"]) for row in label_rows_raw]
        right_pcts = [as_float(row["right_hand_frame_pct"]) for row in label_rows_raw]
        both_missing_pcts = [as_float(row["both_hands_missing_frame_pct"]) for row in label_rows_raw]
        unique_signers = sorted({row["signer_id"] for row in label_rows_raw})
        unique_batches = sorted({row["batch"] for row in label_rows_raw})

        label_rows.append(
            {
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
                "samples_missing_stickman": sum(1 for row in label_rows_raw if not as_bool(row["has_stickman_video"])),
                "samples_with_no_left_hand": sum(
                    1 for row in label_rows_raw if as_float(row["left_hand_frame_pct"]) == 0.0
                ),
                "samples_with_no_right_hand": sum(
                    1 for row in label_rows_raw if as_float(row["right_hand_frame_pct"]) == 0.0
                ),
                "samples_with_no_hands": sum(
                    1 for row in label_rows_raw if as_float(row["both_hands_missing_frame_pct"]) == 100.0
                ),
                "label_flags": ";".join(label_flags(label, sample_count)),
            }
        )

    return label_rows


def apply_cleanup_decisions(
    manifest_path: Path,
    decisions_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest_fieldnames, manifest_rows = read_csv_rows(manifest_path)
    decision_fieldnames, decision_rows = read_csv_rows(decisions_path)

    applicable_drop_rows = [row for row in decision_rows if is_applicable_drop_decision(row)]
    blocked_drop_rows = [
        row
        for row in decision_rows
        if row.get("selected_action", "").strip().lower() in DROP_ACTIONS and not is_applicable_drop_decision(row)
    ]

    drop_sample_decisions_by_path: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    drop_label_decisions_by_label: defaultdict[str, list[dict[str, str]]] = defaultdict(list)

    for row in applicable_drop_rows:
        if row.get("selected_action", "").strip().lower() == "drop_sample" and row.get("landmark_path", "").strip():
            drop_sample_decisions_by_path[row["landmark_path"]].append(row)
        if row.get("selected_action", "").strip().lower() == "drop_label" and row.get("current_label", "").strip():
            drop_label_decisions_by_label[row["current_label"]].append(row)

    retained_rows: list[dict[str, str]] = []
    dropped_rows: list[dict[str, str]] = []
    matched_decision_counts: Counter[str] = Counter()
    rows_matching_sample_decisions = 0
    rows_matching_label_decisions = 0

    for row in manifest_rows:
        matched_decisions = [
            *drop_sample_decisions_by_path.get(row["landmark_path"], []),
            *drop_label_decisions_by_label.get(row["label"], []),
        ]

        if not matched_decisions:
            retained_rows.append(row)
            continue

        if drop_sample_decisions_by_path.get(row["landmark_path"]):
            rows_matching_sample_decisions += 1
        if drop_label_decisions_by_label.get(row["label"]):
            rows_matching_label_decisions += 1

        for decision in matched_decisions:
            matched_decision_counts[decision["decision_id"]] += 1

        dropped_row = dict(row)
        dropped_row["matched_decision_ids"] = ";".join(decision["decision_id"] for decision in matched_decisions)
        dropped_row["matched_scopes"] = ";".join(decision["scope"] for decision in matched_decisions)
        dropped_row["matched_selected_actions"] = ";".join(decision["selected_action"] for decision in matched_decisions)
        dropped_row["matched_review_statuses"] = ";".join(decision.get("review_status", "") for decision in matched_decisions)
        dropped_row["matched_notes"] = "; ".join(
            note for note in (decision.get("notes", "").strip() for decision in matched_decisions) if note
        )
        dropped_rows.append(dropped_row)

    applied_drop_decision_rows = []
    for row in applicable_drop_rows:
        decision_with_audit = dict(row)
        decision_with_audit["matched_manifest_rows"] = matched_decision_counts.get(row["decision_id"], 0)
        decision_with_audit["applied_to_manifest"] = matched_decision_counts.get(row["decision_id"], 0) > 0
        applied_drop_decision_rows.append(decision_with_audit)

    clean_label_rows = build_clean_label_counts(retained_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "manifest.csv", retained_rows, manifest_fieldnames)
    write_csv(
        output_dir / "dropped_manifest_rows.csv",
        dropped_rows,
        [
            *manifest_fieldnames,
            "matched_decision_ids",
            "matched_scopes",
            "matched_selected_actions",
            "matched_review_statuses",
            "matched_notes",
        ],
    )
    write_csv(
        output_dir / "applied_drop_decisions.csv",
        applied_drop_decision_rows,
        [*decision_fieldnames, "matched_manifest_rows", "applied_to_manifest"],
    )
    write_csv(
        output_dir / "blocked_drop_decisions.csv",
        blocked_drop_rows,
        decision_fieldnames,
    )
    write_csv(
        output_dir / "label_counts.csv",
        clean_label_rows,
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

    summary = {
        "manifest_path": str(manifest_path),
        "decisions_path": str(decisions_path),
        "output_dir": str(output_dir),
        "raw_dataset_modified": False,
        "original_manifest_rows": len(manifest_rows),
        "cleaned_manifest_rows": len(retained_rows),
        "dropped_manifest_rows": len(dropped_rows),
        "original_unique_labels": len({row["label"] for row in manifest_rows}),
        "cleaned_unique_labels": len({row["label"] for row in retained_rows}),
        "decision_rows_total": len(decision_rows),
        "drop_decision_rows_applicable": len(applicable_drop_rows),
        "drop_sample_decisions_applicable": sum(
            1 for row in applicable_drop_rows if row.get("selected_action", "").strip().lower() == "drop_sample"
        ),
        "drop_label_decisions_applicable": sum(
            1 for row in applicable_drop_rows if row.get("selected_action", "").strip().lower() == "drop_label"
        ),
        "drop_decision_rows_blocked": len(blocked_drop_rows),
        "drop_decisions_without_manifest_match": sum(
            1 for row in applied_drop_decision_rows if not row["applied_to_manifest"]
        ),
        "rows_matching_sample_decisions": rows_matching_sample_decisions,
        "rows_matching_label_decisions": rows_matching_label_decisions,
        "selected_action_counts": dict(
            Counter(row.get("selected_action", "").strip() for row in decision_rows if row.get("selected_action", "").strip())
        ),
    }

    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply cleanup drop decisions to the generated manifest without modifying raw dataset files."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the generated manifest.csv file.",
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=DEFAULT_DECISIONS_PATH,
        help="Path to cleanup_decisions.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the cleaned manifest outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = apply_cleanup_decisions(
        manifest_path=args.manifest,
        decisions_path=args.decisions,
        output_dir=args.output_dir,
    )
    print("Applied cleanup decisions to manifest")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
