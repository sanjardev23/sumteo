"""Day 3 — camera health: a lost, frozen or dark feed at a hotspot is a silent failure, so it raises CAMERA_HEALTH."""
from __future__ import annotations

import cv2
import numpy as np

from sumteo.events.models import Condition, EventType
from sumteo.video.source import Frame

_THUMB = (160, 90)  # frozen / dark are judged on a small gray thumbnail: cheap, and compression noise averages out


class CameraHealth:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._prev: np.ndarray | None = None
        self._still_since: float | None = None
        self.problems: list[str] = []   # latest result, for the overlay

    def update(self, frame: Frame) -> list[Condition]:
        """One CAMERA_HEALTH condition (zone None) listing every problem right now, so lost + frozen + dark together
        are one event. `frame.image is None` means the source reports the feed as lost."""
        if frame.image is None:
            self._prev, self._still_since = None, None
            self.problems = ["lost"]
        else:
            thumb = cv2.resize(cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY), _THUMB, interpolation=cv2.INTER_AREA)
            thumb = thumb.astype(np.float32)
            changed = self._prev is None or float(np.abs(thumb - self._prev).mean()) >= self.cfg["frozen_diff_below"]
            self._prev = thumb
            self._still_since = None if changed else (frame.ts if self._still_since is None else self._still_since)
            self.problems = []
            if self._still_since is not None and frame.ts - self._still_since >= self.cfg["frozen_seconds"]:
                self.problems.append("frozen")
            if float(thumb.mean()) < self.cfg["dark_mean_below"]:
                self.problems.append("dark")
        if not self.problems:
            return []
        return [Condition(EventType.CAMERA_HEALTH, details={"problems": list(self.problems)})]
