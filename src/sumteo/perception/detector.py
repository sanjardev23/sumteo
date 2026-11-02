"""Day 1 — person detection + tracking (YOLO11 + ByteTrack).

Kept behind this interface so the AGPL Ultralytics model can be swapped (e.g. RT-DETR) in one file.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    track_id: int
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 pixels
    conf: float

    @property
    def foot_point(self) -> tuple[float, float]:
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)


class PersonTracker:
    def __init__(self, weights: str, imgsz: int, conf: float, tracker: str, device: str):
        # TODO(Day 1): self.model = YOLO(weights)
        self.weights, self.imgsz, self.conf, self.tracker, self.device = weights, imgsz, conf, tracker, device

    def update(self, image: np.ndarray) -> list[Detection]:
        # TODO(Day 1): self.model.track(image, classes=[0], persist=True, tracker=..., imgsz=..., conf=..., device=...)
        raise NotImplementedError("Day 1")
