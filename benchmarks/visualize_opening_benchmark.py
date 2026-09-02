"""Render coordinate-level opening benchmark overlays."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

try:
    from .runner import load_annotation, run_plan
except ImportError:
    from runner import load_annotation, run_plan


def _line(canvas, item, color, label):
    if item.get("endpoints_px"):
        start, end = item["endpoints_px"]
        x1, y1, x2, y2 = start["x"], start["y"], end["x"], end["y"]
    else:
        center = item["position_px"]; half = item["width_px"] / 2
        if item.get("side") in ("top", "bottom"):
            x1, y1, x2, y2 = center["x"] - half, center["y"], center["x"] + half, center["y"]
        else:
            x1, y1, x2, y2 = center["x"], center["y"] - half, center["x"], center["y"] + half
    cv2.line(canvas, (round(x1), round(y1)), (round(x2), round(y2)), color, 3, cv2.LINE_AA)
    cv2.putText(canvas, label, (round((x1 + x2) / 2), round((y1 + y2) / 2)),
                cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1, cv2.LINE_AA)


def render(image_path: Path, annotation_path: Path, output_path: Path, opening_detector: str = "v1") -> None:
    result, annotation = run_plan(image_path, annotation_path, opening_detector=opening_detector), load_annotation(annotation_path)
    canvas = cv2.imread(str(image_path))
    expected = annotation["annotations"]["expected"]["openings"]
    for item in expected:
        color = (255, 180, 0) if item["type"] == "door" else (0, 220, 255)
        if item["status"] == "uncertain":
            color = (150, 150, 150)
        _line(canvas, item, color, f"E:{item['id']}")
    for kind, metrics in (("door", result["door_metrics"]), ("window", result["window_metrics"])):
        matches = {item["detected_id"] for item in metrics["matches"]}
        for item in metrics["false_positives"]:
            _line(canvas, item, (0, 0, 230), f"FP:{kind[0]} {float(item.get('confidence', 0)):.2f}")
        for item in result[f"detected_{kind}_candidates"]:
            if item["id"] in matches:
                _line(canvas, item, (30, 180, 30), f"M:{kind[0]} {float(item.get('confidence', 0)):.2f}")
        for item in metrics["false_negatives"]:
            _line(canvas, item, (220, 0, 220), f"MISS:{kind[0]}")
    for item in result.get("uncertain_opening_candidates", []):
        _line(canvas, item, (130, 130, 130), f"U {float(item.get('confidence', 0)):.2f}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("annotation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--detector", choices=("v1", "v2", "v3"), default="v1")
    args = parser.parse_args()
    render(args.image, args.annotation, args.output, args.detector)


if __name__ == "__main__":
    main()
