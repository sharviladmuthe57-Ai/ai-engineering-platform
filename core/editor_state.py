"""Structured, incremental editing operations for the 2D electrical canvas."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any

from .geometry import BUFFER, build_bom, path_length
from .routing import route_component
from .rules_engine import COMPONENTS


PROJECT_STATE_VERSION = "1.0"


class EditorStateError(ValueError):
    """A safe, user-facing validation error for an editor operation."""


def create_project_state(job_id: str, layout: dict[str, Any], scale_m_per_px: float | None, project_name: str | None = None) -> dict[str, Any]:
    """Create the compact, editable state while leaving generated layout intact."""
    state = {
        "project_state_version": PROJECT_STATE_VERSION,
        "job_id": job_id,
        "project_name": project_name or f"Project {job_id}",
        "coordinate_system": {"unit": layout.get("unit", "metres"), "origin": "bottom_left", "y_axis": "up"},
        "scale_m_per_px": scale_m_per_px,
        "architectural_plan": {"reference": "job_upload", "job_id": job_id},
        "rooms": deepcopy(layout.get("rooms", [])),
        "db_pos": deepcopy(layout.get("db_pos")),
        "components": deepcopy(layout.get("placed_components", [])),
        "routes": deepcopy(layout.get("wire_routes", [])),
        "bom": deepcopy(layout.get("bom", [])),
        "total_wire_m": layout.get("total_wire_m", 0.0),
        "cctv_components": deepcopy(layout.get("cctv_components", [])),
        "total_cat6_m": layout.get("total_cat6_m", 0.0),
        "edited": False,
        "revision_number": 0,
        "next_component_sequence": 1,
        "last_modified": _now(),
    }
    for component in state["components"]:
        component.setdefault("position_source", "generated")
        component.setdefault("editor_status", "generated")
    for route in state["routes"]:
        route.setdefault("route_source", "generated")
    return state


def move_component(state: dict[str, Any], component_id: str, position: Any) -> dict[str, Any]:
    """Apply a manual in-room move and recompute just that component's route."""
    component = _component(state, component_id)
    if component.get("comp_id") == "db":
        raise EditorStateError("Distribution Board movement is not supported in Editor V1")
    point = _validated_position(state, component["room_id"], position)
    component["pos"] = point
    component["position_source"] = "user_modified"
    component["editor_status"] = "user_modified"
    component["last_editor_action"] = "move"
    _replace_route(state, component)
    _refresh_bom(state)
    _touch(state)
    return state


def add_component(state: dict[str, Any], component_type: str, room_id: str, position: Any) -> dict[str, Any]:
    """Add one supported manual component with a monotonic project-local ID."""
    if component_type not in COMPONENTS or component_type == "db":
        raise EditorStateError(f"Unsupported manual component type: {component_type}")
    room = _room(state, room_id)
    point = _validated_position(state, room_id, position)
    sequence = int(state.get("next_component_sequence", 1))
    existing_ids = {item["id"] for item in state["components"]}
    while f"user_{component_type}_{sequence:04d}" in existing_ids:
        sequence += 1
    component_id = f"user_{component_type}_{sequence:04d}"
    state["next_component_sequence"] = sequence + 1
    spec = COMPONENTS[component_type]
    component = {
        "id": component_id, "room_id": room_id, "room_name": room.get("name", "unknown"),
        "comp_id": component_type, "label": spec["label"], "symbol": spec["symbol"],
        "pos": point, "qty": 1, "rule_hint": "user_added",
        "placement_version": "manual", "placement_method": "user_added",
        "placement_adjusted": False, "adjustment_reason": None,
        "original_position": point, "validated_position": point,
        "wall_side": None, "door_source": None, "collision_resolved": False,
        "position_source": "user_added", "editor_status": "user_added",
    }
    state["components"].append(component)
    _replace_route(state, component)
    _refresh_bom(state)
    _touch(state)
    return state


def delete_component(state: dict[str, Any], component_id: str) -> dict[str, Any]:
    """Delete a manual or generated electrical component and its route."""
    component = _component(state, component_id)
    if component.get("comp_id") == "db":
        raise EditorStateError("Distribution Board deletion is not supported in Editor V1")
    state["components"] = [item for item in state["components"] if item["id"] != component_id]
    state["routes"] = [route for route in state["routes"] if route.get("to") != component_id]
    _refresh_bom(state)
    _touch(state)
    return state


def reset_project_state(job_id: str, layout: dict[str, Any], scale_m_per_px: float | None, revision_number: int = 0, project_name: str | None = None) -> dict[str, Any]:
    """Restore the immutable generated layout as a new editable-state revision."""
    state = create_project_state(job_id, layout, scale_m_per_px, project_name)
    state["revision_number"] = revision_number + 1
    state["last_editor_action"] = "reset_to_generated"
    return state


def _replace_route(state: dict[str, Any], component: dict[str, Any]) -> None:
    routing = route_component(tuple(state["db_pos"]), tuple(component["pos"]), component["room_id"], state["rooms"], routing_version="v2.1")
    route = {
        "from": "db", "to": component["id"], "waypoints": routing["waypoints"],
        "length_m": round(path_length(routing["waypoints"]) * BUFFER, 2),
        "symbol": component.get("symbol", "outlet"), "route_source": "generated_after_edit",
        **{key: value for key, value in routing.items() if key != "waypoints"},
    }
    for index, existing in enumerate(state["routes"]):
        if existing.get("to") == component["id"]:
            state["routes"][index] = route
            break
    else:
        state["routes"].append(route)


def _refresh_bom(state: dict[str, Any]) -> None:
    total_wire = round(sum(float(route.get("length_m", 0.0)) for route in state["routes"]), 2)
    state["total_wire_m"] = total_wire
    state["bom"] = build_bom(state["components"], total_wire, state.get("cctv_components", []), state.get("total_cat6_m", 0.0))


def _component(state: dict[str, Any], component_id: str) -> dict[str, Any]:
    for component in state.get("components", []):
        if component.get("id") == component_id:
            return component
    raise EditorStateError(f"Component {component_id} was not found")


def _room(state: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in state.get("rooms", []):
        if room.get("id") == room_id:
            return room
    raise EditorStateError(f"Room {room_id} was not found")


def _validated_position(state: dict[str, Any], room_id: str, position: Any) -> list[float]:
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        raise EditorStateError("Position must contain finite x and y coordinates")
    try:
        x, y = float(position[0]), float(position[1])
    except (TypeError, ValueError) as error:
        raise EditorStateError("Position must contain finite x and y coordinates") from error
    if not (math.isfinite(x) and math.isfinite(y)):
        raise EditorStateError("Position must contain finite x and y coordinates")
    room = _room(state, room_id)
    if not (room["x"] <= x <= room["x"] + room["width"] and room["y"] <= y <= room["y"] + room["height"]):
        raise EditorStateError("Editor V1 keeps a component inside its assigned room; cross-room moves are not supported")
    return [round(x, 3), round(y, 3)]


def _touch(state: dict[str, Any]) -> None:
    state["edited"] = True
    state["revision_number"] = int(state.get("revision_number", 0)) + 1
    state["last_modified"] = _now()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
