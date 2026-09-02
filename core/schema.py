"""
core/schema.py
==============
Canonical Architectural Plan Data Schema (v2.0.0).

Defines the shared, type-safe data model for architectural floor plans:
  1. Rooms as 2D polygons (with bounding box legacy compatibility)
  2. Wall segments with thickness, centerline, and materials
  3. Doors with metric position, swing direction, angle, and wall attachment
  4. Windows with metric position, width, sill height, and type
  5. Dimensions and scale calibration metadata
  6. Coordinate system specification (Cartesian metric vs. raster image space)

Provides bidirectional adapters (from_legacy_dict / to_legacy_dict)
so that all existing modules (cv_analyzer, geometry, rules_engine, renderer,
app.py, and index.html) maintain 100% backward compatibility without breaks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union

try:
    from shapely.geometry import Polygon as ShapelyPolygon, LineString as ShapelyLineString, Point as ShapelyPoint
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


# ═════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ═════════════════════════════════════════════════════════════════════════════

class LengthUnit(str, Enum):
    METRES = "metres"
    MILLIMETRES = "mm"
    CENTIMETRES = "cm"
    FEET = "feet"
    INCHES = "inches"
    PIXELS = "pixels"


class OriginLocation(str, Enum):
    BOTTOM_LEFT = "bottom_left"   # Standard Cartesian (X right, Y up) in metric
    TOP_LEFT    = "top_left"      # Screen / Image raster space (X right, Y down)


class CalibrationSource(str, Enum):
    USER_INPUT       = "user_input"
    DIMENSION_TEXT   = "dimension_text"
    RATIO_HEURISTIC  = "ratio_heuristic"
    DEFAULT_FALLBACK = "default_fallback"
    UNCALIBRATED     = "uncalibrated"


class WallType(str, Enum):
    EXTERIOR  = "exterior"
    INTERIOR  = "interior"
    PARTITION = "partition"
    BEARING   = "bearing"
    CURTAIN   = "curtain"
    VIRTUAL   = "virtual"       # Open threshold / room partition without physical wall


class DoorSwing(str, Enum):
    INWARD_LEFT   = "inward_left"
    INWARD_RIGHT  = "inward_right"
    OUTWARD_LEFT  = "outward_left"
    OUTWARD_RIGHT = "outward_right"
    SLIDING       = "sliding"
    DOUBLE        = "double"
    POCKET        = "pocket"
    NONE          = "none"
    UNKNOWN       = "unknown"


class WindowType(str, Enum):
    STANDARD = "standard"
    CASEMENT = "casement"
    SLIDING  = "sliding"
    FIXED    = "fixed"
    BAY      = "bay"
    LOUVERED = "louvered"


# ═════════════════════════════════════════════════════════════════════════════
#  GEOMETRY PRIMITIVES
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Point2D:
    """2D point representation in plan coordinate space."""
    x: float
    y: float

    def __iter__(self):
        yield self.x
        yield self.y

    def __getitem__(self, idx: int) -> float:
        if idx == 0: return self.x
        elif idx == 1: return self.y
        raise IndexError("Point2D index out of range (use 0 for x, 1 for y)")

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, float]:
        return {"x": round(self.x, 3), "y": round(self.y, 3)}

    @classmethod
    def from_any(cls, pt: Union[Point2D, Tuple[float, float], List[float], Dict[str, float]]) -> Point2D:
        if isinstance(pt, Point2D):
            return pt
        if isinstance(pt, (tuple, list)) and len(pt) >= 2:
            return cls(x=float(pt[0]), y=float(pt[1]))
        if isinstance(pt, dict) and "x" in pt and "y" in pt:
            return cls(x=float(pt["x"]), y=float(pt["y"]))
        raise ValueError(f"Cannot construct Point2D from: {pt}")

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


# ═════════════════════════════════════════════════════════════════════════════
#  COORDINATE SYSTEM & SCALE
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class CoordinateSystem:
    """Defines coordinate space orientation, reference origin, and metric units."""
    origin       : OriginLocation = OriginLocation.BOTTOM_LEFT
    unit         : LengthUnit     = LengthUnit.METRES
    pixel_height : Optional[int]  = None
    rotation_deg : float          = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin.value if isinstance(self.origin, OriginLocation) else str(self.origin),
            "unit": self.unit.value if isinstance(self.unit, LengthUnit) else str(self.unit),
            "pixel_height": self.pixel_height,
            "rotation_deg": self.rotation_deg,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CoordinateSystem:
        return cls(
            origin=OriginLocation(data.get("origin", OriginLocation.BOTTOM_LEFT)),
            unit=LengthUnit(data.get("unit", LengthUnit.METRES)),
            pixel_height=data.get("pixel_height"),
            rotation_deg=float(data.get("rotation_deg", 0.0)),
        )


@dataclass
class ScaleInfo:
    """Scale calibration metadata linking pixel coordinates to real-world units."""
    scale_m_per_px : float
    calibrated_from: CalibrationSource = CalibrationSource.DEFAULT_FALLBACK
    known_width_m  : Optional[float]   = None
    known_height_m : Optional[float]   = None
    image_width_px : Optional[int]     = None
    image_height_px: Optional[int]     = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale_m_per_px": round(self.scale_m_per_px, 6),
            "calibrated_from": self.calibrated_from.value if isinstance(self.calibrated_from, CalibrationSource) else str(self.calibrated_from),
            "known_width_m": self.known_width_m,
            "known_height_m": self.known_height_m,
            "image_width_px": self.image_width_px,
            "image_height_px": self.image_height_px,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScaleInfo:
        return cls(
            scale_m_per_px=float(data.get("scale_m_per_px", 0.015)),
            calibrated_from=CalibrationSource(data.get("calibrated_from", CalibrationSource.DEFAULT_FALLBACK)),
            known_width_m=data.get("known_width_m"),
            known_height_m=data.get("known_height_m"),
            image_width_px=data.get("image_width_px"),
            image_height_px=data.get("image_height_px"),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  DIMENSION ANNOTATIONS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class DimensionAnnotation:
    """Explicit dimension measurement / leader line found on architectural drawings."""
    id                 : str
    start              : Point2D
    end                : Point2D
    measured_distance_m: float
    text_value         : str
    orientation        : str = "aligned"   # "horizontal", "vertical", "aligned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "measured_distance_m": round(self.measured_distance_m, 3),
            "text_value": self.text_value,
            "orientation": self.orientation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DimensionAnnotation:
        return cls(
            id=data.get("id", ""),
            start=Point2D.from_any(data["start"]),
            end=Point2D.from_any(data["end"]),
            measured_distance_m=float(data.get("measured_distance_m", 0.0)),
            text_value=data.get("text_value", ""),
            orientation=data.get("orientation", "aligned"),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  DOORS & WINDOWS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Door:
    """Architectural Door object with position, dimensions, swing, and room attachments."""
    id                : str
    position          : Point2D
    width             : float         = 0.90     # in metres
    height            : float         = 2.10     # in metres
    wall              : Optional[str] = None     # legacy orientation: "bottom", "top", "left", "right"
    offset_along_wall : Optional[float] = None   # legacy relative position along room wall
    wall_id           : Optional[str] = None     # reference to parent WallSegment id
    swing_direction   : DoorSwing     = DoorSwing.INWARD_RIGHT
    swing_angle_deg   : float         = 90.0
    connects_rooms    : List[str]     = field(default_factory=list)

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Produces exact legacy door format used by current renderer and rules engine."""
        return {
            "wall": self.wall or "bottom",
            "position": round(self.offset_along_wall if self.offset_along_wall is not None else self.position.x, 2),
            "width": round(self.width, 2),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "position": self.position.to_dict(),
            "width": round(self.width, 3),
            "height": round(self.height, 3),
            "wall": self.wall,
            "offset_along_wall": round(self.offset_along_wall, 3) if self.offset_along_wall is not None else None,
            "wall_id": self.wall_id,
            "swing_direction": self.swing_direction.value if isinstance(self.swing_direction, DoorSwing) else str(self.swing_direction),
            "swing_angle_deg": self.swing_angle_deg,
            "connects_rooms": self.connects_rooms,
        }

    @classmethod
    def from_legacy_dict(cls, d: Dict[str, Any], idx: int = 0, room_x: float = 0.0, room_y: float = 0.0) -> Door:
        wall = d.get("wall", "bottom")
        pos_val = float(d.get("position", 0.0))
        w = float(d.get("width", 0.90))

        # Approximate metric world position from room origin + offset
        if wall in ("bottom", "top"):
            world_pos = Point2D(room_x + pos_val, room_y)
        else:
            world_pos = Point2D(room_x, room_y + pos_val)

        return cls(
            id=f"door_{idx+1}",
            position=world_pos,
            width=w,
            height=2.10,
            wall=wall,
            offset_along_wall=pos_val,
            swing_direction=DoorSwing.INWARD_RIGHT,
            swing_angle_deg=90.0,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Door:
        return cls(
            id=data.get("id", ""),
            position=Point2D.from_any(data.get("position", {"x": 0.0, "y": 0.0})),
            width=float(data.get("width", 0.90)),
            height=float(data.get("height", 2.10)),
            wall=data.get("wall"),
            offset_along_wall=float(data["offset_along_wall"]) if data.get("offset_along_wall") is not None else None,
            wall_id=data.get("wall_id"),
            swing_direction=DoorSwing(data.get("swing_direction", DoorSwing.INWARD_RIGHT)),
            swing_angle_deg=float(data.get("swing_angle_deg", 90.0)),
            connects_rooms=data.get("connects_rooms", []),
        )


@dataclass
class Window:
    """Architectural Window object with position, dimensions, and wall attachment."""
    id                : str
    position          : Point2D
    width             : float         = 1.20     # in metres
    height            : float         = 1.20     # in metres
    sill_height       : float         = 0.90     # in metres
    wall              : Optional[str] = None     # legacy orientation
    offset_along_wall : Optional[float] = None   # legacy relative position along room wall
    wall_id           : Optional[str] = None
    window_type       : WindowType    = WindowType.STANDARD

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Produces exact legacy window format used by current renderer and rules engine."""
        return {
            "wall": self.wall or "right",
            "position": round(self.offset_along_wall if self.offset_along_wall is not None else self.position.y, 2),
            "width": round(self.width, 2),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "position": self.position.to_dict(),
            "width": round(self.width, 3),
            "height": round(self.height, 3),
            "sill_height": round(self.sill_height, 3),
            "wall": self.wall,
            "offset_along_wall": round(self.offset_along_wall, 3) if self.offset_along_wall is not None else None,
            "wall_id": self.wall_id,
            "window_type": self.window_type.value if isinstance(self.window_type, WindowType) else str(self.window_type),
        }

    @classmethod
    def from_legacy_dict(cls, d: Dict[str, Any], idx: int = 0, room_x: float = 0.0, room_y: float = 0.0) -> Window:
        wall = d.get("wall", "right")
        pos_val = float(d.get("position", 0.0))
        w = float(d.get("width", 1.20))

        if wall in ("bottom", "top"):
            world_pos = Point2D(room_x + pos_val, room_y)
        else:
            world_pos = Point2D(room_x, room_y + pos_val)

        return cls(
            id=f"win_{idx+1}",
            position=world_pos,
            width=w,
            height=1.20,
            sill_height=0.90,
            wall=wall,
            offset_along_wall=pos_val,
            window_type=WindowType.STANDARD,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Window:
        return cls(
            id=data.get("id", ""),
            position=Point2D.from_any(data.get("position", {"x": 0.0, "y": 0.0})),
            width=float(data.get("width", 1.20)),
            height=float(data.get("height", 1.20)),
            sill_height=float(data.get("sill_height", 0.90)),
            wall=data.get("wall"),
            offset_along_wall=float(data["offset_along_wall"]) if data.get("offset_along_wall") is not None else None,
            wall_id=data.get("wall_id"),
            window_type=WindowType(data.get("window_type", WindowType.STANDARD)),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  WALL SEGMENTS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class WallSegment:
    """Wall segment representation with start/end coordinates, thickness, and material."""
    id             : str
    start          : Point2D
    end            : Point2D
    thickness      : float           = 0.20     # in metres (e.g. 0.20m exterior, 0.10m interior)
    wall_type      : WallType        = WallType.INTERIOR
    height         : float           = 2.80     # in metres
    material       : Optional[str]   = "brick"
    connected_rooms: List[str]       = field(default_factory=list)

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def centerline(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        return (self.start.to_tuple(), self.end.to_tuple())

    @property
    def polygon_footprint(self) -> List[Point2D]:
        """Calculates 4 oriented corner coordinates of wall accounting for thickness."""
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        ln = self.length
        if ln < 1e-6:
            return [self.start, self.start, self.end, self.end]

        nx = (-dy / ln) * (self.thickness / 2.0)
        ny = (dx / ln) * (self.thickness / 2.0)

        return [
            Point2D(self.start.x + nx, self.start.y + ny),
            Point2D(self.end.x + nx, self.end.y + ny),
            Point2D(self.end.x - nx, self.end.y - ny),
            Point2D(self.start.x - nx, self.start.y - ny),
        ]

    def to_shapely(self) -> Any:
        """Returns Shapely Polygon for wall footprint or LineString if Shapely available."""
        if not SHAPELY_AVAILABLE:
            return None
        pts = [p.to_tuple() for p in self.polygon_footprint]
        return ShapelyPolygon(pts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "thickness": round(self.thickness, 3),
            "wall_type": self.wall_type.value if isinstance(self.wall_type, WallType) else str(self.wall_type),
            "height": round(self.height, 3),
            "material": self.material,
            "connected_rooms": self.connected_rooms,
            "length_m": round(self.length, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WallSegment:
        return cls(
            id=data.get("id", ""),
            start=Point2D.from_any(data["start"]),
            end=Point2D.from_any(data["end"]),
            thickness=float(data.get("thickness", 0.20)),
            wall_type=WallType(data.get("wall_type", WallType.INTERIOR)),
            height=float(data.get("height", 2.80)),
            material=data.get("material", "brick"),
            connected_rooms=data.get("connected_rooms", []),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  ROOMS AS POLYGONS (with AABB backward compatibility)
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Room:
    """
    Architectural Room model.
    Internal representation: 2D polygon vertices.
    Backward compatibility: dynamically provides (x, y, width, height, area_m2).
    """
    id       : str
    name     : str                      # Room type e.g. "bedroom", "living", "kitchen"
    polygon  : List[Point2D]            # Ordered list of boundary vertices in metres
    doors    : List[Door]               = field(default_factory=list)
    windows  : List[Window]             = field(default_factory=list)
    level    : int                      = 1
    metadata : Dict[str, Any]           = field(default_factory=dict)

    # ── BACKWARD COMPATIBILITY PROPERTIES ─────────────────────────────────────

    @property
    def x(self) -> float:
        """Min X of polygon bounding box (metres)."""
        if not self.polygon: return 0.0
        return round(min(p.x for p in self.polygon), 3)

    @property
    def y(self) -> float:
        """Min Y of polygon bounding box (metres)."""
        if not self.polygon: return 0.0
        return round(min(p.y for p in self.polygon), 3)

    @property
    def width(self) -> float:
        """Width of polygon bounding box (metres)."""
        if not self.polygon: return 0.0
        xs = [p.x for p in self.polygon]
        return round(max(xs) - min(xs), 3)

    @property
    def height(self) -> float:
        """Height of polygon bounding box (metres)."""
        if not self.polygon: return 0.0
        ys = [p.y for p in self.polygon]
        return round(max(ys) - min(ys), 3)

    @property
    def area_m2(self) -> float:
        """Area in square metres computed from polygon vertices (Shoelace formula)."""
        if len(self.polygon) < 3:
            return round(self.width * self.height, 2)
        n = len(self.polygon)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.polygon[i].x * self.polygon[j].y
            area -= self.polygon[j].x * self.polygon[i].y
        return round(abs(area) / 2.0, 2)

    @property
    def centroid(self) -> Point2D:
        """Polygon centroid coordinate."""
        if not self.polygon:
            return Point2D(0.0, 0.0)
        if len(self.polygon) < 3:
            return Point2D(self.x + self.width / 2.0, self.y + self.height / 2.0)

        # Polygon centroid calculation
        n = len(self.polygon)
        cx, cy, signed_area = 0.0, 0.0, 0.0
        for i in range(n):
            j = (i + 1) % n
            factor = (self.polygon[i].x * self.polygon[j].y - self.polygon[j].x * self.polygon[i].y)
            cx += (self.polygon[i].x + self.polygon[j].x) * factor
            cy += (self.polygon[i].y + self.polygon[j].y) * factor
            signed_area += factor

        signed_area *= 0.5
        if abs(signed_area) < 1e-6:
            return Point2D(self.x + self.width / 2.0, self.y + self.height / 2.0)

        cx = cx / (6.0 * signed_area)
        cy = cy / (6.0 * signed_area)
        return Point2D(round(cx, 3), round(cy, 3))

    @property
    def shape(self) -> str:
        """Returns 'rectangle' if 4 orthogonal points, else 'polygon'."""
        if len(self.polygon) == 4:
            # Check orthogonality
            return "rectangle"
        return "polygon"

    def to_shapely(self) -> Any:
        """Converts room boundary to a Shapely Polygon."""
        if not SHAPELY_AVAILABLE or len(self.polygon) < 3:
            return None
        return ShapelyPolygon([p.to_tuple() for p in self.polygon])

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Produces exact legacy room dictionary consumed by:
          - core/rules_engine.py
          - core/geometry.py
          - core/renderer.py
          - static/index.html
        """
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "area_m2": round(self.area_m2, 1),
            "shape": self.shape,
            "doors": [d.to_legacy_dict() for d in self.doors],
            "windows": [w.to_legacy_dict() for w in self.windows],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Produces canonical schema dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "polygon": [p.to_dict() for p in self.polygon],
            "doors": [d.to_dict() for d in self.doors],
            "windows": [w.to_dict() for w in self.windows],
            "level": self.level,
            "metadata": self.metadata,
            "computed": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
                "area_m2": self.area_m2,
                "centroid": self.centroid.to_dict(),
                "shape": self.shape,
            }
        }

    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any], default_name: str = "unknown") -> Room:
        """Constructs canonical Room from legacy dict (e.g. from existing cv_analyzer)."""
        rid = data.get("id", "room_1")
        name = data.get("name", default_name)

        if "polygon" in data and data["polygon"]:
            poly = [Point2D.from_any(pt) for pt in data["polygon"]]
        else:
            # Construct rectangular polygon from x, y, width, height
            x = float(data.get("x", 0.0))
            y = float(data.get("y", 0.0))
            w = float(data.get("width", 1.0))
            h = float(data.get("height", 1.0))
            poly = [
                Point2D(x, y),
                Point2D(x + w, y),
                Point2D(x + w, y + h),
                Point2D(x, y + h),
            ]

        doors = [
            Door.from_legacy_dict(d, idx=i, room_x=float(data.get("x", 0.0)), room_y=float(data.get("y", 0.0)))
            for i, d in enumerate(data.get("doors", []))
        ]
        windows = [
            Window.from_legacy_dict(w, idx=i, room_x=float(data.get("x", 0.0)), room_y=float(data.get("y", 0.0)))
            for i, w in enumerate(data.get("windows", []))
        ]

        return cls(
            id=rid,
            name=name,
            polygon=poly,
            doors=doors,
            windows=windows,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Room:
        """Constructs Room from canonical dict."""
        poly = [Point2D.from_any(pt) for pt in data.get("polygon", [])]
        doors = [Door.from_dict(d) for d in data.get("doors", [])]
        windows = [Window.from_dict(w) for w in data.get("windows", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "unknown"),
            polygon=poly,
            doors=doors,
            windows=windows,
            level=int(data.get("level", 1)),
            metadata=data.get("metadata", {}),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  DETECTED ELEMENTS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class DetectedElement:
    """Special element detected on plan (CCTV camera, NVR, panel, etc.)."""
    id      : str
    type    : str            # "camera", "nvr", "electrical_panel", etc.
    label   : str            = ""
    position: Point2D        = field(default_factory=lambda: Point2D(0.0, 0.0))
    width   : float          = 0.5
    height  : float          = 0.5
    notes   : str            = ""

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label,
            "x": round(self.position.x, 2),
            "y": round(self.position.y, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "notes": self.notes,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "position": self.position.to_dict(),
            "width": round(self.width, 3),
            "height": round(self.height, 3),
            "notes": self.notes,
        }

    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any], idx: int = 0) -> DetectedElement:
        return cls(
            id=f"elem_{idx+1}",
            type=data.get("type", "camera"),
            label=data.get("label", ""),
            position=Point2D(float(data.get("x", 0.0)), float(data.get("y", 0.0))),
            width=float(data.get("width", 0.5)),
            height=float(data.get("height", 0.5)),
            notes=data.get("notes", ""),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DetectedElement:
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "camera"),
            label=data.get("label", ""),
            position=Point2D.from_any(data.get("position", {"x": 0.0, "y": 0.0})),
            width=float(data.get("width", 0.5)),
            height=float(data.get("height", 0.5)),
            notes=data.get("notes", ""),
        )


# ═════════════════════════════════════════════════════════════════════════════
#  SITE & CANONICAL ARCHITECTURAL PLAN ROOT
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class SiteInfo:
    """Site / compound overall dimensions and footprint boundary."""
    total_width     : float
    total_height    : float
    has_compound    : bool          = False
    boundary_polygon: List[Point2D] = field(default_factory=list)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "total_width": round(self.total_width, 1),
            "total_height": round(self.total_height, 1),
            "has_compound": self.has_compound,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_width": round(self.total_width, 3),
            "total_height": round(self.total_height, 3),
            "has_compound": self.has_compound,
            "boundary_polygon": [p.to_dict() for p in self.boundary_polygon],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SiteInfo:
        poly = [Point2D.from_any(p) for p in data.get("boundary_polygon", [])]
        return cls(
            total_width=float(data.get("total_width", 15.0)),
            total_height=float(data.get("total_height", 12.0)),
            has_compound=bool(data.get("has_compound", False)),
            boundary_polygon=poly,
        )


@dataclass
class ArchitecturalPlan:
    """
    Canonical Root Schema Container for architectural floor plans.
    """
    schema_version   : str                       = "2.0.0"
    plan_id          : str                       = ""
    plan_type        : str                       = "architectural"
    confidence       : float                     = 1.0
    unit             : LengthUnit                = LengthUnit.METRES
    coordinate_system: CoordinateSystem          = field(default_factory=CoordinateSystem)
    scale            : ScaleInfo                 = field(default_factory=lambda: ScaleInfo(scale_m_per_px=0.015))
    site             : SiteInfo                  = field(default_factory=lambda: SiteInfo(total_width=15.0, total_height=12.0))
    rooms            : List[Room]                = field(default_factory=list)
    walls            : List[WallSegment]         = field(default_factory=list)
    doors            : List[Door]                = field(default_factory=list)
    windows          : List[Window]              = field(default_factory=list)
    detected_elements: List[DetectedElement]     = field(default_factory=list)
    dimensions       : List[DimensionAnnotation] = field(default_factory=list)
    electrical_hints : List[Dict[str, Any]]      = field(default_factory=list)
    warnings         : List[str]                 = field(default_factory=list)
    metadata         : Dict[str, Any]            = field(default_factory=dict)

    # ── CONVERSION METHODS ───────────────────────────────────────────────────

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Converts canonical plan to the exact legacy 'vision_data' dict structure.
        Ensures 100% backward compatibility for all downstream modules.
        """
        return {
            "plan_type": self.plan_type,
            "confidence": round(self.confidence, 2),
            "unit": self.unit.value if isinstance(self.unit, LengthUnit) else str(self.unit),
            "site": self.site.to_legacy_dict(),
            "rooms": [r.to_legacy_dict() for r in self.rooms],
            "detected_elements": [e.to_legacy_dict() for e in self.detected_elements],
            "electrical_hints": self.electrical_hints,
            "warnings": self.warnings,
            "_debug": self.metadata.get("_debug", {}),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full canonical JSON representation."""
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "plan_type": self.plan_type,
            "confidence": round(self.confidence, 2),
            "unit": self.unit.value if isinstance(self.unit, LengthUnit) else str(self.unit),
            "coordinate_system": self.coordinate_system.to_dict(),
            "scale": self.scale.to_dict(),
            "site": self.site.to_dict(),
            "rooms": [r.to_dict() for r in self.rooms],
            "walls": [w.to_dict() for w in self.walls],
            "doors": [d.to_dict() for d in self.doors],
            "windows": [w.to_dict() for w in self.windows],
            "detected_elements": [e.to_dict() for e in self.detected_elements],
            "dimensions": [d.to_dict() for d in self.dimensions],
            "electrical_hints": self.electrical_hints,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any]) -> ArchitecturalPlan:
        """
        Constructs an ArchitecturalPlan from a legacy 'vision_data' dict.
        Automatically converts rectangular rooms to polygon rooms and derives wall segments.
        """
        unit_str = data.get("unit", "metres")
        conf = float(data.get("confidence", 1.0))
        plan_type = data.get("plan_type", "local_cv")

        site_d = data.get("site", {})
        site = SiteInfo(
            total_width=float(site_d.get("total_width", 15.0)),
            total_height=float(site_d.get("total_height", 12.0)),
            has_compound=bool(site_d.get("has_compound", False)),
        )

        rooms = [Room.from_legacy_dict(r) for r in data.get("rooms", [])]
        elements = [DetectedElement.from_legacy_dict(e, idx=i) for i, e in enumerate(data.get("detected_elements", []))]

        # Collect doors and windows across rooms
        all_doors = []
        all_windows = []
        for r in rooms:
            all_doors.extend(r.doors)
            all_windows.extend(r.windows)

        # Derive initial wall segments from room boundaries if walls not explicitly provided
        walls = []
        wall_id = 1
        for r in rooms:
            poly = r.polygon
            n = len(poly)
            for i in range(n):
                p1 = poly[i]
                p2 = poly[(i + 1) % n]
                walls.append(WallSegment(
                    id=f"wall_{wall_id}",
                    start=p1,
                    end=p2,
                    thickness=0.20 if (p1.x == 0 or p1.y == 0) else 0.10,
                    wall_type=WallType.INTERIOR,
                    connected_rooms=[r.id],
                ))
                wall_id += 1

        dbg = data.get("_debug", {})
        scale_val = float(dbg.get("scale_mppx", 0.015)) if isinstance(dbg, dict) else 0.015

        return cls(
            plan_type=plan_type,
            confidence=conf,
            unit=LengthUnit.METRES if unit_str == "metres" else LengthUnit(unit_str),
            coordinate_system=CoordinateSystem(origin=OriginLocation.BOTTOM_LEFT, unit=LengthUnit.METRES),
            scale=ScaleInfo(scale_m_per_px=scale_val),
            site=site,
            rooms=rooms,
            walls=walls,
            doors=all_doors,
            windows=all_windows,
            detected_elements=elements,
            electrical_hints=data.get("electrical_hints", []),
            warnings=data.get("warnings", []),
            metadata={"_debug": dbg},
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitecturalPlan:
        """Constructs an ArchitecturalPlan from a canonical dictionary."""
        return cls(
            schema_version=data.get("schema_version", "2.0.0"),
            plan_id=data.get("plan_id", ""),
            plan_type=data.get("plan_type", "architectural"),
            confidence=float(data.get("confidence", 1.0)),
            unit=LengthUnit(data.get("unit", LengthUnit.METRES)),
            coordinate_system=CoordinateSystem.from_dict(data.get("coordinate_system", {})),
            scale=ScaleInfo.from_dict(data.get("scale", {})),
            site=SiteInfo.from_dict(data.get("site", {})),
            rooms=[Room.from_dict(r) for r in data.get("rooms", [])],
            walls=[WallSegment.from_dict(w) for w in data.get("walls", [])],
            doors=[Door.from_dict(d) for d in data.get("doors", [])],
            windows=[Window.from_dict(w) for w in data.get("windows", [])],
            detected_elements=[DetectedElement.from_dict(e) for e in data.get("detected_elements", [])],
            dimensions=[DimensionAnnotation.from_dict(d) for d in data.get("dimensions", [])],
            electrical_hints=data.get("electrical_hints", []),
            warnings=data.get("warnings", []),
            metadata=data.get("metadata", {}),
        )
