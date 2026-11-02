"""Day 1 — person detection + tracking (YOLO26 + ByteTrack).

Kept behind this interface so the AGPL Ultralytics model can be swapped (e.g. RT-DETR) in one file.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

PERSON_CLASS = 0  # COCO


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
        self.model = YOLO(weights)
        self.imgsz, self.conf, self.tracker, self.device = imgsz, conf, tracker, device

    def update(self, image: np.ndarray) -> list[Detection]:
        result = self.model.track(
            image, classes=[PERSON_CLASS], persist=True, tracker=self.tracker,
            imgsz=self.imgsz, conf=self.conf, device=self.device, verbose=False,
        )[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:   # ByteTrack has not confirmed any track yet
            return []
        return [
            Detection(track_id=int(tid), bbox=tuple(map(float, xyxy)), conf=float(c))
            for tid, xyxy, c in zip(boxes.id.tolist(), boxes.xyxy.tolist(), boxes.conf.tolist())
        ]
