"""Day 2 — crowd density map (DM-Count pretrained) for dense crowds where detection under-counts."""
from __future__ import annotations

import numpy as np


class DensityEstimator:
    def __init__(self, weights: str, device: str):
        self.weights, self.device = weights, device

    def estimate(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        """Return (density_map resized to image HxW, total count)."""
        # TODO(Day 2): load DM-Count VGG19 model, normalize with ImageNet stats, upsample map
        raise NotImplementedError("Day 2")
