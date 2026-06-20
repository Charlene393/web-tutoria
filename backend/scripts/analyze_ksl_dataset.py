#!/usr/bin/env python3

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from pathlib import Path

import numpy as np


def iter_landmark_files(root: Path):
    for file_path in root.glob("Batch */*/Extract/Landmarks/*.npy"):
        yield file_path


def inspect_sample(file_path: Path) -> dict[str, object]:
    sequence = np.load(file_path, allow_pickle=True)
    first_frame = sequence[0] if len(sequence) else {}
    return {
        "sequence_len": int(len(sequence)),
        "keys": sorted(first_frame.keys()) if isinstance(first_frame, dict) else [],
        "pose_points": len(first_frame.get("pose", [])) if isinstance(first_frame, dict) else 0,
        "left_hand_points": len(first_frame.get("left_hand", [])) if isinstance(first_frame, dict) else 0,
        "right_hand_points": len(first_frame.get("right_hand", [])) if isinstance(first_frame, dict) else 0,
        "face_points": len(first_frame.get("face", [])) if isinstance(first_frame, dict) else 0,
    }


def analyze_dataset(root: Path, hand_sample_limit: int) -> None:
    labels = Counter()
    signer_dirs = 0
    batch_dirs = 0
    landmark_files = list(iter_landmark_files(root))

    for batch_dir in sorted(root.iterdir()):
        if not batch_dir.is_dir():
            continue
        batch_dirs += 1
        for signer_dir in sorted(batch_dir.iterdir()):
            if signer_dir.is_dir():
                signer_dirs += 1

    for file_path in landmark_files:
        labels[file_path.stem] += 1

    if not landmark_files:
        print(f"No landmark files found under {root}")
        return

    sample = inspect_sample(landmark_files[0])
    counts = list(labels.values())

    sampled_frames = 0
    left_nonempty = 0
    right_nonempty = 0
    both_empty = 0

    for file_path in landmark_files[:hand_sample_limit]:
        sequence = np.load(file_path, allow_pickle=True)
        for frame in sequence:
            if not isinstance(frame, dict):
                continue
            sampled_frames += 1
            left_points = len(frame.get("left_hand", []))
            right_points = len(frame.get("right_hand", []))
            if left_points:
                left_nonempty += 1
            if right_points:
                right_nonempty += 1
            if not left_points and not right_points:
                both_empty += 1

    print("KSL dataset audit")
    print(f"root: {root}")
    print(f"batches: {batch_dirs}")
    print(f"signer_dirs: {signer_dirs}")
    print(f"landmark_files: {len(landmark_files)}")
    print(f"unique_labels: {len(labels)}")
    print(f"median_samples_per_label: {statistics.median(counts)}")
    print(f"min_samples_per_label: {min(counts)}")
    print(f"max_samples_per_label: {max(counts)}")
    print(f"labels_with_1_sample: {sum(1 for count in counts if count == 1)}")
    print(f"labels_with_lt_3_samples: {sum(1 for count in counts if count < 3)}")
    print(f"labels_with_ge_10_samples: {sum(1 for count in counts if count >= 10)}")
    print()
    print("sample_sequence")
    print(f"sequence_len: {sample['sequence_len']}")
    print(f"frame_keys: {sample['keys']}")
    print(f"pose_points: {sample['pose_points']}")
    print(f"left_hand_points: {sample['left_hand_points']}")
    print(f"right_hand_points: {sample['right_hand_points']}")
    print(f"face_points: {sample['face_points']}")
    print()
    print("hand_presence_sample")
    print(f"sampled_files: {min(len(landmark_files), hand_sample_limit)}")
    print(f"sampled_frames: {sampled_frames}")
    if sampled_frames:
        print(f"left_nonempty_pct: {left_nonempty / sampled_frames * 100:.2f}")
        print(f"right_nonempty_pct: {right_nonempty / sampled_frames * 100:.2f}")
        print(f"both_hands_empty_pct: {both_empty / sampled_frames * 100:.2f}")
    print()
    print("top_labels")
    for label, count in labels.most_common(20):
        print(f"{label}: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the KSL landmark dataset.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("KSL-Dataset/Pose Data"),
        help="Path to the pose dataset root.",
    )
    parser.add_argument(
        "--hand-sample-limit",
        type=int,
        default=200,
        help="How many landmark files to sample when estimating hand presence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyze_dataset(args.root, args.hand_sample_limit)


if __name__ == "__main__":
    main()
