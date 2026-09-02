"""Coordinate-level, type-sensitive opening benchmark matching."""

from __future__ import annotations

import math
from typing import Any


def _center(item: dict[str, Any]) -> tuple[float, float]:
    value = item.get("center_px") or item.get("position_px")
    return float(value["x"]), float(value["y"])


def _orientation(item: dict[str, Any]) -> str:
    wall = item.get("wall", {})
    if wall.get("orientation"):
        return wall["orientation"]
    return "horizontal" if item.get("side") in ("top", "bottom") else "vertical"


def _width(item: dict[str, Any]) -> float:
    return float(item.get("width_px", 0.0))


def validate_opening_annotations(openings: list[dict[str, Any]]) -> list[str]:
    errors = []
    for item in openings:
        prefix = item.get("id", "<missing id>")
        if item.get("type") not in {"door", "window"}:
            errors.append(f"{prefix}: invalid type")
        if item.get("status") not in {"confirmed", "uncertain"}:
            errors.append(f"{prefix}: invalid status")
        if not item.get("center_px") or len(item.get("endpoints_px", [])) != 2:
            errors.append(f"{prefix}: requires center_px and two endpoints_px")
        if _width(item) <= 0:
            errors.append(f"{prefix}: width_px must be positive")
        if _orientation(item) not in {"horizontal", "vertical"}:
            errors.append(f"{prefix}: invalid wall orientation")
    return errors


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax, ay = _center(a); bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _tolerance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(24.0, 0.60 * max(_width(a), _width(b)))


def _pair_metrics(truth: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float] | None:
    if truth["type"] != candidate.get("type") or _orientation(truth) != _orientation(candidate):
        return None
    distance = _distance(truth, candidate)
    tolerance = _tolerance(truth, candidate)
    width_error = abs(_width(truth) - _width(candidate))
    width_relative_error = width_error / _width(truth)
    if distance > tolerance or width_relative_error > 1.50:
        return None
    return {"center_error_px": distance, "width_error_px": width_error,
            "width_relative_error": width_relative_error,
            "score": distance / tolerance + width_relative_error * .25}


def evaluate_openings(detected: list[dict[str, Any]], expected: list[dict[str, Any]], opening_type: str) -> dict[str, Any]:
    """Greedy global one-to-one matching among confirmed coordinate annotations."""
    truth = [item for item in expected if item.get("type") == opening_type and item.get("status") == "confirmed"]
    candidates = [item for item in detected if item.get("type") == opening_type]
    pairs = []
    for truth_index, truth_item in enumerate(truth):
        for candidate_index, candidate in enumerate(candidates):
            metrics = _pair_metrics(truth_item, candidate)
            if metrics:
                pairs.append((metrics["score"], truth_index, candidate_index, metrics))
    used_truth, used_candidates, matches = set(), set(), []
    for _, truth_index, candidate_index, metrics in sorted(pairs):
        if truth_index not in used_truth and candidate_index not in used_candidates:
            used_truth.add(truth_index); used_candidates.add(candidate_index)
            matches.append({"expected_id": truth[truth_index]["id"], "detected_id": candidates[candidate_index]["id"], **metrics})

    duplicate_ids, wrong_type_ids = set(), set()
    for candidate_index, candidate in enumerate(candidates):
        if candidate_index in used_candidates:
            continue
        for match in matches:
            matched_truth = next(item for item in truth if item["id"] == match["expected_id"])
            if _orientation(matched_truth) == _orientation(candidate) and _distance(matched_truth, candidate) <= _tolerance(matched_truth, candidate):
                duplicate_ids.add(candidate["id"])
                break
        if candidate["id"] in duplicate_ids:
            continue
        for other in expected:
            if other.get("status") == "confirmed" and other.get("type") != opening_type and _orientation(other) == _orientation(candidate) and _distance(other, candidate) <= _tolerance(other, candidate):
                wrong_type_ids.add(candidate["id"])
                break

    false_positives = [item for index, item in enumerate(candidates) if index not in used_candidates]
    false_negatives = [item for index, item in enumerate(truth) if index not in used_truth]
    tp, fp, fn = len(matches), len(false_positives), len(false_negatives)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"evaluated": bool(truth), "ground_truth_count": len(truth), "detected_count": len(candidates),
            "true_positives": tp, "false_positives": false_positives, "false_negatives": false_negatives,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
            "matches": matches, "duplicate_detections": [item for item in candidates if item["id"] in duplicate_ids],
            "wrong_type_detections": [item for item in candidates if item["id"] in wrong_type_ids],
            "mean_localization_error_px": round(sum(item["center_error_px"] for item in matches) / tp, 2) if tp else None,
            "mean_width_error_px": round(sum(item["width_error_px"] for item in matches) / tp, 2) if tp else None,
            "mean_width_relative_error": round(sum(item["width_relative_error"] for item in matches) / tp, 3) if tp else None}
