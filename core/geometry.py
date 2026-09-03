"""
geometry.py  —  Component Placement + Wall-Following Wire Router v2
====================================================================
Uses rules_engine.py for per-room component placement.
Wire routing follows walls using L-shaped Manhattan paths.
BOM derived entirely from placed components (no estimates).
"""

import math
from .rules_engine import get_rules, compute_position, COMPONENTS
from .placement import PlacementValidator, preferred_door_source
from .routing import legacy_manhattan_route, path_length as routing_path_length, route_component

BUFFER = 1.15   # 15% wire slack

# ── ROOM COLOURS (for renderer) ──────────────────────────────────────────────
ROOM_FILL = {
    "bedroom"      : "#1A2535",
    "living"       : "#1A2B1A",
    "dining"       : "#2A1A2A",
    "kitchen"      : "#2A2A1A",
    "bathroom"     : "#1A2A2A",
    "verandah"     : "#2A1F1A",
    "corridor"     : "#1F1F2A",
    "staircase"    : "#2A1A1A",
    "store"        : "#222222",
    "lobby"        : "#1A2020",
    "office"       : "#1A1A2A",
    "study"        : "#1A1A2A",
    "puja_room"    : "#2A1A2A",
    "servant_room" : "#222222",
    "balcony"      : "#1A2A1A",
    "garage"       : "#222222",
    "unknown"      : "#1C1C1C",
}


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def generate_layout(vision_data: dict, project_type: str = "electrical", routing_version: str = "v2.1", placement_version: str = "v2") -> dict:
    rooms    = vision_data.get("rooms",    [])
    elements = vision_data.get("detected_elements", [])

    placed   = []    # electrical components
    routes   = []    # wire routes

    # Find or estimate DB (distribution board) position
    db_pos = _find_db_position(rooms)

    # ── ELECTRICAL LAYOUT ────────────────────────────────────────────────────
    if project_type in ("electrical", "both"):
        for room in rooms:
            room_type = room.get("name", "unknown")
            rules     = get_rules(room_type)
            validator = PlacementValidator(room) if placement_version == "v2" else None
            component_occurrences = {}

            for (comp_id, qty, pos_hint) in rules:
                spec = COMPONENTS.get(comp_id, {})
                pos  = compute_position(pos_hint, room)

                # Multiple outlets → spread them
                positions = _spread_positions(pos, qty, room, pos_hint)

                for i, p in enumerate(positions):
                    occurrence = component_occurrences.get(comp_id, 0) if validator else i
                    component_occurrences[comp_id] = occurrence + 1
                    if validator:
                        validated_pos, placement = validator.validate(p, pos_hint)
                    else:
                        validated_pos = p
                        placement = {
                            "placement_version": "v1", "placement_method": "unvalidated_rule_position",
                            "placement_adjusted": False, "adjustment_reason": None,
                            "original_position": p, "validated_position": p,
                            "wall_side": None, "collision_resolved": False,
                        }
                    component_id = f"{room['id']}_{comp_id}_{occurrence}"
                    component = {
                        "id"       : component_id,
                        "room_id"  : room["id"],
                        "room_name": room_type,
                        "comp_id"  : comp_id,
                        "label"    : spec.get("label", comp_id),
                        "symbol"   : spec.get("symbol", "outlet"),
                        "pos"      : validated_pos,
                        "qty"      : 1,
                        "rule_hint": pos_hint,
                        "door_source": preferred_door_source(room, pos_hint),
                        **placement,
                    }
                    placed.append(component)

                    # V2 stays inside the detected room domain when a connected
                    # architectural path exists. V1 remains available for audit.
                    if routing_version == "v1":
                        routing = {
                            "waypoints": wall_route(db_pos, validated_pos), "routing_version": "v1",
                            "architecture_aware": False, "fallback_used": False,
                            "fallback_reason": None, "source_room": None,
                            "target_room": room["id"], "traversed_rooms": [],
                            "controlled_transitions": [],
                        }
                    else:
                        routing = route_component(db_pos, validated_pos, room["id"], rooms, routing_version=routing_version)
                    route = routing["waypoints"]
                    routes.append({
                        "from"      : "db",
                        "to"        : component_id,
                        "waypoints" : route,
                        "length_m"  : round(path_length(route) * BUFFER, 2),
                        "symbol"    : spec.get("symbol","outlet"),
                        **{key: value for key, value in routing.items() if key != "waypoints"},
                    })

    # Add DB itself to placed components
    placed.insert(0, {
        "id"       : "db_main",
        "room_id"  : "entry",
        "room_name": "distribution",
        "comp_id"  : "db",
        "label"    : "Distribution Board",
        "symbol"   : "db",
        "pos"      : db_pos,
        "qty"      : 1,
    })

    # ── CCTV LAYOUT ──────────────────────────────────────────────────────────
    cctv_components = []
    cctv_routes     = []
    total_cat6      = 0.0
    nvr_pos         = None

    if project_type in ("cctv", "both"):
        cameras  = [e for e in elements if e["type"] == "camera"]
        nvr_list = [e for e in elements if e["type"] == "nvr"]

        if nvr_list:
            n = nvr_list[0]
            nvr_pos = (n["x"], n["y"])
        elif rooms:
            r = rooms[0]
            nvr_pos = (r["x"] + r["width"] - 1.5, r["y"] + 1.5)

        bld_bounds = _building_bounds(rooms)

        for i, cam in enumerate(cameras):
            cam_pos = (cam["x"], cam["y"])
            if nvr_pos:
                wpts   = _cable_to_nvr(cam_pos, nvr_pos, bld_bounds)
                length = path_length(wpts) * BUFFER
                total_cat6 += length
            else:
                wpts   = [cam_pos]
                length = 0.0

            cctv_components.append({
                "id"   : f"CAM-{i+1:02d}",
                "pos"  : cam_pos,
                "label": f"Camera {i+1}",
                "notes": cam.get("notes",""),
            })
            cctv_routes.append({
                "cam_id"   : f"CAM-{i+1:02d}",
                "waypoints": wpts,
                "length_m" : round(length, 2),
            })

    # ── BOM ──────────────────────────────────────────────────────────────────
    total_wire = sum(r["length_m"] for r in routes)
    bom = build_bom(placed, total_wire, cctv_components, total_cat6)

    return {
        "unit"              : vision_data.get("unit","metres"),
        "project_type"      : project_type,
        "routing_version"   : routing_version,
        "placement_version" : placement_version,
        "rooms"             : rooms,
        "db_pos"            : db_pos,
        "placed_components" : placed,
        "wire_routes"       : routes,
        "total_wire_m"      : round(total_wire, 2),
        "cctv_components"   : cctv_components,
        "cctv_routes"       : cctv_routes,
        "total_cat6_m"      : round(total_cat6, 2),
        "nvr_pos"           : nvr_pos,
        "bom"               : bom,
        "warnings"          : vision_data.get("warnings", []),
    }


# ═════════════════════════════════════════════════════════════════════════════
#  WIRE ROUTING  (wall-following L-path)
# ═════════════════════════════════════════════════════════════════════════════
def wall_route(start: tuple, end: tuple) -> list:
    """
    Manhattan / L-shaped route between two points.
    Chooses the shorter of two L-options.
    Real wall-graph routing (Dijkstra) will come in V1.2.
    """
    return legacy_manhattan_route(start, end)


def path_length(wpts: list) -> float:
    return routing_path_length(wpts)


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def _find_db_position(rooms):
    """DB goes near the entrance room (smallest area near building edge) or default."""
    if not rooms:
        return (1.0, 1.0)
    # Find room closest to origin (entrance / lobby)
    def dist_to_origin(r):
        return math.hypot(r["x"], r["y"])
    entry = min(rooms, key=dist_to_origin)
    # Place DB on left wall of that room
    return (round(entry["x"] + 0.3, 2),
            round(entry["y"] + entry["height"] - 0.5, 2))


def _spread_positions(base_pos, qty, room, hint):
    """If qty > 1, spread positions along the wall."""
    if qty == 1:
        return [base_pos]

    rx, ry = room["x"], room["y"]
    rw, rh = room["width"], room["height"]
    bx, by = base_pos
    positions = []

    for i in range(qty):
        offset = (i - (qty-1)/2) * min(rw, rh) * 0.25
        if "wall_n" in hint or "wall_s" in hint or "counter" in hint:
            positions.append((bx + offset, by))
        elif "wall_e" in hint or "wall_w" in hint:
            positions.append((bx, by + offset))
        else:
            positions.append((bx + offset * 0.5, by + offset * 0.5))

    return positions


def _building_bounds(rooms):
    if not rooms:
        return (0,0,20,20)
    min_x = min(r["x"] for r in rooms)
    min_y = min(r["y"] for r in rooms)
    max_x = max(r["x"]+r["width"]  for r in rooms)
    max_y = max(r["y"]+r["height"] for r in rooms)
    return (min_x, min_y, max_x, max_y)


def _cable_to_nvr(cam_pos, nvr_pos, bounds):
    cx,cy  = cam_pos
    nx,ny  = nvr_pos
    _,_,bx2,_ = bounds
    wall_x = bx2 - 0.2
    return [(cx,cy), (wall_x,cy), (wall_x,ny), (nx,ny)]


# ═════════════════════════════════════════════════════════════════════════════
#  BOM  (derived from actual placed components)
# ═════════════════════════════════════════════════════════════════════════════
def build_bom(placed, total_wire, cctv_comps, total_cat6):
    counts = {}

    for comp in placed:
        label = comp["label"]
        counts[label] = counts.get(label, 0) + 1

    # Wire
    if total_wire > 0:
        wm = round(total_wire)
        counts["Electrical Wire / Cable (m)"]   = wm
        counts["Conduit (m)"]                   = round(wm * 0.90)
        counts["Cable Clips"]                   = max(1, round(wm / 1.5))
        counts["Junction / Gang Box"]           = max(1, round(len(placed) * 0.6))
        counts["Earthing Wire (m)"]             = round(wm * 0.15)
        counts["Screws / Wall Plugs (packs)"]   = 2

    # CCTV
    if cctv_comps:
        n = len(cctv_comps)
        counts["CCTV Camera (2MP Bullet IP66)"] = n
        counts["NVR (8-channel)"]               = 1
        counts["NVR Rack / Cabinet"]            = 1
        counts["CAT6 Cable (m)"]                = round(total_cat6)
        counts["RJ45 Connectors (pairs)"]       = n * 2
        counts["PoE Switch (8-port)"]           = 1
        counts["HDD 1TB Storage"]               = 1
        counts["CCTV Conduit (m)"]              = round(total_cat6 * 0.9)
        counts["Cable Clips (CCTV)"]            = round(total_cat6 / 1.5)

    def unit_of(item):
        return "metres" if "(m)" in item else "pcs"

    return [{"item": k, "qty": v, "unit": unit_of(k)}
            for k, v in counts.items()]
