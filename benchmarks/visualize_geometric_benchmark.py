"""Render expected/detected room geometry and benchmark classifications."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

try:
    from .runner import load_annotation, run_plan
except ImportError:
    from runner import load_annotation, run_plan


def _draw_polygon(canvas, polygon, color, label):
    points = np.asarray(polygon, dtype=np.int32)
    cv2.polylines(canvas, [points], True, color, 2, cv2.LINE_AA)
    x, y = points.min(axis=0)
    cv2.putText(canvas, label, (int(x) + 3, int(y) + 18),
                cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)


def render(image_path: Path, annotation_path: Path, output_path: Path) -> None:
    result = run_plan(image_path, annotation_path)
    annotation = load_annotation(annotation_path)
    geometry = result["geometric_room_detection"]
    canvas = cv2.imread(str(image_path))
    expected = {space["id"]: space for space in annotation["annotations"]["expected"].get("spaces", []) if space.get("status", "confirmed") == "confirmed"}
    detected = {room["id"]: room for room in result["detected_rooms"]}
    correct = {item["detected_id"] for item in geometry["correct_rooms"]}
    poor = {item["detected_id"] for item in geometry["poor_boundary_matches"]}
    missed = {item["id"] for item in geometry["missed_rooms"]}
    false_positive = {item["id"] for item in geometry["false_positives"]}

    for space_id, space in expected.items():
        _draw_polygon(canvas, space["polygon"], (0, 190, 255) if space_id not in missed else (190, 0, 255), f"E:{space_id}")
    for room_id, room in detected.items():
        polygon = room.get("geometry_px", {}).get("polygon", [])
        if len(polygon) < 3:
            continue
        color = (30, 180, 30) if room_id in correct else (0, 140, 255) if room_id in poor else (30, 30, 230) if room_id in false_positive else (180, 180, 180)
        _draw_polygon(canvas, polygon, color, f"D:{room_id}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("annotation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.image, args.annotation, args.output)


if __name__ == "__main__":
    main()
