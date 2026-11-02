"""Day 3 — dense optical flow (Farneback) for crowd movement and turbulence."""
from __future__ import annotations

import numpy as np


class FlowEstimator:
    def __init__(self, scale: float = 0.5):
        self.scale = scale
        self._prev_gray: np.ndarray | None = None

    def update(self, image: np.ndarray) -> np.ndarray | None:
        """Return flow field (H, W, 2) at full resolution, or None on the first frame."""
        # TODO(Day 3): downscale, gray, cv2.calcOpticalFlowFarneback, upscale vectors
        raise NotImplementedError("Day 3")
