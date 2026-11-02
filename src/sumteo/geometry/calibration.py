"""Day 1 — pixel ↔ meter homography from 4 ground points."""
from __future__ import annotations

Point = tuple[float, float]


class Homography:
    def __init__(self, image_points: list[Point], world_points: list[Point]):
        # TODO(Day 1): self.H = cv2.getPerspectiveTransform(...)
        self.image_points, self.world_points = image_points, world_points

    def to_world(self, pt: Point) -> Point:
        raise NotImplementedError("Day 1")

    def polygon_area_m2(self, polygon: list[Point]) -> float:
        # TODO(Day 1): map vertices to world, shoelace formula
        raise NotImplementedError("Day 1")
