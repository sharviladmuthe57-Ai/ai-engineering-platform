"""Candidate extraction and legacy adaptation for architectural openings.

This module consumes the existing raster wall mask and room bounding regions.
It does not change the legacy room contract until a user accepts a candidate.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

DOOR_MIN_PX, DOOR_MAX_PX = 12, 100
WINDOW_MIN_PX, WINDOW_MAX_PX = 8, 70


def _profile(mask: np.ndarray, x1: int, y1: int, x2: int, y2: int, axis: int) -> np.ndarray:
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(mask.shape[1], x2), min(mask.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return np.array([], dtype=np.uint8)
    return np.min(mask[y1:y2, x1:x2], axis=axis)


def _gaps(profile: np.ndarray, minimum: int, maximum: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(profile):
        if value < 50 and start is None:
            start = index
        elif value >= 50 and start is not None:
            if minimum <= index - start <= maximum:
                result.append((start, index))
            start = None
    if start is not None and minimum <= len(profile) - start <= maximum:
        result.append((start, len(profile)))
    return result


def _confidence(width_px: int, kind: str, side: str) -> float:
    """A transparent heuristic, not a learned confidence score."""
    low, high = (DOOR_MIN_PX, DOOR_MAX_PX) if kind == "door" else (WINDOW_MIN_PX, WINDOW_MAX_PX)
    target = (low + high) / 2
    score = 0.52 + 0.32 * max(0.0, 1.0 - abs(width_px - target) / target)
    if kind == "window" and side in ("top", "right"):
        score += 0.06
    return round(min(score, 0.92), 2)


def extract_opening_candidates(
    wall_mask: np.ndarray,
    regions: list[dict[str, Any]],
    *,
    scale_x_m_per_px: float,
    scale_y_m_per_px: float,
) -> list[dict[str, Any]]:
    """Return unverified candidates derived from room-boundary wall gaps."""
    candidates: list[dict[str, Any]] = []
    wall_specs = (
        ("top", lambda r: (r["x"], r["y"] - 5, r["x"] + r["w"], r["y"] + 5, 0)),
        ("bottom", lambda r: (r["x"], r["y"] + r["h"] - 5, r["x"] + r["w"], r["y"] + r["h"] + 5, 0)),
        ("left", lambda r: (r["x"] - 5, r["y"], r["x"] + 5, r["y"] + r["h"], 1)),
        ("right", lambda r: (r["x"] + r["w"] - 5, r["y"], r["x"] + r["w"] + 5, r["y"] + r["h"], 1)),
    )

    for room_index, region in enumerate(regions, start=1):
        room_id = f"room_{room_index}"
        for side, bounds_fn in wall_specs:
            x1, y1, x2, y2, axis = bounds_fn(region)
            profile = _profile(wall_mask, x1, y1, x2, y2, axis)
            for kind, minimum, maximum in (
                ("door", DOOR_MIN_PX, DOOR_MAX_PX),
                ("window", WINDOW_MIN_PX, WINDOW_MAX_PX),
            ):
                if kind == "window" and side not in ("top", "right"):
                    continue
                for start, end in _gaps(profile, minimum, maximum):
                    width_px = end - start
                    offset_px = (start + end) / 2
                    if side in ("top", "bottom"):
                        x_px = region["x"] + offset_px
                        y_px = region["y"] if side == "top" else region["y"] + region["h"]
                        width_m = width_px * scale_x_m_per_px
                    else:
                        x_px = region["x"] if side == "left" else region["x"] + region["w"]
                        y_px = region["y"] + offset_px
                        width_m = width_px * scale_y_m_per_px
                    candidates.append({
                        "id": f"opening_{kind}_{room_index}_{side}_{start}_{end}",
                        "type": kind,
                        "room_id": room_id,
                        "position_px": {"x": round(x_px, 1), "y": round(y_px, 1)},
                        "side": side,
                        "wall_location": side,
                        "offset_px": round(offset_px, 1),
                        "width_px": int(width_px),
                        "approx_width_m": round(width_m, 2),
                        "scale_x_m_per_px": round(scale_x_m_per_px, 8),
                        "scale_y_m_per_px": round(scale_y_m_per_px, 8),
                        "confidence": _confidence(width_px, kind, side),
                        "detection_method": "wall_mask_boundary_gap_v1",
                        "provenance": {"source": "cv_wall_mask", "region_index": room_index - 1},
                        "verification_status": "pending",
                    })
    return candidates


def apply_verified_openings_to_rooms(
    rooms: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Adapt accepted candidates to legacy door/window fields.

    Pending and rejected candidates never modify legacy room data. An accepted
    opening replaces only its own type for that room.
    """
    adapted = deepcopy(rooms)
    by_room: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for candidate in candidates or []:
        if candidate.get("verification_status") != "accepted":
            continue
        kind = candidate.get("type")
        if kind not in ("door", "window"):
            continue
        by_room.setdefault(candidate.get("room_id"), {}).setdefault(kind, []).append(candidate)

    for room in adapted:
        for kind, values in by_room.get(room.get("id"), {}).items():
            converted = []
            for value in values:
                side = value.get("side", value.get("wall_location", "bottom"))
                offset_px = float(value.get("offset_px", 0.0))
                width_px = float(value.get("width_px", 0.0))
                is_horizontal = side in ("top", "bottom")
                scale = value.get("scale_x_m_per_px", 1.0) if is_horizontal else value.get("scale_y_m_per_px", 1.0)
                position = offset_px * scale if is_horizontal else room["height"] - offset_px * scale
                converted.append({
                    "wall": side,
                    "position": round(max(0.0, position), 2),
                    "width": round(max(0.1, width_px * scale), 2),
                    "source": "verified_opening_candidate",
                    "candidate_id": value.get("id"),
                })
            room[f"{kind}s"] = converted
    return adapted
