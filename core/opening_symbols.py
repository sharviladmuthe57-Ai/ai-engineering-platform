"""Local, geometry-constrained architectural symbol evidence for V2 proposals."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _interior_normal(side: str) -> tuple[float, float]:
    return {"top": (0.0, 1.0), "bottom": (0.0, -1.0),
            "left": (1.0, 0.0), "right": (-1.0, 0.0)}[side]


def _crop(binary: np.ndarray, proposal: dict[str, Any], region: dict[str, Any]) -> tuple[np.ndarray, int, int]:
    """Return a local crop that extends primarily into the proposal's room."""
    x, y = proposal["position_px"]["x"], proposal["position_px"]["y"]
    width = max(16, int(proposal["width_px"]))
    depth = max(24, int(width * 1.35))
    span = max(24, int(width * 1.35))
    nx, ny = _interior_normal(proposal["side"])
    x1 = int(round(x - span + min(0, nx * depth)))
    x2 = int(round(x + span + max(0, nx * depth)))
    y1 = int(round(y - span + min(0, ny * depth)))
    y2 = int(round(y + span + max(0, ny * depth)))
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(binary.shape[1], x2), min(binary.shape[0], y2)
    return binary[y1:y2, x1:x2], x1, y1


def _leaf_score(binary: np.ndarray, proposal: dict[str, Any], region: dict[str, Any]) -> float:
    crop, ox, oy = _crop(binary, proposal, region)
    width = float(max(16, proposal["width_px"]))
    if crop.size == 0:
        return 0.0
    edges = cv2.Canny(crop, 40, 120)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=max(8, int(width * .18)),
        minLineLength=max(8, int(width * .33)), maxLineGap=max(4, int(width * .11)),
    )
    if lines is None:
        return 0.0
    nx, ny = _interior_normal(proposal["side"])
    hinges = [(endpoint["x"], endpoint["y"]) for endpoint in proposal["endpoints_px"]]
    best = 0.0
    for x1, y1, x2, y2 in lines[:, 0]:
        a, b = (x1 + ox, y1 + oy), (x2 + ox, y2 + oy)
        length = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        if not (.50 * width <= length <= 1.30 * width):
            continue
        for hx, hy in hinges:
            near, far = (a, b) if np.hypot(a[0] - hx, a[1] - hy) <= np.hypot(b[0] - hx, b[1] - hy) else (b, a)
            hinge_distance = float(np.hypot(near[0] - hx, near[1] - hy))
            if hinge_distance > max(6.0, width * .14):
                continue
            vx, vy = far[0] - hx, far[1] - hy
            direction = (vx * nx + vy * ny) / max(np.hypot(vx, vy), 1.0)
            if direction < .52:
                continue
            score = .25 + .30 * min(1.0, length / width) + .35 * min(1.0, direction)
            best = max(best, score)
    return round(min(1.0, best), 2)


def _swing_arc_score(binary: np.ndarray, proposal: dict[str, Any], region: dict[str, Any]) -> float:
    """Score dotted/solid circular support centered at a true opening endpoint."""
    width = float(max(16, proposal["width_px"]))
    nx, ny = _interior_normal(proposal["side"])
    best = 0.0
    crop, ox, oy = _crop(binary, proposal, region)
    if crop.size == 0:
        return 0.0
    softened = cv2.GaussianBlur(crop, (5, 5), 1.1)
    circles = cv2.HoughCircles(
        softened, cv2.HOUGH_GRADIENT, dp=1.0, minDist=max(10, int(width * .45)),
        param1=40, param2=max(7, int(width * .13)),
        minRadius=max(7, int(width * .42)), maxRadius=max(9, int(width * 1.18)),
    )
    if circles is None:
        return 0.0
    support = cv2.dilate((binary > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
    for endpoint in proposal["endpoints_px"]:
        hx, hy = float(endpoint["x"]), float(endpoint["y"])
        for cx, cy, radius in circles[0]:
            cx, cy = float(cx + ox), float(cy + oy)
            if np.hypot(cx - hx, cy - hy) > max(7.0, width * .16):
                continue
            hits, bins = 0, set()
            # Only inspect the interior half-disc: arbitrary nearby circles do
            # not qualify unless their geometry is anchored at this hinge.
            for index, angle in enumerate(np.linspace(0, 2 * np.pi, 96, endpoint=False)):
                dx, dy = np.cos(angle), np.sin(angle)
                if dx * nx + dy * ny < .16:
                    continue
                x, y = int(round(hx + radius * dx)), int(round(hy + radius * dy))
                if 0 <= x < support.shape[1] and 0 <= y < support.shape[0] and support[y, x]:
                    hits += 1
                    bins.add(index // 6)
            # Architectural swings may be dashed; separated angular hits are
            # stronger evidence than a single blob or fixture edge.
            sample_count = sum(1 for angle in np.linspace(0, 2 * np.pi, 96, endpoint=False)
                               if np.cos(angle) * nx + np.sin(angle) * ny >= .16)
            ratio = hits / max(sample_count, 1)
            if ratio >= .10 and len(bins) >= 5:
                best = max(best, min(1.0, .25 + ratio * 2.0 + len(bins) / 42))
    return round(best, 2)


def classify_symbol_aware(
    binary: np.ndarray,
    wall_mask: np.ndarray,
    proposal: dict[str, Any],
    region: dict[str, Any],
    *,
    exterior_score: float,
    parallel_window_score: float,
    fixture_noise_penalty: float,
    v2_door_eligible: bool,
    v2_window_eligible: bool,
) -> dict[str, float | str]:
    """Classify one *existing* V2 proposal without generating a new proposal."""
    # Structural wall strokes explain gap context, not a swing. Removing them
    # before local symbol scoring prevents window bands and wall continuations
    # from impersonating a door leaf or circular arc.
    symbols = binary.copy()
    symbols[wall_mask > 0] = 0
    leaf = _leaf_score(symbols, proposal, region)
    arc = _swing_arc_score(symbols, proposal, region)
    relative_width = proposal["width_px"] / max(min(region["w"], region["h"]), 1)
    width_score = min(1.0, relative_width / .35)
    symbol_door = min(1.0, .58 * max(leaf, arc) + .42 * min(leaf, arc) + (.10 if leaf >= .62 and arc >= .48 else 0.0))
    door_score = (.13 + .17 * (1.0 - exterior_score) + .16 * width_score +
                  .12 * (1.0 - fixture_noise_penalty) + .44 * leaf + .48 * arc + .18 * min(leaf, arc))
    window_score = (.10 + .20 * exterior_score + .38 * parallel_window_score +
                    .14 * width_score + .09 * (1.0 - fixture_noise_penalty) +
                    .14 * (1.0 - symbol_door))
    door_score, window_score = min(1.0, door_score), min(1.0, window_score)

    # Symbol evidence gets precedence over exterior parallel bands. For weak
    # evidence, keep a reviewable candidate instead of inventing a type.
    strong_symbol_door = (leaf >= .62 and arc >= .42) or (arc >= .65 and fixture_noise_penalty < .30)
    if strong_symbol_door and fixture_noise_penalty < .35 and door_score >= .52:
        kind = "door"
    elif v2_window_eligible and window_score >= .58 and window_score >= door_score + .08:
        kind = "window"
    elif v2_door_eligible and fixture_noise_penalty < .34:
        kind = "door"
    elif v2_door_eligible and leaf >= .70 and fixture_noise_penalty < .42:
        kind = "door"
    else:
        kind = "uncertain"
    confidence = (door_score if kind == "door" else window_score if kind == "window"
                  else max(0.25, min(.70, abs(door_score - window_score) + .25)))
    return {
        "classification": kind, "confidence": round(float(confidence), 2),
        "swing_arc_score": arc, "door_leaf_score": leaf,
        "parallel_window_score": round(parallel_window_score, 2),
        "exterior_score": round(exterior_score, 2),
        "fixture_noise_penalty": round(fixture_noise_penalty, 2),
        "door_score": round(door_score, 2), "window_score": round(window_score, 2),
    }

