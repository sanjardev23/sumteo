"""Day 1 — zones (polygons) and entry/exit counting lines."""
from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


@dataclass
class Polygon:
    points: list[Point]

    def contains(self, pt: Point) -> bool:
        # TODO(Day 1): ray casting (or cv2.pointPolygonTest)
        raise NotImplementedError("Day 1")


@dataclass
class Line:
    a: Point
    b: Point

    def side(self, pt: Point) -> int:
        """+1 / -1 for the two sides of the line, 0 on it. A side change between frames = a crossing."""
        # TODO(Day 1): sign of the cross product (b - a) × (pt - a)
        raise NotImplementedError("Day 1")
