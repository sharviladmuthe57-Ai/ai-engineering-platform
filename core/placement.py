"""Deterministic, room-local validation for electrical component placement."""

from __future__ import annotations

import math
from typing import Any


PLACEMENT_VERSION = "v2"
WALL_HINT_SIDES = {
    "wall_n": "top", "high_wall_n": "top", "wall_s": "bottom", "counter_s": "bottom",
    "wall_e": "right", "high_wall_e": "right", "wall_w": "left", "high_wall_w": "left",
    "counter_w": "left", "corner_ne": "top", "corner_nw": "top",
    "corner_se": "bottom", "corner_sw": "bottom",
}


def preferred_door_source(room: dict[str, Any], hint: str) -> str | None:
    """Describe the trusted source used by a doorway-oriented placement."""
    if not (hint.startswith("near_door") or hint == "outside_door"):
        return None
    doors = list(room.get("doors", []))
    if not doors:
        return "wall_fallback"
    return "accepted_opening" if any(door.get("source") == "verified_opening_candidate" for door in doors) else "legacy_door"


class PlacementValidator:
    """Keep a room's components inside, separated, and safely wall-adjacent.

    This layer knows only the frozen room rectangle supplied by architectural
    analysis. It deliberately does not infer or rewrite room/wall geometry.
    """

    def __init__(self, room: dict[str, Any]):
        self.room = room
        self.occupied: list[tuple[float, float]] = []
        smallest = min(float(room["width"]), float(room["height"]))
        self.inset = min(0.30, max(0.12, smallest * 0.12))
        self.minimum_separation = min(0.35, max(0.14, smallest * 0.22))

    def validate(self, preferred: tuple[float, float], hint: str) -> tuple[tuple[float, float], dict[str, Any]]:
        original = (round(preferred[0], 3), round(preferred[1], 3))
        side = self._wall_side(original, hint)
        normalized = self._normalize(original, side)
        candidates = self._candidates(normalized, side)
        selected = next((point for point in candidates if self._clear(point)), None)
        if selected is None:
            # A very small room can be physically unable to satisfy the desired
            # separation. Select the most-separated valid room-local point,
            # deterministically, rather than leaving the room or jittering.
            selected = max(candidates, key=lambda point: min((math.dist(point, other) for other in self.occupied), default=math.inf))
        selected = (round(selected[0], 3), round(selected[1], 3))
        self.occupied.append(selected)
        adjusted = selected != original
        reasons = []
        if normalized != original:
            reasons.append("room_inset")
        if selected != normalized:
            reasons.append("co_location_resolution")
        return selected, {
            "placement_version": PLACEMENT_VERSION,
            "placement_method": "validated_room_local",
            "placement_adjusted": adjusted,
            "adjustment_reason": ",".join(reasons) if reasons else None,
            "original_position": original,
            "validated_position": selected,
            "wall_side": side,
            "collision_resolved": selected != normalized,
        }

    def _bounds(self) -> tuple[float, float, float, float]:
        room = self.room
        return (room["x"] + self.inset, room["y"] + self.inset,
                room["x"] + room["width"] - self.inset, room["y"] + room["height"] - self.inset)

    def _normalize(self, point: tuple[float, float], side: str) -> tuple[float, float]:
        left, bottom, right, top = self._bounds()
        x, y = min(max(point[0], left), right), min(max(point[1], bottom), top)
        if side == "left":
            x = left
        elif side == "right":
            x = right
        elif side == "bottom":
            y = bottom
        elif side == "top":
            y = top
        return (round(x, 3), round(y, 3))

    def _wall_side(self, point: tuple[float, float], hint: str) -> str | None:
        if hint in WALL_HINT_SIDES:
            return WALL_HINT_SIDES[hint]
        if hint.startswith("near_door") or hint == "outside_door":
            room = self.room
            distances = {
                "left": abs(point[0] - room["x"]), "right": abs(room["x"] + room["width"] - point[0]),
                "bottom": abs(point[1] - room["y"]), "top": abs(room["y"] + room["height"] - point[1]),
            }
            return min(distances, key=distances.get)
        return None

    def _candidates(self, point: tuple[float, float], side: str | None) -> list[tuple[float, float]]:
        step = self.minimum_separation
        if side in {"top", "bottom"}:
            shifts = [(0, 0), (step, 0), (-step, 0), (2 * step, 0), (-2 * step, 0)]
        elif side in {"left", "right"}:
            shifts = [(0, 0), (0, step), (0, -step), (0, 2 * step), (0, -2 * step)]
        else:
            shifts = [(0, 0), (0, step), (0, -step), (step, 0), (-step, 0),
                      (step, step), (-step, step), (step, -step), (-step, -step)]
        result = []
        for dx, dy in shifts:
            candidate = self._normalize((point[0] + dx, point[1] + dy), side)
            if candidate not in result:
                result.append(candidate)
        return result

    def _clear(self, point: tuple[float, float]) -> bool:
        return all(math.dist(point, other) >= self.minimum_separation for other in self.occupied)
