"""Read-only benchmark and sanity audit for the frozen electrical engine."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import math
import statistics

import cv2
import numpy as np

from core.cv_analyzer import analyze_floor_plan, make_wall_mask, preprocess
from core.geometry import BUFFER, generate_layout, path_length
from core.openings import apply_verified_openings_to_rooms
from core.rules_engine import COMPONENTS, get_rules

from .electrical_expectations import category_for, expectation_for, validate_expectations


WALL_MOUNTED = {
    "switch_1way", "switch_2way", "outlet_5pin", "outlet_2pin", "ac_point",
    "geyser_point", "tv_point", "wifi_point", "fridge_point", "chimney_point",
    "ro_point", "microwave_point", "washing_point", "doorbell_point", "exhaust_fan",
}
CEILING_COMPONENTS = {"ceiling_light", "ceiling_fan", "smoke_detector"}
COLORS = {
    "light": (0, 220, 255), "fan": (80, 220, 80), "switch": (255, 160, 0),
    "switch2": (255, 190, 80), "outlet": (50, 60, 230), "outlet2": (90, 110, 255),
    "ac": (180, 70, 180), "exhaust": (100, 240, 100), "db": (40, 40, 230),
    "default": (210, 210, 210),
}


def _finite(point: Any) -> bool:
    return (isinstance(point, (tuple, list)) and len(point) == 2 and
            all(isinstance(value, (int, float)) and math.isfinite(value) for value in point))


def _inside(point: tuple[float, float], room: dict[str, Any], tolerance: float = 1e-9) -> bool:
    x, y = point
    return (room["x"] - tolerance <= x <= room["x"] + room["width"] + tolerance and
            room["y"] - tolerance <= y <= room["y"] + room["height"] + tolerance)


def _wall_distance(point: tuple[float, float], room: dict[str, Any]) -> tuple[float, str]:
    x, y = point
    values = {
        "left": abs(x - room["x"]), "right": abs(room["x"] + room["width"] - x),
        "bottom": abs(y - room["y"]), "top": abs(room["y"] + room["height"] - y),
    }
    side = min(values, key=values.get)
    return round(values[side], 3), side


def _room_doors(room: dict[str, Any]) -> list[tuple[float, float]]:
    points = []
    for door in room.get("doors", []):
        side = door.get("wall", "bottom")
        position = float(door.get("position", room["width"] / 2))
        if side == "top":
            points.append((room["x"] + position, room["y"] + room["height"]))
        elif side == "bottom":
            points.append((room["x"] + position, room["y"]))
        elif side == "left":
            points.append((room["x"], room["y"] + position))
        else:
            points.append((room["x"] + room["width"], room["y"] + position))
    return points


def _rule_hints(room: dict[str, Any]) -> dict[str, str]:
    # The production output does not preserve the hint. This deterministic
    # lookup exposes the source rule for audit only; it never changes placement.
    return {component_id: hint for component_id, _quantity, hint in get_rules(room.get("name", "unknown"))}


def _world_to_px(point: tuple[float, float], scale_x: float, scale_y: float, image_height: int) -> tuple[int, int]:
    return round(point[0] / scale_x), round(image_height - point[1] / scale_y)


def _pixel_wall_collision(point: tuple[float, float], wall_mask: np.ndarray, scale_x: float, scale_y: float) -> bool | None:
    px, py = _world_to_px(point, scale_x, scale_y, wall_mask.shape[0])
    if not (0 <= px < wall_mask.shape[1] and 0 <= py < wall_mask.shape[0]):
        return None
    return bool(np.any(wall_mask[max(0, py - 2):py + 3, max(0, px - 2):px + 3] > 0))


def _component_records(layout: dict[str, Any], wall_mask: np.ndarray, scale_x: float, scale_y: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rooms = {room["id"]: room for room in layout["rooms"]}
    records, collisions = [], []
    by_room = defaultdict(list)
    for component in layout["placed_components"]:
        point = component.get("pos")
        room = rooms.get(component.get("room_id"))
        finite = _finite(point)
        point = tuple(point) if finite else (math.nan, math.nan)
        intended_inside = _inside(point, room) if finite and room else None
        building_rooms = [candidate["id"] for candidate in rooms.values() if finite and _inside(point, candidate)]
        building_inside = bool(building_rooms) if finite else False
        wall_distance, wall_side = _wall_distance(point, room) if finite and room else (None, None)
        doors = _room_doors(room) if room else []
        door_distance = min((math.dist(point, door) for door in doors), default=None) if finite else None
        hint = _rule_hints(room).get(component["comp_id"]) if room else "db_heuristic"
        threshold = min(.35, .15 * min(room["width"], room["height"])) if room else None
        record = {
            "id": component["id"], "component_type": component["comp_id"], "label": component["label"],
            "symbol": component.get("symbol"), "position_m": {"x": point[0], "y": point[1]},
            "room_id": component.get("room_id"), "room_type": component.get("room_name"),
            "quantity": component.get("qty", 1), "rule_hint": hint,
            "coordinates_finite": finite, "inside_intended_room": intended_inside,
            "inside_building": building_inside, "building_room_ids": building_rooms,
            "distance_to_nearest_room_wall_m": wall_distance, "associated_wall_side": wall_side,
            "near_associated_wall": (wall_distance <= threshold) if threshold is not None else None,
            "distance_to_nearest_usable_legacy_door_m": round(door_distance, 3) if door_distance is not None else None,
            "wall_mask_collision": _pixel_wall_collision(point, wall_mask, scale_x, scale_y) if finite else None,
            "duplicate_or_collision": False,
        }
        records.append(record)
        if room:
            by_room[room["id"]].append(record)

    # Same-coordinate components are retained as production output but surfaced
    # as an obvious collision rather than silently treated as independent space.
    for room_id, items in by_room.items():
        for index, first in enumerate(items):
            for second in items[index + 1:]:
                a, b = first["position_m"], second["position_m"]
                if all(math.isfinite(value) for value in (*a.values(), *b.values())):
                    distance = math.dist((a["x"], a["y"]), (b["x"], b["y"]))
                    if distance <= .12:
                        first["duplicate_or_collision"] = second["duplicate_or_collision"] = True
                        collisions.append({"room_id": room_id, "first": first["id"], "second": second["id"], "distance_m": round(distance, 3)})
    return records, collisions


def _sample_segment(a: tuple[float, float], b: tuple[float, float], step: float = .15) -> list[tuple[float, float]]:
    length = math.dist(a, b)
    count = max(1, math.ceil(length / step))
    return [(a[0] + (b[0] - a[0]) * index / count, a[1] + (b[1] - a[1]) * index / count)
            for index in range(count + 1)]


def _on_controlled_transition(point: tuple[float, float], transitions: list[dict[str, Any]], tolerance: float = .025) -> bool:
    """Whether a sampled point lies on an explicitly declared V2 room bridge."""
    px, py = point
    for transition in transitions:
        ax, ay = transition["from_point"]
        bx, by = transition["to_point"]
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            if math.dist(point, (ax, ay)) <= tolerance:
                return True
            continue
        ratio = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        if math.dist(point, (ax + ratio * dx, ay + ratio * dy)) <= tolerance:
            return True
    return False


def _route_records(layout: dict[str, Any], wall_mask: np.ndarray, scale_x: float, scale_y: float) -> list[dict[str, Any]]:
    rooms = layout["rooms"]
    components = {tuple(component["pos"]): component for component in layout["placed_components"] if _finite(component.get("pos"))}
    records = []
    for index, route in enumerate(layout["wire_routes"]):
        points = [tuple(point) for point in route["waypoints"]]
        sampled = [point for a, b in zip(points, points[1:]) for point in _sample_segment(a, b)]
        crossed = sorted({room["id"] for point in sampled for room in rooms if _inside(point, room)})
        transitions = route.get("controlled_transitions", [])
        outside_room_union = any(not any(_inside(point, room) for room in rooms) for point in sampled)
        outside = any(not any(_inside(point, room) for room in rooms) and not _on_controlled_transition(point, transitions)
                      for point in sampled)
        wall_hits = sum(bool(_pixel_wall_collision(point, wall_mask, scale_x, scale_y)) for point in sampled)
        end_component = components.get(points[-1])
        raw = path_length(points)
        records.append({
            "route_id": f"route_{index + 1}", "source": route.get("from"), "destination": route.get("to"),
            "destination_component_id": end_component.get("id") if end_component else None,
            "route_points_m": [{"x": point[0], "y": point[1]} for point in points],
            "raw_length_m": raw, "reported_length_m": route.get("length_m"),
            "slack_factor": round(route.get("length_m", 0) / raw, 3) if raw else None,
            "spaces_crossed": crossed, "outside_building": outside,
            "outside_room_union": outside_room_union,
            "wall_mask_samples": wall_hits, "sample_count": len(sampled),
            "routing_version": route.get("routing_version", "v1"),
            "architecture_aware": bool(route.get("architecture_aware", False)),
            "fallback_used": bool(route.get("fallback_used", False)),
            "fallback_reason": route.get("fallback_reason"),
            "source_room": route.get("source_room"), "target_room": route.get("target_room"),
            "traversed_rooms": route.get("traversed_rooms", []),
            "controlled_transition_count": len(transitions),
            "controlled_transitions": transitions,
            "suspicious": (outside or bool(route.get("fallback_used", False)) or
                           (route.get("routing_version", "v1") == "v1" and len(crossed) > 2)),
        })
    return records


def route_summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable, additive V1/V2 comparison summary for the electrical benchmark."""
    raw = [route["raw_length_m"] for route in routes]
    reported = [route["reported_length_m"] for route in routes]
    return {
        "route_count": len(routes),
        "total_raw_route_length_m": round(sum(raw), 2),
        "total_reported_wire_length_m": round(sum(reported), 2),
        "mean_route_length_m": round(statistics.mean(raw), 2) if raw else 0.0,
        "median_route_length_m": round(statistics.median(raw), 2) if raw else 0.0,
        "max_route_length_m": round(max(raw), 2) if raw else 0.0,
        "outside_building_routes": sum(route["outside_building"] for route in routes),
        "outside_room_union_routes": sum(route["outside_room_union"] for route in routes),
        "suspicious_routes": sum(route["suspicious"] for route in routes),
        "fallback_routes": sum(route["fallback_used"] for route in routes),
        "architecture_aware_routes": sum(route["architecture_aware"] and not route["fallback_used"] for route in routes),
        "architecture_aware_success_percent": round(100 * sum(route["architecture_aware"] and not route["fallback_used"] for route in routes) / len(routes), 1) if routes else 0.0,
        "wall_mask_samples": sum(route["wall_mask_samples"] for route in routes),
        "controlled_transition_count": sum(route["controlled_transition_count"] for route in routes),
        "worst_routes": [
            {key: route[key] for key in ("route_id", "destination_component_id", "raw_length_m", "reported_length_m", "outside_building", "suspicious", "fallback_used")}
            for route in sorted(routes, key=lambda route: route["raw_length_m"], reverse=True)[:5]
        ],
    }


def _room_expectations(layout: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = defaultdict(set)
    for component in components:
        category = category_for(component["component_type"])
        if category:
            grouped[component["room_id"]].add(category)
    records = []
    for room in layout["rooms"]:
        expected = expectation_for(room.get("name", "unknown"))
        actual = grouped[room["id"]]
        records.append({"room_id": room["id"], "room_type": room.get("name"),
                        "expected_categories": sorted(expected), "actual_categories": sorted(actual),
                        "missing_categories": sorted(expected - actual),
                        "unexpected_categories": sorted(actual - expected)})
    return records


def _bom_audit(layout: dict[str, Any]) -> dict[str, Any]:
    component_counts = Counter(component["label"] for component in layout["placed_components"])
    bom = {item["item"]: item["qty"] for item in layout["bom"]}
    direct = []
    for label, count in sorted(component_counts.items()):
        direct.append({"item": label, "component_count": count, "bom_count": bom.get(label),
                       "difference": None if label not in bom else bom[label] - count})
    heuristic = [item for item in layout["bom"] if item["item"] not in component_counts]
    wire_bom = bom.get("Electrical Wire / Cable (m)")
    return {"direct_component_reconciliation": direct, "heuristic_consumables": heuristic,
            "wire": {"reported_wire_m": layout["total_wire_m"], "bom_wire_m": wire_bom,
                     "rounded_difference_m": None if wire_bom is None else wire_bom - round(layout["total_wire_m"])} }


def _quality(records: list[dict[str, Any]], routes: list[dict[str, Any]], collisions: list[dict[str, Any]]) -> dict[str, Any]:
    non_db = [item for item in records if item["component_type"] != "db"]
    mounted = [item for item in non_db if item["component_type"] in WALL_MOUNTED]
    switches = [item for item in non_db if item["component_type"] in {"switch_1way", "switch_2way"}]
    with_door = [item for item in switches if item["distance_to_nearest_usable_legacy_door_m"] is not None]
    near_door = [item for item in with_door if item["distance_to_nearest_usable_legacy_door_m"] <= .8]
    def percentage(items: list[Any], predicate) -> float | None:
        return round(100 * sum(bool(predicate(item)) for item in items) / len(items), 1) if items else None
    return {
        "component_count_excluding_db": len(non_db),
        "inside_intended_room_percent": percentage([item for item in non_db if item["inside_intended_room"] is not None], lambda item: item["inside_intended_room"]),
        "inside_building_percent": percentage(non_db, lambda item: item["inside_building"]),
        "wall_mounted_near_wall_percent": percentage(mounted, lambda item: item["near_associated_wall"]),
        "switches_with_usable_legacy_door": len(with_door), "switches_near_usable_door_percent": percentage(with_door, lambda item: item in near_door),
        "wall_mask_collisions": sum(item["wall_mask_collision"] is True for item in non_db),
        "outside_building_components": sum(not item["inside_building"] for item in non_db),
        "component_collisions": len(collisions), "outside_building_routes": sum(route["outside_building"] for route in routes),
        "suspicious_routes": sum(route["suspicious"] for route in routes),
    }


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    values = Counter(record["component_type"] for record in records)
    return dict(sorted(values.items()))


def run_electrical_plan(image_path: str | Path, *, opening_detector: str = "v3", routing_version: str = "v2") -> dict[str, Any]:
    """Run frozen architecture → frozen electrical engine and audit its output."""
    if validate_expectations():
        raise ValueError("Electrical expectation schema is invalid")
    result = analyze_floor_plan(str(image_path), opening_detector=opening_detector)
    if not result["success"]:
        return {"plan_id": Path(image_path).stem, "success": False, "error": result.get("error")}
    vision = dict(result["data"])
    # Matches application compatibility behaviour: only explicitly accepted
    # openings can alter legacy room doors/windows. Frozen benchmark outputs
    # currently contain pending V3 candidates, so electrical inputs stay stable.
    vision["rooms"] = apply_verified_openings_to_rooms(vision.get("rooms", []), vision.get("opening_candidates", []))
    layout = generate_layout(vision, "electrical", routing_version=routing_version)
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot load {image_path}")
    _gray, binary = preprocess(image)
    wall_mask = make_wall_mask(binary, image.shape[1], image.shape[0])
    scale_x = float(vision["_debug"]["scale_mppx"])
    scale_y = scale_x
    components, collisions = _component_records(layout, wall_mask, scale_x, scale_y)
    routes = _route_records(layout, wall_mask, scale_x, scale_y)
    duplicate_ids = sorted(identifier for identifier, count in Counter(item["id"] for item in components).items() if count > 1)
    rooms = [{"room_id": room["id"], "label": room.get("name"), "dimensions_m": {"width": room["width"], "height": room["height"]}, "area_m2": room.get("area_m2"), "legacy_door_count": len(room.get("doors", [])), "legacy_window_count": len(room.get("windows", []))} for room in layout["rooms"]]
    return {
        "plan_id": Path(image_path).stem, "success": True, "opening_detector": opening_detector,
        "routing_version": routing_version,
        "architectural_input": {"room_count": len(rooms), "opening_candidates_pending": sum(item.get("verification_status") == "pending" for item in vision.get("opening_candidates", [])), "accepted_opening_candidates": sum(item.get("verification_status") == "accepted" for item in vision.get("opening_candidates", [])), "legacy_room_doors_used_by_engine": sum(len(room.get("doors", [])) for room in layout["rooms"])},
        "rooms": rooms, "db_location_m": {"x": layout["db_pos"][0], "y": layout["db_pos"][1]},
        "components": components, "component_counts": _counts(components), "total_component_count": len(components),
        "routes": routes, "total_route_count": len(routes), "total_raw_route_length_m": round(sum(route["raw_length_m"] for route in routes), 2), "total_reported_wire_length_m": layout["total_wire_m"], "configured_slack_factor": BUFFER,
        "routing_summary": route_summary(routes),
        "placement_quality": {**_quality(components, routes, collisions), "duplicate_component_ids": duplicate_ids}, "component_collisions": collisions,
        "room_expectations": _room_expectations(layout, components), "boq_audit": _bom_audit(layout), "bom": layout["bom"],
        "failure_classification": _failure_classification(components, routes, collisions, layout),
        "_visualization": {"image_path": str(image_path), "scale_x_m_per_px": scale_x, "scale_y_m_per_px": scale_y, "room_geometry": {room["id"]: room.get("geometry_px") for room in layout["rooms"]}},
    }


def _failure_classification(components, routes, collisions, layout) -> dict[str, list[dict[str, Any]]]:
    return {
        "architectural_input": [{"issue": "legacy room doors are heuristic CV output; V3 candidates are pending and intentionally inert", "severity": "review"}],
        "electrical_rules": [{"issue": "room expectations missing categories", "room_id": item["room_id"], "missing": item["missing_categories"]} for item in _room_expectations(layout, components) if item["missing_categories"]],
        "placement": ([{"issue": "co-located components", **item} for item in collisions] + [{"issue": "outside building", "component_id": item["id"]} for item in components if item["inside_building"] is False]),
        "routing": [{"issue": "route crosses multiple spaces or leaves building", "route_id": item["route_id"], "spaces": item["spaces_crossed"], "outside": item["outside_building"]} for item in routes if item["suspicious"]],
        "boq": [{"issue": "direct component/BOM mismatch", **item} for item in _bom_audit(layout)["direct_component_reconciliation"] if item["difference"] not in (0, None)],
    }


def render_electrical_overlay(report: dict[str, Any], output_path: str | Path) -> str:
    """Independent benchmark overlay on the original architectural raster."""
    visual = report["_visualization"]
    canvas = cv2.imread(visual["image_path"])
    if canvas is None:
        raise ValueError("Cannot render overlay without source image")
    height, width = canvas.shape[:2]
    canvas = cv2.copyMakeBorder(canvas, 0, 0, 0, 250, cv2.BORDER_CONSTANT, value=(28, 28, 28))
    sx, sy = visual["scale_x_m_per_px"], visual["scale_y_m_per_px"]
    for geometry in visual["room_geometry"].values():
        if geometry and geometry.get("bbox"):
            box = geometry["bbox"]
            cv2.rectangle(canvas, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (165, 165, 165), 1, cv2.LINE_AA)
    def px(position):
        return _world_to_px((position["x"], position["y"]), sx, sy, height)
    for route in report["routes"]:
        points = [px(point) for point in route["route_points_m"]]
        cv2.polylines(canvas, [np.array(points, np.int32)], False, (120, 120, 120), 1, cv2.LINE_AA)
    for component in report["components"]:
        point = px(component["position_m"])
        color = COLORS.get(component.get("symbol"), COLORS["default"])
        marker = cv2.MARKER_CROSS if component["component_type"] in CEILING_COMPONENTS else cv2.MARKER_TILTED_CROSS
        if component["component_type"] == "db":
            cv2.rectangle(canvas, (point[0] - 6, point[1] - 8), (point[0] + 6, point[1] + 8), color, 2)
        else:
            cv2.drawMarker(canvas, point, color, marker, 10, 2, cv2.LINE_AA)
        if component["wall_mask_collision"] or component["inside_building"] is False:
            cv2.circle(canvas, point, 9, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (width, 0), (width + 250, height), (28, 28, 28), -1)
    cv2.putText(canvas, "ELECTRICAL BENCHMARK", (width + 12, 28), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
    legend = [
        ("light", "Light / ceiling"), ("fan", "Fan"), ("switch", "Switch"),
        ("outlet", "Socket / power"), ("ac", "AC"), ("exhaust", "Exhaust"),
        ("default", "Other supported point"), ("db", "Distribution board"),
    ]
    for index, (symbol, label) in enumerate(legend):
        y = 58 + index * 28
        color = COLORS[symbol]
        cv2.drawMarker(canvas, (width + 22, y), color, cv2.MARKER_CROSS, 10, 2, cv2.LINE_AA)
        cv2.putText(canvas, label, (width + 38, y + 4), cv2.FONT_HERSHEY_SIMPLEX, .43, (235, 235, 235), 1, cv2.LINE_AA)
    quality = report["placement_quality"]
    lines = [f"Routing: {report.get('routing_version', 'v1').upper()}", f"Components: {report['total_component_count']}", f"Routes: {report['total_route_count']}", f"Wire: {report['total_reported_wire_length_m']} m", f"Wall collisions: {quality['wall_mask_collisions']}", f"Co-locations: {quality['component_collisions']}"]
    for index, line in enumerate(lines):
        cv2.putText(canvas, line, (width + 12, 310 + index * 22), cv2.FONT_HERSHEY_SIMPLEX, .43, (220, 220, 220), 1, cv2.LINE_AA)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    return str(output_path)

