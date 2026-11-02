"""Day 1 — video input: file, webcam index or RTSP URL."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np


@dataclass
class Frame:
    image: np.ndarray   # BGR
    ts: float           # seconds since start (from frame index for files → reproducible)
    index: int


class VideoSource:
    def __init__(self, source: str | int, target_fps: float | None = None):
        self.source = source
        self.target_fps = target_fps

    def frames(self) -> Iterator[Frame]:
        # TODO(Day 1): cv2.VideoCapture, skip frames to match target_fps, release on exit
        raise NotImplementedError("Day 1")
