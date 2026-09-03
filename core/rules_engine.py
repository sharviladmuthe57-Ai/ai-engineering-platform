"""
rules_engine.py — Per-room electrical component placement rules
================================================================
Each room type has:
  - Required components (always placed)
  - Optional components (based on room size / user selection)
  - Placement positions (centroid, near_door, wall_n/s/e/w, corner)

Component positions explained:
  centroid      → ceiling centre (lights, fans)
  centroid_off  → offset from centre (fan when light also on ceiling)
  near_door     → 0.3m from door frame, inside the intended room (switches)
  wall_n/s/e/w  → along that wall, at mid-height
  high_wall     → 2.1m height (AC, exhaust fan)
  corner_ne/nw  → near corner on that wall
  counter       → kitchen counter height (0.9m)
"""

# ── COMPONENT CATALOGUE ────────────────────────────────────────────────────
# Each entry: id → {label, symbol, voltage, note}
COMPONENTS = {
    "ceiling_light"   : {"label": "Ceiling Light",        "symbol": "light",     "v": "240"},
    "ceiling_fan"     : {"label": "Ceiling Fan",           "symbol": "fan",       "v": "240"},
    "exhaust_fan"     : {"label": "Exhaust Fan",           "symbol": "exhaust",   "v": "240"},
    "switch_1way"     : {"label": "1-Way Switch",          "symbol": "switch",    "v": "240"},
    "switch_2way"     : {"label": "2-Way Switch",          "symbol": "switch2",   "v": "240"},
    "outlet_5pin"     : {"label": "5-Pin Socket (15A)",    "symbol": "outlet",    "v": "240"},
    "outlet_2pin"     : {"label": "2-Pin Socket (5A)",     "symbol": "outlet2",   "v": "240"},
    "ac_point"        : {"label": "AC Power Point",        "symbol": "ac",        "v": "240"},
    "geyser_point"    : {"label": "Geyser / Water Heater", "symbol": "geyser",    "v": "240"},
    "tv_point"        : {"label": "TV Point",              "symbol": "tv",        "v": "240"},
    "wifi_point"      : {"label": "Wi-Fi / Router Point",  "symbol": "wifi",      "v": "240"},
    "fridge_point"    : {"label": "Refrigerator Point",    "symbol": "outlet",    "v": "240"},
    "chimney_point"   : {"label": "Chimney Point",         "symbol": "outlet",    "v": "240"},
    "ro_point"        : {"label": "RO / Purifier Point",   "symbol": "outlet2",   "v": "240"},
    "microwave_point" : {"label": "Microwave Point",       "symbol": "outlet",    "v": "240"},
    "washing_point"   : {"label": "Washing Machine Point", "symbol": "outlet",    "v": "240"},
    "doorbell_point"  : {"label": "Door Bell",             "symbol": "bell",      "v": "12"},
    "smoke_detector"  : {"label": "Smoke Detector",        "symbol": "smoke",     "v": "12"},
    "mcb"             : {"label": "MCB Breaker",           "symbol": "mcb",       "v": "240"},
    "db"              : {"label": "Distribution Board",    "symbol": "db",        "v": "240"},
    "emergency_light" : {"label": "Emergency Light",       "symbol": "emlight",   "v": "240"},
}

# ── PER-ROOM RULES ─────────────────────────────────────────────────────────
# Format: list of (component_id, qty, position_hint)
ROOM_RULES = {
    "bedroom": [
        ("ceiling_light", 1, "centroid"),
        ("ceiling_fan",   1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),       # bedside
        ("outlet_5pin",   1, "wall_w"),       # other side
        ("ac_point",      1, "high_wall_n"),
        ("outlet_2pin",   1, "wall_s"),       # phone charger
    ],
    "living": [
        ("ceiling_light", 2, "centroid"),
        ("ceiling_fan",   1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("switch_2way",   1, "near_door_2"),
        ("tv_point",      1, "wall_e"),
        ("wifi_point",    1, "wall_n"),
        ("ac_point",      1, "high_wall_n"),
        ("outlet_5pin",   2, "wall_s"),
        ("outlet_2pin",   1, "wall_w"),
    ],
    "dining": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),
    ],
    "kitchen": [
        ("ceiling_light", 1, "centroid"),
        ("exhaust_fan",   1, "high_wall_n"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   2, "counter_s"),    # counter sockets
        ("fridge_point",  1, "wall_e"),
        ("chimney_point", 1, "high_wall_n"),
        ("microwave_point",1,"counter_s"),
        ("ro_point",      1, "counter_w"),
    ],
    "bathroom": [
        ("ceiling_light", 1, "centroid"),     # waterproof
        ("exhaust_fan",   1, "high_wall_n"),
        ("switch_1way",   1, "outside_door"), # corrected by Placement V2 validation
        ("geyser_point",  1, "high_wall_e"),
        ("outlet_2pin",   1, "wall_s"),       # shaver socket
    ],
    "verandah": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),
        ("doorbell_point",1, "near_door"),
    ],
    "corridor": [
        ("ceiling_light", 1, "centroid"),
        ("switch_2way",   2, "near_door"),    # 2-way for both ends
    ],
    "staircase": [
        ("ceiling_light", 1, "centroid"),
        ("switch_2way",   2, "near_door"),
        ("emergency_light",1,"wall_n"),
    ],
    "store": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),
    ],
    "lobby": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("doorbell_point",1, "near_door"),
        ("outlet_5pin",   1, "wall_s"),
    ],
    "office": [
        ("ceiling_light", 1, "centroid"),
        ("ceiling_fan",   1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   3, "wall_s"),
        ("wifi_point",    1, "wall_n"),
        ("ac_point",      1, "high_wall_e"),
    ],
    "study": [
        ("ceiling_light", 1, "centroid"),
        ("ceiling_fan",   1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   2, "wall_s"),
        ("wifi_point",    1, "wall_n"),
    ],
    "puja_room": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_2pin",   1, "wall_s"),
    ],
    "servant_room": [
        ("ceiling_light", 1, "centroid"),
        ("ceiling_fan",   1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),
    ],
    "balcony": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_e"),
        ("washing_point", 1, "wall_w"),
    ],
    "garage": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   2, "wall_s"),
    ],
    "unknown": [
        ("ceiling_light", 1, "centroid"),
        ("switch_1way",   1, "near_door"),
        ("outlet_5pin",   1, "wall_s"),
    ],
}


def get_rules(room_type: str) -> list:
    """Return component rules for a given room type."""
    return ROOM_RULES.get(room_type, ROOM_RULES["unknown"])


def compute_position(hint: str, room: dict) -> tuple:
    """
    Convert a position hint to (x, y) world coordinates.
    Room: {x, y, width, height, doors}
    """
    rx, ry   = room["x"],     room["y"]
    rw, rh   = room["width"], room["height"]
    cx, cy   = rx + rw/2,     ry + rh/2

    WALL_INSET = 0.25    # metres from wall
    HIGH       = 2.0     # high fixtures (AC, exhaust) relative to room bottom
    SWITCH_H   = 0.25    # switch is near door, 0.25m inside room

    POS = {
        "centroid"       : (cx, cy),
        "centroid_off"   : (cx + rw*0.15, cy),
        "wall_n"         : (cx, ry + rh - WALL_INSET),
        "wall_s"         : (cx, ry + WALL_INSET),
        "wall_e"         : (rx + rw - WALL_INSET, cy),
        "wall_w"         : (rx + WALL_INSET, cy),
        "high_wall_n"    : (cx, ry + rh - WALL_INSET),
        "high_wall_e"    : (rx + rw - WALL_INSET, cy + rh*0.3),
        "high_wall_w"    : (rx + WALL_INSET, cy + rh*0.3),
        "counter_s"      : (cx - rw*0.15, ry + WALL_INSET + 0.1),
        "counter_w"      : (rx + WALL_INSET, cy - rh*0.1),
        "corner_ne"      : (rx + rw - WALL_INSET, ry + rh - WALL_INSET),
        "corner_nw"      : (rx + WALL_INSET, ry + rh - WALL_INSET),
        "corner_se"      : (rx + rw - WALL_INSET, ry + WALL_INSET),
        "corner_sw"      : (rx + WALL_INSET, ry + WALL_INSET),
    }

    if hint in POS:
        return POS[hint]

    if hint == "near_door":
        return _near_door(room, 0)
    if hint == "near_door_2":
        return _near_door(room, 1)

    if hint == "outside_door":
        return _outside_door(room)

    return (cx, cy)   # fallback


def _near_door(room, door_idx=0):
    """Position just inside the door."""
    doors = _ordered_doors(room)
    rx,ry = room["x"],     room["y"]
    rw,rh = room["width"], room["height"]
    INSET = 0.30

    if doors and door_idx < len(doors):
        d  = doors[door_idx]
        wl = d.get("wall","bottom")
        p  = d.get("position", rw/2)
        if wl=="bottom": return (rx+p,        ry+INSET)
        if wl=="top":    return (rx+p,         ry+rh-INSET)
        if wl=="left":   return (rx+INSET,     ry+p)
        if wl=="right":  return (rx+rw-INSET,  ry+p)

    # No door info — deterministic wall-adjacent interior fallback.
    return (rx+INSET, ry+INSET)


def _ordered_doors(room):
    """Return accepted openings before legacy doors without trusting pending data.

    Pending and rejected candidates never reach ``rooms[].doors`` through the
    compatibility adapter.  The remaining ``verified_opening_candidate`` doors
    are therefore safe to prefer over the legacy CV door list.
    """
    doors = list(room.get("doors", []))
    ranked = sorted(enumerate(doors), key=lambda item: (
        0 if item[1].get("source") == "verified_opening_candidate" else 1,
        item[0],
    ))
    return [door for _index, door in ranked]


def _outside_door(room):
    """Legacy bathroom-switch proposal retained for Placement V1 comparison.

    Placement V2 validates this candidate back inside the intended room before
    generation. Keeping the proposal here makes before/after benchmark output
    comparable without changing the room rule catalogue.
    """
    doors = _ordered_doors(room)
    rx, ry = room["x"], room["y"]
    rw, rh = room["width"], room["height"]
    outset = 0.25
    if doors:
        door = doors[0]
        wall = door.get("wall", "bottom")
        position = door.get("position", rw / 2)
        if wall == "bottom": return (rx + position, ry - outset)
        if wall == "top": return (rx + position, ry + rh + outset)
        if wall == "left": return (rx - outset, ry + position)
        if wall == "right": return (rx + rw + outset, ry + position)
    return (rx - outset, ry + rh / 2)
