"""Pixel-polygon matching for benchmark evaluation only."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

MATCH_IOU = 0.35
POOR_BOUNDARY_IOU = 0.10
MULTI_SPACE_COVERAGE = 0.65


def polygon(item: dict[str, Any]) -> list[list[int]]:
    return item.get("polygon") or item.get("geometry_px", {}).get("polygon", [])


def polygon_metrics(expected: list[list[int]], detected: list[list[int]]) -> dict[str, float] | None:
    if len(expected) < 3 or len(detected) < 3:
        return None
    points = np.asarray(expected + detected, dtype=np.int32)
    min_x, min_y = points.min(axis=0)
    max_x, max_y = points.max(axis=0)
    offset = np.array([min_x - 1, min_y - 1])
    shape = (int(max_y - min_y + 3), int(max_x - min_x + 3))
    expected_mask = np.zeros(shape, dtype=np.uint8)
    detected_mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(expected_mask, [np.asarray(expected, dtype=np.int32) - offset], 1)
    cv2.fillPoly(detected_mask, [np.asarray(detected, dtype=np.int32) - offset], 1)
    intersection = int(np.count_nonzero(expected_mask & detected_mask))
    expected_area = int(np.count_nonzero(expected_mask))
    detected_area = int(np.count_nonzero(detected_mask))
    union = int(np.count_nonzero(expected_mask | detected_mask))
    ma, mb = cv2.moments(expected_mask), cv2.moments(detected_mask)
    return {"iou": intersection / union if union else 0.0,
            "intersection_area_px": intersection, "expected_area_px": expected_area,
            "detected_area_px": detected_area,
            "expected_coverage": intersection / expected_area if expected_area else 0.0,
            "detected_coverage": intersection / detected_area if detected_area else 0.0,
            "centroid_error_px": math.hypot(ma["m10"] / ma["m00"] - mb["m10"] / mb["m00"], ma["m01"] / ma["m00"] - mb["m01"] / mb["m00"])}


def evaluate(detected_rooms: list[dict[str, Any]], expected_spaces: list[dict[str, Any]]) -> dict[str, Any]:
    expected = [space for space in expected_spaces if space.get("status", "confirmed") == "confirmed" and len(polygon(space)) >= 3]
    detected = [room for room in detected_rooms if len(polygon(room)) >= 3]
    pairs = []
    for ei, truth in enumerate(expected):
        for di, candidate in enumerate(detected):
            metric = polygon_metrics(polygon(truth), polygon(candidate))
            if metric and metric["iou"] >= POOR_BOUNDARY_IOU:
                pairs.append((metric["iou"], ei, di, metric))

    matched_expected, matched_detected, correct = set(), set(), []
    for _, ei, di, metric in sorted(pairs, reverse=True):
        if ei not in matched_expected and di not in matched_detected and metric["iou"] >= MATCH_IOU:
            matched_expected.add(ei); matched_detected.add(di)
            correct.append({"expected_id": expected[ei]["id"], "detected_id": detected[di]["id"], **metric})

    remaining = [(ei, di, metric) for _, ei, di, metric in pairs if ei not in matched_expected and di not in matched_detected]
    used_expected, used_detected, merges, splits, poor = set(), set(), [], [], []
    for di in range(len(detected)):
        overlaps = [(ei, metric) for ei, pair_di, metric in remaining if pair_di == di]
        detected_area = detected[di].get("geometry_px", {}).get("area", 0)
        if len(overlaps) >= 2 and sum(metric["intersection_area_px"] for _, metric in overlaps) / max(detected_area, 1) >= MULTI_SPACE_COVERAGE:
            merges.append({"detected_id": detected[di]["id"], "expected_ids": [expected[ei]["id"] for ei, _ in overlaps]})
            used_detected.add(di); used_expected.update(ei for ei, _ in overlaps)
    for ei in range(len(expected)):
        overlaps = [(di, metric) for pair_ei, di, metric in remaining if pair_ei == ei and di not in used_detected]
        own = polygon_metrics(polygon(expected[ei]), polygon(expected[ei]))
        if len(overlaps) >= 2 and sum(metric["intersection_area_px"] for _, metric in overlaps) / own["expected_area_px"] >= MULTI_SPACE_COVERAGE:
            splits.append({"expected_id": expected[ei]["id"], "detected_ids": [detected[di]["id"] for di, _ in overlaps]})
            used_expected.add(ei); used_detected.update(di for di, _ in overlaps)
    for ei, di, metric in remaining:
        if ei not in used_expected and di not in used_detected:
            poor.append({"expected_id": expected[ei]["id"], "detected_id": detected[di]["id"], **metric})
            used_expected.add(ei); used_detected.add(di)

    missed = [expected[i] for i in range(len(expected)) if i not in matched_expected and i not in used_expected]
    false_positive = [detected[i] for i in range(len(detected)) if i not in matched_detected and i not in used_detected]
    ious = [item["iou"] for item in correct]
    return {"expected_count": len(expected), "detected_count": len(detected), "matched_count": len(correct),
            "mean_iou": round(float(np.mean(ious)), 3) if ious else None,
            "median_iou": round(float(np.median(ious)), 3) if ious else None,
            "precision": round(len(correct) / len(detected), 3) if detected else 0.0,
            "recall": round(len(correct) / len(expected), 3) if expected else None,
            "correct_rooms": correct, "false_positives": false_positive, "missed_rooms": missed,
            "merged_rooms": merges, "split_rooms": splits, "poor_boundary_matches": poor,
            "thresholds": {"match_iou": MATCH_IOU, "poor_boundary_iou": POOR_BOUNDARY_IOU, "multi_space_coverage": MULTI_SPACE_COVERAGE}}
