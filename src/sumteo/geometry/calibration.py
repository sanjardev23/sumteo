"""Day 1 — pixel ↔ meter homography from 4 ground points."""
from __future__ import annotations

import cv2
import numpy as np

Point = tuple[float, float]


class Homography:
    """Maps image pixels on the ground plane to meters. Only valid for points on the ground (foot points)."""

    def __init__(self, image_points: list[Point], world_points: list[Point]):
        if len(image_points) != 4 or len(world_points) != 4:
            raise ValueError("calibration needs exactly 4 image points and 4 world points")
        self.image_points, self.world_points = image_points, world_points
        self.H = cv2.getPerspectiveTransform(
            np.asarray(image_points, dtype=np.float32), np.asarray(world_points, dtype=np.float32)
        )

    def to_world(self, pt: Point) -> Point:
        x, y = cv2.perspectiveTransform(np.asarray([[pt]], dtype=np.float64), self.H)[0, 0]
        return (float(x), float(y))

    def polygon_area_m2(self, polygon: list[Point]) -> float:
        # Shoelace on the world-space vertices; a straight edge stays straight under a homography.
        world = np.asarray([self.to_world(p) for p in polygon])
        x, y = world[:, 0], world[:, 1]
        return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)
