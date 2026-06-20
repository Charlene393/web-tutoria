#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECISIONS_PATH = PROJECT_ROOT / "backend" / "reports" / "ksl_cleanup" / "cleanup_decisions.csv"


def split_flags(value: str) -> set[str]:
    return {flag for flag in value.split(";") if flag}


def infer_defaults(row: dict[str, str]) -> tuple[str, str, str]:
    recommended_action = row.get("recommended_action", "")
    current_label = row.get("current_label", "")
    label_flags = split_flags(row.get("label_flags", ""))
    sample_flags = split_flags(row.get("sample_flags", ""))

    if recommended_action == "rename_or_drop_label":
        return (
            "drop_label",
            "",
            "filename-like label, not a valid KSL gloss",
        )

    if recommended_action == "rename_label_or_drop_sample":
        if current_label == ".mp4" or "looks_like_filename" in label_flags:
            return (
                "drop_sample",
                "",
                "filename-like label; sample dropped until correct gloss is known",
            )
        return (
            "keep",
            "",
            "label needs manual rename review before changing dataset",
        )

    if recommended_action == "drop_or_reextract_sample":
        if "both_hands_missing_all_frames" in sample_flags:
            return (
                "drop_sample",
                "",
                "both hands missing across all frames",
            )
        if "pose_missing_all_frames" in sample_flags:
            return (
                "drop_sample",
                "",
                "pose landmarks missing across all frames",
            )
        if "missing_stickman_video" in sample_flags:
            return (
                "drop_sample",
                "",
                "stickman video missing; re-extraction needed",
            )
        return (
            "drop_sample",
            "",
            "sample quality too low for training or playback",
        )

    if recommended_action == "rename_label_review":
        return (
            "keep",
            "",
            "multiword or non-standard label; keep for now and review naming later",
        )

    if recommended_action == "review_short_sequence":
        return (
            "keep",
            "",
            "short sequence flagged; keep unless playback looks truncated",
        )

    if recommended_action == "review_hand_quality":
        if "left_hand_missing_all_frames" in sample_flags and "right_hand_missing_all_frames" not in sample_flags:
            return (
                "keep",
                "",
                "left hand missing across all frames; keep unless playback looks wrong",
            )
        if "right_hand_missing_all_frames" in sample_flags and "left_hand_missing_all_frames" not in sample_flags:
            return (
                "keep",
                "",
                "right hand missing across all frames; keep unless playback looks wrong",
            )
        if "short_sequence" in sample_flags:
            return (
                "keep",
                "",
                "short sequence with hand-quality flag; keep unless playback looks truncated",
            )
        return (
            "keep",
            "",
            "hand landmark quality flag; keep unless playback looks wrong",
        )

    return (
        "keep",
        "",
        "default keep decision; review manually if needed",
    )


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if reader.fieldnames is None:
            raise RuntimeError(f"No CSV header found in {path}")
        return reader.fieldnames, rows


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def prefill_cleanup_decisions(path: Path) -> dict[str, int]:
    if not path.exists():
        raise RuntimeError(f"cleanup decisions file not found: {path}")

    fieldnames, rows = read_rows(path)

    updated_selected_action = 0
    updated_target_label = 0
    updated_notes = 0

    for row in rows:
        selected_action, target_label, notes = infer_defaults(row)

        if not row.get("selected_action", "").strip():
            row["selected_action"] = selected_action
            updated_selected_action += 1
        if not row.get("target_label", "").strip() and target_label:
            row["target_label"] = target_label
            updated_target_label += 1
        if not row.get("notes", "").strip():
            row["notes"] = notes
            updated_notes += 1

    write_rows(path, fieldnames, rows)

    return {
        "rows": len(rows),
        "updated_selected_action": updated_selected_action,
        "updated_target_label": updated_target_label,
        "updated_notes": updated_notes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prefill safe default decisions into cleanup_decisions.csv."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DECISIONS_PATH,
        help="Path to cleanup_decisions.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = prefill_cleanup_decisions(args.input)
    print("Prefilled cleanup decisions")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
