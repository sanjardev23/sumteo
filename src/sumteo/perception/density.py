"""Day 2 — crowd density map (DM-Count pretrained) for dense crowds where detection under-counts.

Model: DM-Count (Wang et al., NeurIPS 2020, MIT license), VGG19 backbone + small regression head, re-declared here
so the authors' pretrained weights load directly.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

_VGG19 = [64, 64, "M", 128, 128, "M", 256, 256, 256, 256, "M", 512, 512, 512, 512, "M", 512, 512, 512, 512]
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)  # ImageNet stats, as in DM-Count training
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class _DMCount(nn.Module):
    def __init__(self):
        super().__init__()
        layers, channels = [], 3
        for v in _VGG19:
            if v == "M":
                layers.append(nn.MaxPool2d(2, 2))
            else:
                layers += [nn.Conv2d(channels, v, 3, padding=1), nn.ReLU(inplace=True)]
                channels = v
        self.features = nn.Sequential(*layers)
        self.reg_layer = nn.Sequential(
            nn.Conv2d(512, 256, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(256, 128, 3, padding=1), nn.ReLU(inplace=True),
        )
        self.density_layer = nn.Sequential(nn.Conv2d(128, 1, 1), nn.ReLU())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(self.features(x), scale_factor=2, mode="bilinear", align_corners=True)
        return self.density_layer(self.reg_layer(x))  # people per cell, 1/8 of the input resolution


class DensityEstimator:
    def __init__(self, weights: str, device: str):
        self.weights, self.device = weights, torch.device(device)
        self.model = _DMCount()
        self.model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        self.model.to(self.device).eval()

    @torch.inference_mode()
    def estimate(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        """Return (density_map resized to image HxW, total count). `image` is BGR."""
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = torch.from_numpy((rgb - _MEAN) / _STD).permute(2, 0, 1)[None].to(self.device)
        cells = self.model(x)[0, 0].float().cpu().numpy()
        count = float(cells.sum())
        h, w = image.shape[:2]
        density = cv2.resize(cells, (w, h), interpolation=cv2.INTER_LINEAR)
        total = float(density.sum())
        if total > 0:
            density *= count / total  # resizing spreads the cells; rescale so the map still sums to the count
        return density, count
