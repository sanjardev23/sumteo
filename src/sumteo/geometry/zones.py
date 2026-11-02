"""Day 1 — zones (polygons) and entry/exit counting lines."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

Point = tuple[float, float]


@dataclass
class Polygon:
    points: list[Point]
    _contour: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        if len(self.points) < 3:
            raise ValueError(f"a polygon needs at least 3 points, got {len(self.points)}")
        self._contour = np.asarray(self.points, dtype=np.float32).reshape(-1, 1, 2)

    def contains(self, pt: Point) -> bool:
        """Points on the edge count as inside, so a person standing on the border is not lost."""
        return cv2.pointPolygonTest(self._contour, (float(pt[0]), float(pt[1])), False) >= 0


@dataclass
class Line:
    a: Point
    b: Point

    def side(self, pt: Point) -> int:
        """+1 / -1 for the two sides of the line, 0 on it. A side change between frames = a crossing."""
        cross = (self.b[0] - self.a[0]) * (pt[1] - self.a[1]) - (self.b[1] - self.a[1]) * (pt[0] - self.a[0])
        return (cross > 0) - (cross < 0)
