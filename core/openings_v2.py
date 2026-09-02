"""Exterior-wall-aware opening proposals and conservative V2 classification."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .openings import _gaps, _profile
from .opening_symbols import classify_symbol_aware


def _orientation(side: str) -> str:
    return "horizontal" if side in ("top", "bottom") else "vertical"


def _wall_bounds(region: dict[str, Any], side: str) -> tuple[int, int, int, int, int]:
    if side == "top":
        return region["x"], region["y"] - 5, region["x"] + region["w"], region["y"] + 5, 0
    if side == "bottom":
        return region["x"], region["y"] + region["h"] - 5, region["x"] + region["w"], region["y"] + region["h"] + 5, 0
    if side == "left":
        return region["x"] - 5, region["y"], region["x"] + 5, region["y"] + region["h"], 1
    return region["x"] + region["w"] - 5, region["y"], region["x"] + region["w"] + 5, region["y"] + region["h"], 1


def _exterior_sides(regions: list[dict[str, Any]], W: int, H: int) -> set[tuple[int, str]]:
    if not regions:
        return set()
    x0 = min(region["x"] for region in regions)
    y0 = min(region["y"] for region in regions)
    x1 = max(region["x"] + region["w"] for region in regions)
    y1 = max(region["y"] + region["h"] for region in regions)
    tolerance = max(8, int(min(W, H) * .018))
    result = set()
    for index, region in enumerate(regions):
        if abs(region["y"] - y0) <= tolerance: result.add((index, "top"))
        if abs(region["y"] + region["h"] - y1) <= tolerance: result.add((index, "bottom"))
        if abs(region["x"] - x0) <= tolerance: result.add((index, "left"))
        if abs(region["x"] + region["w"] - x1) <= tolerance: result.add((index, "right"))
    return result


def _point(region: dict[str, Any], side: str, start: int, end: int) -> tuple[float, float]:
    offset = (start + end) / 2
    if side in ("top", "bottom"):
        return region["x"] + offset, region["y"] if side == "top" else region["y"] + region["h"]
    return region["x"] if side == "left" else region["x"] + region["w"], region["y"] + offset


def _endpoints(region: dict[str, Any], side: str, start: int, end: int) -> list[dict[str, int]]:
    if side in ("top", "bottom"):
        y = region["y"] if side == "top" else region["y"] + region["h"]
        return [{"x": region["x"] + start, "y": y}, {"x": region["x"] + end, "y": y}]
    x = region["x"] if side == "left" else region["x"] + region["w"]
    return [{"x": x, "y": region["y"] + start}, {"x": x, "y": region["y"] + end}]


def _inner_ink_density(binary: np.ndarray, proposal: dict[str, Any], region: dict[str, Any]) -> float:
    x, y = proposal["position_px"]["x"], proposal["position_px"]["y"]
    depth = max(12, int(min(region["w"], region["h"]) * .12))
    half = max(8, proposal["width_px"] // 2)
    side = proposal["side"]
    if side == "top": crop = binary[int(y):int(y)+depth, max(0, int(x)-half):int(x)+half]
    elif side == "bottom": crop = binary[int(y)-depth:int(y), max(0, int(x)-half):int(x)+half]
    elif side == "left": crop = binary[max(0, int(y)-half):int(y)+half, int(x):int(x)+depth]
    else: crop = binary[max(0, int(y)-half):int(y)+half, int(x)-depth:int(x)]
    return float(np.count_nonzero(crop > 0)) / crop.size if crop.size else 1.0


def _parallel_line_score(binary: np.ndarray, proposal: dict[str, Any]) -> float:
    endpoints = proposal["endpoints_px"]
    x1, y1 = endpoints[0]["x"], endpoints[0]["y"]
    x2, y2 = endpoints[1]["x"], endpoints[1]["y"]
    pad = max(5, proposal["width_px"] // 8)
    if proposal["orientation"] == "horizontal":
        crop = binary[max(0, y1-pad):min(binary.shape[0], y1+pad+1), max(0, x1):min(binary.shape[1], x2)]
        lengths = np.sum(crop > 0, axis=1)
    else:
        crop = binary[max(0, y1):min(binary.shape[0], y2), max(0, x1-pad):min(binary.shape[1], x1+pad+1)]
        lengths = np.sum(crop > 0, axis=0)
    if not lengths.size: return 0.0
    return round(min(1.0, np.count_nonzero(lengths >= crop.shape[1 if proposal["orientation"] == "horizontal" else 0] * .45) / 3), 2)


def _cluster(proposals: list[dict[str, Any]], short_side: int) -> list[dict[str, Any]]:
    clustered: list[dict[str, Any]] = []
    distance = max(12, int(short_side * .018))
    for proposal in sorted(proposals, key=lambda item: item["width_px"], reverse=True):
        existing = next((item for item in clustered if item["orientation"] == proposal["orientation"] and abs(item["position_px"]["x"] - proposal["position_px"]["x"]) <= distance and abs(item["position_px"]["y"] - proposal["position_px"]["y"]) <= distance), None)
        if existing:
            existing["merged_proposal_ids"].append(proposal["proposal_id"])
            existing["support_count"] += 1
            existing["exterior_wall"] = existing["exterior_wall"] or proposal["exterior_wall"]
        else:
            proposal["merged_proposal_ids"] = [proposal["proposal_id"]]
            proposal["support_count"] = 1
            clustered.append(proposal)
    return clustered


def extract_opening_candidates_v2(wall_mask: np.ndarray, binary: np.ndarray, regions: list[dict[str, Any]], *, scale_x_m_per_px: float, scale_y_m_per_px: float, W: int, H: int, symbol_aware: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return V2 candidates plus proposal-stage counts; V1 remains untouched."""
    exterior = _exterior_sides(regions, W, H)
    raw = []
    min_gap, max_gap = max(10, int(min(W, H) * .018)), max(70, int(min(W, H) * .23))
    for index, region in enumerate(regions):
        for side in ("top", "bottom", "left", "right"):
            x1, y1, x2, y2, axis = _wall_bounds(region, side)
            for start, end in _gaps(_profile(wall_mask, x1, y1, x2, y2, axis), min_gap, max_gap):
                width = end - start
                px, py = _point(region, side, start, end)
                raw.append({"proposal_id": f"v2_raw_{index}_{side}_{start}_{end}", "room_id": f"room_{index+1}", "region_index": index, "side": side, "wall_location": side, "orientation": _orientation(side), "position_px": {"x": round(px, 1), "y": round(py, 1)}, "endpoints_px": _endpoints(region, side, start, end), "width_px": width, "exterior_wall": (index, side) in exterior})
    clustered = _cluster(raw, min(W, H))
    candidates = []
    for proposal in clustered:
        region = regions[proposal["region_index"]]
        fixture_penalty = round(min(1.0, _inner_ink_density(binary, proposal, region) * 3.0), 2)
        parallel_score = _parallel_line_score(binary, proposal) if proposal["exterior_wall"] else 0.0
        relative_width = proposal["width_px"] / max(min(region["w"], region["h"]), 1)
        width_score = round(min(1.0, relative_width / .35), 2)
        symbol_evidence = None
        if symbol_aware:
            v2_window_eligible = proposal["exterior_wall"] and parallel_score >= .33 and fixture_penalty < .72
            v2_door_eligible = ((not proposal["exterior_wall"] and proposal["width_px"] >= max(22, int(min(W, H) * .035)) and fixture_penalty < .36) or (proposal["exterior_wall"] and proposal["width_px"] >= max(40, int(min(W, H) * .07)) and fixture_penalty < .42))
            symbol_evidence = classify_symbol_aware(
                binary, wall_mask, proposal, region, exterior_score=float(proposal["exterior_wall"]),
                parallel_window_score=parallel_score, fixture_noise_penalty=fixture_penalty,
                v2_door_eligible=v2_door_eligible, v2_window_eligible=v2_window_eligible)
            kind = str(symbol_evidence["classification"])
            confidence = float(symbol_evidence["confidence"])
        else:
            kind = None
            if proposal["exterior_wall"] and parallel_score >= .33 and fixture_penalty < .72:
                kind = "window"
            elif (not proposal["exterior_wall"] and proposal["width_px"] >= max(22, int(min(W, H) * .035)) and fixture_penalty < .36):
                kind = "door"
            elif proposal["exterior_wall"] and proposal["width_px"] >= max(40, int(min(W, H) * .07)) and fixture_penalty < .42:
                kind = "door"
            if not kind:
                continue
            confidence = .30 + .20 * width_score + .20 * min(1.0, proposal["support_count"] / 2) + (.22 * parallel_score if kind == "window" else .12 * (1 - fixture_penalty))
        scale = scale_x_m_per_px if proposal["orientation"] == "horizontal" else scale_y_m_per_px
        evidence = {"gap_score": 1.0, "exterior_wall": proposal["exterior_wall"], "parallel_line_score": parallel_score, "width_score": width_score, "fixture_noise_penalty": fixture_penalty, "wall_continuity_score": round(min(1.0, proposal["support_count"] / 2), 2)}
        if symbol_evidence:
            evidence.update(symbol_evidence)
        candidates.append({"id": f"opening_v2_{kind}_{proposal['proposal_id']}", "type": kind, "room_id": proposal["room_id"], "position_px": proposal["position_px"], "side": proposal["side"], "wall_location": proposal["wall_location"], "offset_px": None, "width_px": proposal["width_px"], "approx_width_m": round(proposal["width_px"] * scale, 2), "scale_x_m_per_px": round(scale_x_m_per_px, 8), "scale_y_m_per_px": round(scale_y_m_per_px, 8), "confidence": round(min(.92, confidence), 2), "detection_method": "symbol_aware_opening_v3" if symbol_aware else "exterior_wall_aware_v2", "provenance": {"source": "cv_wall_mask", "version": "v3" if symbol_aware else "v2", "raw_proposal_ids": proposal["merged_proposal_ids"], "evidence": evidence}, "verification_status": "pending", "endpoints_px": proposal["endpoints_px"]})
    return candidates, {"raw_proposals": len(raw), "deduplicated_proposals": len(clustered), "final_candidates": len(candidates)}
