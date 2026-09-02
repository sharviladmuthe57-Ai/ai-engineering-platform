"""Deterministic, room-aware routing for the Phase-1 electrical engine.

The routing domain is the union of detected room rectangles plus narrow,
explicitly recorded transitions where two room boundaries nearly coincide. It
does not infer new architectural openings: pending/rejected candidates remain
outside this module. A route that cannot traverse the room graph falls back to
the legacy Manhattan route and declares that fallback in its metadata.
"""

from __future__ import annotations

from collections import defaultdict
import heapq
import math
from typing import Any


Point = tuple[float, float]
MAX_TRANSITION_GAP_M = 0.25
MIN_SHARED_SPAN_M = 0.12


def legacy_manhattan_route(start: Point, end: Point) -> list[Point]:
    """Preserved V1 route shape for explicit comparison/fallback paths."""
    sx, sy = start
    ex, ey = end
    horizontal_first = [start, (ex, sy), end]
    vertical_first = [start, (sx, ey), end]
    return horizontal_first if path_length(horizontal_first) <= path_length(vertical_first) else vertical_first


def path_length(points: list[Point]) -> float:
    return round(sum(abs(bx - ax) + abs(by - ay)
                     for (ax, ay), (bx, by) in zip(points, points[1:])), 2)


def _contains(room: dict[str, Any], point: Point, tolerance: float = 1e-9) -> bool:
    x, y = point
    return (room["x"] - tolerance <= x <= room["x"] + room["width"] + tolerance and
            room["y"] - tolerance <= y <= room["y"] + room["height"] + tolerance)


def _center(room: dict[str, Any]) -> Point:
    return (room["x"] + room["width"] / 2, room["y"] + room["height"] / 2)


def _inside_boundary_point(room: dict[str, Any], axis: str, value: float, other: float) -> Point:
    """Return an exact boundary anchor. Rectangle inclusion treats it as valid."""
    return (value, other) if axis == "vertical" else (other, value)


def _transition(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any] | None:
    """Return one conservative portal/bridge between two detected rectangles."""
    ax1, ay1 = first["x"], first["y"]
    ax2, ay2 = ax1 + first["width"], ay1 + first["height"]
    bx1, by1 = second["x"], second["y"]
    bx2, by2 = bx1 + second["width"], by1 + second["height"]

    overlap_x1, overlap_x2 = max(ax1, bx1), min(ax2, bx2)
    overlap_y1, overlap_y2 = max(ay1, by1), min(ay2, by2)
    if overlap_x2 - overlap_x1 >= MIN_SHARED_SPAN_M and overlap_y2 - overlap_y1 >= MIN_SHARED_SPAN_M:
        point = ((overlap_x1 + overlap_x2) / 2, (overlap_y1 + overlap_y2) / 2)
        return {"type": "overlapping_room_area", "from_point": point, "to_point": point, "gap_m": 0.0}

    candidates: list[tuple[float, str, float, float, float]] = []
    # (gap, axis, first boundary, second boundary, shared-span midpoint)
    shared_y1, shared_y2 = max(ay1, by1), min(ay2, by2)
    if shared_y2 - shared_y1 >= MIN_SHARED_SPAN_M:
        candidates.extend([
            (abs(ax2 - bx1), "vertical", ax2, bx1, (shared_y1 + shared_y2) / 2),
            (abs(bx2 - ax1), "vertical", ax1, bx2, (shared_y1 + shared_y2) / 2),
        ])
    shared_x1, shared_x2 = max(ax1, bx1), min(ax2, bx2)
    if shared_x2 - shared_x1 >= MIN_SHARED_SPAN_M:
        candidates.extend([
            (abs(ay2 - by1), "horizontal", ay2, by1, (shared_x1 + shared_x2) / 2),
            (abs(by2 - ay1), "horizontal", ay1, by2, (shared_x1 + shared_x2) / 2),
        ])
    valid = [candidate for candidate in candidates if candidate[0] <= MAX_TRANSITION_GAP_M]
    if not valid:
        return None
    gap, axis, first_boundary, second_boundary, shared_midpoint = min(valid, key=lambda item: (item[0], item[1], item[2]))
    first_point = _inside_boundary_point(first, axis, first_boundary, shared_midpoint)
    second_point = _inside_boundary_point(second, axis, second_boundary, shared_midpoint)
    return {"type": "near_shared_boundary", "from_point": first_point, "to_point": second_point, "gap_m": round(gap, 3)}


def build_room_graph(rooms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic bidirectional edges from actual rectangular geometry."""
    graph: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, first in enumerate(rooms):
        for second in rooms[index + 1:]:
            connection = _transition(first, second)
            if connection is None:
                continue
            forward = {"to": second["id"], **connection}
            backward = {
                "to": first["id"], "type": connection["type"],
                "from_point": connection["to_point"], "to_point": connection["from_point"],
                "gap_m": connection["gap_m"],
            }
            graph[first["id"]].append(forward)
            graph[second["id"]].append(backward)
    for room_id in graph:
        graph[room_id].sort(key=lambda edge: (edge["to"], edge["type"], edge["from_point"], edge["to_point"]))
    return graph


def _room_for_point(rooms: list[dict[str, Any]], point: Point) -> dict[str, Any] | None:
    containing = [room for room in rooms if _contains(room, point)]
    if containing:
        return min(containing, key=lambda room: (room["width"] * room["height"], room["id"]))
    return None


def _shortest_room_edges(graph: dict[str, list[dict[str, Any]]], start: str, target: str) -> list[dict[str, Any]] | None:
    if start == target:
        return []
    queue: list[tuple[float, tuple[str, ...], str, list[dict[str, Any]]]] = [(0.0, (start,), start, [])]
    best: dict[str, tuple[float, tuple[str, ...]]] = {start: (0.0, (start,))}
    while queue:
        cost, route_key, room_id, path = heapq.heappop(queue)
        if (cost, route_key) != best.get(room_id):
            continue
        if room_id == target:
            return path
        for edge in graph.get(room_id, []):
            next_room = edge["to"]
            edge_cost = math.dist(edge["from_point"], edge["to_point"]) + 1.0
            candidate = (round(cost + edge_cost, 6), route_key + (next_room,))
            if candidate < best.get(next_room, (math.inf, ())):
                best[next_room] = candidate
                heapq.heappush(queue, (candidate[0], candidate[1], next_room, path + [edge]))
    return None


def _append_orthogonal(points: list[Point], start: Point, end: Point) -> None:
    segment = legacy_manhattan_route(start, end)
    for point in segment[1:]:
        if point != points[-1]:
            points.append(point)


def route_component(
    db_pos: Point,
    component_pos: Point,
    component_room_id: str,
    rooms: list[dict[str, Any]],
) -> dict[str, Any]:
    """Route through the room graph, returning additive diagnostics and metadata."""
    by_id = {room["id"]: room for room in rooms}
    source_room = _room_for_point(rooms, db_pos)
    target_room = by_id.get(component_room_id)
    if source_room is None or target_room is None:
        return {
            "waypoints": legacy_manhattan_route(db_pos, component_pos), "routing_version": "v2",
            "architecture_aware": False, "fallback_used": True,
            "fallback_reason": "db_or_component_room_unavailable", "source_room": source_room.get("id") if source_room else None,
            "target_room": component_room_id, "traversed_rooms": [], "controlled_transitions": [],
        }

    graph = build_room_graph(rooms)
    edges = _shortest_room_edges(graph, source_room["id"], target_room["id"])
    if edges is None:
        return {
            "waypoints": legacy_manhattan_route(db_pos, component_pos), "routing_version": "v2",
            "architecture_aware": False, "fallback_used": True, "fallback_reason": "no_room_connectivity_path",
            "source_room": source_room["id"], "target_room": target_room["id"],
            "traversed_rooms": [source_room["id"]], "controlled_transitions": [],
        }

    points: list[Point] = [db_pos]
    traversed = [source_room["id"]]
    transitions = []
    current = db_pos
    for edge in edges:
        _append_orthogonal(points, current, edge["from_point"])
        if edge["to_point"] != points[-1]:
            points.append(edge["to_point"])
        transitions.append({
            "from_room": traversed[-1], "to_room": edge["to"], "type": edge["type"],
            "from_point": edge["from_point"], "to_point": edge["to_point"], "gap_m": edge["gap_m"],
        })
        traversed.append(edge["to"])
        current = edge["to_point"]
    _append_orthogonal(points, current, component_pos)
    return {
        "waypoints": points, "routing_version": "v2", "architecture_aware": True,
        "fallback_used": False, "fallback_reason": None, "source_room": source_room["id"],
        "target_room": target_room["id"], "traversed_rooms": traversed,
        "controlled_transitions": transitions,
    }
