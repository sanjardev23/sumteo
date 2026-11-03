"""Day 3 — dense optical flow (Farneback) for crowd movement and turbulence."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import Polygon

GRID_STEP_PX = 8     # zone flow is sampled on this pixel grid (full resolution); denser adds time, not accuracy
_LINEARIZE_S = 0.1   # world velocity = homography difference over this short step


@dataclass
class ZoneFlow:
    speed_mps: float = 0.0     # mean ground speed, weighted by the density map so empty ground doesn't count
    turbulence: float = 0.0    # 1 − |mean unit direction| of moving points: 0 = one direction, 1 = chaotic
    counter_flow: float = 0.0  # weighted share of moving points heading > 90° away from the main direction


class FlowEstimator:
    """Flow is only needed inside the zones, so it runs on their bounding box (`roi` = x, y, w, h in pixels)."""

    def __init__(self, scale: float = 0.5, roi: tuple[int, int, int, int] | None = None):
        self.scale = scale
        self.roi = roi
        self._prev_gray: np.ndarray | None = None
        self._prev_ts = 0.0

    @property
    def origin(self) -> tuple[int, int]:
        return self.roi[:2] if self.roi else (0, 0)

    def update(self, image: np.ndarray, ts: float) -> np.ndarray | None:
        """Flow field (h, w, 2) of the roi at `scale` resolution, in full-resolution pixels per second; None on the
        first frame."""
        if self.roi:
            x, y, w, h = self.roi
            image = image[y:y + h, x:x + w]
        gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None, fx=self.scale, fy=self.scale,
                          interpolation=cv2.INTER_AREA)
        prev, prev_ts = self._prev_gray, self._prev_ts
        self._prev_gray, self._prev_ts = gray, ts
        if prev is None or ts <= prev_ts:
            return None
        flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        return flow / (self.scale * (ts - prev_ts))


def zones_roi(polygons: list[Polygon], shape: tuple[int, int], margin: int = GRID_STEP_PX) -> tuple[int, int, int, int]:
    """Bounding box (x, y, w, h) around all zones, clipped to the image."""
    pts = np.concatenate([np.asarray(p.points) for p in polygons])
    x0, y0 = np.maximum(pts.min(axis=0).astype(int) - margin, 0)
    x1, y1 = np.minimum(pts.max(axis=0).astype(int) + margin, (shape[1], shape[0]))
    return int(x0), int(y0), int(x1 - x0), int(y1 - y0)


def zone_grid(polygon: Polygon, shape: tuple[int, int]) -> np.ndarray:
    """Full-resolution pixel points (N, 2) on a GRID_STEP_PX grid inside the zone."""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.int32(polygon.points)], 1)
    ys, xs = np.mgrid[GRID_STEP_PX // 2:h:GRID_STEP_PX, GRID_STEP_PX // 2:w:GRID_STEP_PX]
    inside = mask[ys, xs].astype(bool)
    return np.stack([xs[inside], ys[inside]], axis=1).astype(np.float64)


def zone_flow(flow: np.ndarray, scale: float, points: np.ndarray, homography: Homography,
              density_map: np.ndarray | None, moving_mps: float, origin: tuple[int, int] = (0, 0)) -> ZoneFlow:
    """Ground velocities (m/s) of the zone's grid points → speed, turbulence and counter-flow. `origin` = top-left
    pixel of the flow field's roi."""
    if len(points) == 0:
        return ZoneFlow()
    fh, fw = flow.shape[:2]
    ix = np.clip(((points[:, 0] - origin[0]) * scale).astype(int), 0, fw - 1)
    iy = np.clip(((points[:, 1] - origin[1]) * scale).astype(int), 0, fh - 1)
    v_px = flow[iy, ix].astype(np.float64)
    here = cv2.perspectiveTransform(points[None], homography.H)[0]
    ahead = cv2.perspectiveTransform((points + v_px * _LINEARIZE_S)[None], homography.H)[0]
    v = (ahead - here) / _LINEARIZE_S
    speed = np.hypot(v[:, 0], v[:, 1])

    weights = density_map[points[:, 1].astype(int), points[:, 0].astype(int)] if density_map is not None else None
    if weights is None or weights.sum() <= 0:
        weights = np.ones(len(points))
    mean_speed = float((weights * speed).sum() / weights.sum())

    moving = speed >= moving_mps
    w = weights[moving]
    if w.sum() <= 0:
        return ZoneFlow(speed_mps=mean_speed)
    units = v[moving] / speed[moving, None]
    resultant = (w[:, None] * units).sum(axis=0) / w.sum()
    length = float(np.hypot(*resultant))
    counter = float(w[units @ resultant < 0].sum() / w.sum()) if length > 0 else 0.0
    return ZoneFlow(speed_mps=mean_speed, turbulence=1.0 - length, counter_flow=counter)
