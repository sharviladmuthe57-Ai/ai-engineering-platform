"""Reproducible benchmark runner for immutable architectural-plan fixtures."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json
import math

try:
    from .geometric import evaluate as geometric_room_result
except ImportError:  # Supports `python benchmarks/run_benchmark.py`.
    from geometric import evaluate as geometric_room_result


def load_annotation(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _room_type(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def room_detection_result(detected_rooms: list[dict[str, Any]], expected_rooms: list[dict[str, Any]]) -> dict[str, Any]:
    expected = Counter(_room_type(room["type"]) for room in expected_rooms)
    detected = Counter(_room_type(room.get("name", "unknown")) for room in detected_rooms)
    matched = sum(min(expected[name], detected[name]) for name in expected)
    total_expected = sum(expected.values())
    total_detected = sum(detected.values())
    return {
        "expected_count": total_expected,
        "detected_count": total_detected,
        "matched_by_type": matched,
        "false_negative_by_type": list((expected - detected).elements()),
        "false_positive_by_type": list((detected - expected).elements()),
        "recall_by_type": round(matched / total_expected, 3) if total_expected else None,
        "precision_by_type": round(matched / total_detected, 3) if total_detected else None,
    }


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(a["position_px"]["x"] - b["position_px"]["x"], a["position_px"]["y"] - b["position_px"]["y"])


def opening_detection_result(
    detected: list[dict[str, Any]], expected: list[dict[str, Any]], opening_type: str
) -> dict[str, Any]:
    """One-to-one point/side matching against only confident expected openings."""
    candidates = [item for item in detected if item.get("type") == opening_type]
    truth = [item for item in expected if item.get("type") == opening_type and item.get("status") == "expected"]
    if not truth:
        return {
            "evaluated": False,
            "reason": "No confident expected annotations; uncertain observations are intentionally excluded.",
            "detected_count": len(candidates),
            "expected_count": 0,
            "precision": None,
            "recall": None,
            "false_positives": [],
            "false_negatives": [],
        }

    unused = set(range(len(candidates)))
    matches = []
    for truth_item in truth:
        tolerance = truth_item.get("tolerance_px", 24)
        match = next(
            (
                index for index in unused
                if candidates[index].get("side") == truth_item.get("side")
                and _distance(candidates[index], truth_item) <= tolerance
            ),
            None,
        )
        if match is not None:
            unused.remove(match)
            matches.append((truth_item, candidates[match]))

    false_negatives = [item for item in truth if not any(item is pair[0] for pair in matches)]
    false_positives = [candidates[index] for index in sorted(unused)]
    return {
        "evaluated": True,
        "detected_count": len(candidates),
        "expected_count": len(truth),
        "true_positives": len(matches),
        "precision": round(len(matches) / len(candidates), 3) if candidates else 0.0,
        "recall": round(len(matches) / len(truth), 3) if truth else None,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def confidence_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {"0.00-0.49": 0, "0.50-0.69": 0, "0.70-0.84": 0, "0.85-1.00": 0}
    for candidate in candidates:
        confidence = float(candidate.get("confidence", 0.0))
        if confidence < 0.50:
            buckets["0.00-0.49"] += 1
        elif confidence < 0.70:
            buckets["0.50-0.69"] += 1
        elif confidence < 0.85:
            buckets["0.70-0.84"] += 1
        else:
            buckets["0.85-1.00"] += 1
    return buckets


def run_plan(image_path: str | Path, annotation_path: str | Path) -> dict[str, Any]:
    """Run the unchanged CV entry point and compare its output to annotations."""
    from core.cv_analyzer import analyze_floor_plan

    annotation = load_annotation(annotation_path)
    cv_result = analyze_floor_plan(str(image_path))
    if not cv_result["success"]:
        return {"plan_id": annotation["plan_id"], "success": False, "error": cv_result.get("error")}

    data = cv_result["data"]
    candidates = data.get("opening_candidates", [])
    expected = annotation["annotations"]["expected"]
    return {
        "plan_id": annotation["plan_id"],
        "success": True,
        "dimensions_and_scale": {
            "drawing_dimensions": annotation["drawing_dimensions"],
            "detected_site": data.get("site"),
            "detected_scale_mppx": data.get("_debug", {}).get("scale_mppx"),
            "scale_note": "The runner does not convert annotated feet labels into metres.",
        },
        "detected_rooms": data.get("rooms", []),
        "detected_door_candidates": [item for item in candidates if item["type"] == "door"],
        "detected_window_candidates": [item for item in candidates if item["type"] == "window"],
        "room_detection": room_detection_result(data.get("rooms", []), expected["rooms"]),
        "geometric_room_detection": geometric_room_result(
            data.get("rooms", []), expected.get("spaces", [])),
        "door_metrics": opening_detection_result(candidates, expected["openings"], "door"),
        "window_metrics": opening_detection_result(candidates, expected["openings"], "window"),
        "confidence_distribution": confidence_distribution(candidates),
        "annotation_status": annotation["annotations"],
    }
