"""Per-camera processing loop. Grows day by day; see docs/PLAN.md."""
from __future__ import annotations

import statistics
import time

import cv2
import numpy as np

from sumteo.analytics.crowd import CrowdAnalyzer, CrowdMetrics, risk_factor
from sumteo.analytics.state import TrackStore
from sumteo.config import AppConfig, CameraConfig
from sumteo.events.engine import RuleEngine
from sumteo.events.notifiers.console import ConsoleNotifier
from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import ZoneShape
from sumteo.perception.density import DensityEstimator
from sumteo.perception.detector import PersonTracker
from sumteo.perception.flow import FlowEstimator, ZoneFlow, zone_flow, zone_grid, zones_roi
from sumteo.video.health import CameraHealth
from sumteo.video.overlay import Overlay
from sumteo.video.source import VideoSource

QUIT_KEYS = (ord("q"), 27)  # q / Esc
HEATMAP_KEY, FLOW_KEY = ord("h"), ord("f")


class Pipeline:
    def __init__(self, app: AppConfig, camera: CameraConfig):
        self.app = app
        self.camera = camera
        runtime, models, health = app.runtime, app.models, app.camera_health
        self.source = VideoSource(camera.source, target_fps=runtime.get("target_fps"),
                                  reconnect_attempts=health["reconnect_attempts"],
                                  reconnect_wait_s=health["reconnect_wait_s"])
        self.tracker = PersonTracker(
            models["detector"], models["detector_imgsz"], models["detector_conf"], models["tracker"], runtime["device"],
        )
        self.density = DensityEstimator(models["density"], runtime["device"])
        self.density_every = models["density_every_n_frames"]
        self.flow = FlowEstimator()
        self.flow_every = models["flow_every_n_frames"]
        self.health = CameraHealth(health)

        calibration = camera.calibration
        self.homography = (Homography(calibration.image_points, calibration.world_points)
                           if len(calibration.image_points) == 4 else None)
        self.zones = [ZoneShape.from_config(z) for z in camera.zones if len(z.polygon) >= 3]
        self.zone_areas = {z.id: self.homography.polygon_area_m2(z.polygon.points) if self.homography else None
                           for z in self.zones}
        tracking = app.tracking
        self.tracks = TrackStore(tracking["lost_after_s"], tracking["speed_window_s"], tracking["still_speed_mps"],
                                 tracking["line_band_m"], tracking["recross_lockout_s"])
        # Levels need people/m², so only calibrated zones get an analyzer.
        risks = {z.id: z.risk for z in camera.zones}
        self.analyzers = {
            z.id: CrowdAnalyzer(app.crowd, z.id, self.zone_areas[z.id], risk_factor(app.crowd, risks[z.id]))
            for z in self.zones if self.zone_areas[z.id]
        }
        self.engine = RuleEngine(camera.id, app.events["debounce_s"], app.events["cooldown_s"])
        self.notifiers = [ConsoleNotifier()] if app.notifiers.get("console") else []
        self.overlay = Overlay()
        # A camera with its own level thresholds is a demo: say so on screen, so it can't be mistaken for real danger.
        self.demo_levels = app.crowd["levels_ppm2"] if "levels_ppm2" in camera.overrides.get("crowd", {}) else None
        self.metrics: dict[str, CrowdMetrics] = {}
        self.active: dict[str, list[str]] = {}                   # zone id → condition types holding now (badges)
        self.zone_crossings = {z.id: {"in": 0, "out": 0} for z in self.zones}
        # Day 4: db, blur
        # Day 5: platform notifier → API

    def run(self) -> None:
        show = self.app.runtime.get("show_window", True)
        save_path = self.app.runtime.get("save_path")
        writer: cv2.VideoWriter | None = None
        fps = _FpsMeter()
        density_map, zone_density, masks = None, {}, None
        flow_field, grids, zone_flows = None, None, {}
        show_heatmap, show_flow = False, False
        try:
            for i, frame in enumerate(self.source.frames()):
                conditions = self.health.update(frame)
                if self.health.problems:
                    # A lost, frozen or dark feed says nothing about the crowd: zones keep their last level and emit
                    # nothing, so a covered lens (0 people → GREEN) can never announce an all-clear.
                    self._fire(frame.ts, conditions)
                    if frame.image is None:
                        continue
                else:
                    detections = self.tracker.update(frame.image)
                    crossings = self.tracks.update(frame.ts, detections, self.homography, self.zones)
                    if i % self.density_every == 0:
                        density_map, _ = self.density.estimate(frame.image)
                        masks = masks or _zone_masks(self.zones, frame.image.shape[:2])
                        zone_density = {zone_id: float(density_map[mask].sum()) for zone_id, mask in masks.items()}
                    if self.homography and self.zones and i % self.flow_every == 0:
                        if grids is None:
                            grids = {z.id: zone_grid(z.polygon, frame.image.shape[:2]) for z in self.zones}
                            self.flow.roi = zones_roi([z.polygon for z in self.zones], frame.image.shape[:2])
                        flow_field = self.flow.update(frame.image, frame.ts)
                        if flow_field is not None:
                            zone_flows = {z.id: zone_flow(flow_field, self.flow.scale, grids[z.id], self.homography,
                                                          density_map, self.app.crowd["flow_moving_mps"], self.flow.origin)
                                          for z in self.zones}
                    conditions += self._zone_conditions(frame.ts, detections, crossings, zone_density, zone_flows)
                    self._fire(frame.ts, conditions)

                fps.tick()
                self.overlay.draw(
                    frame.image, detections=[] if self.health.problems else detections,
                    tracks=self.tracks if self.homography else None, zones=self.zones, metrics=self.metrics,
                    zone_areas=self.zone_areas, crossing_counts=self.tracks.crossing_counts, density_map=density_map,
                    show_heatmap=show_heatmap, fps=fps.value, demo_levels=self.demo_levels,
                    flow=flow_field if show_flow else None, flow_scale=self.flow.scale, flow_origin=self.flow.origin,
                    active=self.active,
                    zone_crossings=self.zone_crossings, health=self.health.problems,
                )
                if save_path:
                    writer = writer or _open_writer(save_path, frame.image, self._output_fps())
                    writer.write(frame.image)
                if show:
                    cv2.imshow(self.camera.name or self.camera.id, frame.image)
                    key = cv2.waitKey(1) & 0xFF
                    if key in QUIT_KEYS:
                        break
                    if key == HEATMAP_KEY:
                        show_heatmap = not show_heatmap
                    if key == FLOW_KEY:
                        show_flow = not show_flow
        finally:
            if writer is not None:
                writer.release()
            if show:
                cv2.destroyAllWindows()

    def _zone_conditions(self, ts, detections, crossings, zone_density, zone_flows) -> list:
        by_zone: dict[str, list[tuple[float, bool]]] = {}
        for c in crossings:
            zone_id = c.line_id.split(":")[0]
            by_zone.setdefault(zone_id, []).append((c.ts, c.into_zone))
            self.zone_crossings[zone_id]["in" if c.into_zone else "out"] += 1
        conditions = []
        for zone in self.zones:
            analyzer = self.analyzers.get(zone.id)
            if analyzer is None:
                continue
            inside = [d for d in detections if zone.polygon.contains(d.foot_point)]
            speeds = [self.tracks.tracks[d.track_id].speed_mps for d in inside if d.track_id in self.tracks.tracks]
            metrics = analyzer.update(ts, len(inside), zone_density.get(zone.id),
                                      statistics.median(speeds) if speeds else 0.0,
                                      zone_flows.get(zone.id, ZoneFlow()), by_zone.get(zone.id, []))
            self.metrics[zone.id] = metrics
            zone_conditions = analyzer.conditions(metrics)
            self.active[zone.id] = [c.type.value for c in zone_conditions]
            conditions += zone_conditions
        return conditions

    def _fire(self, ts: float, conditions: list) -> None:
        for event in self.engine.process(ts, conditions):
            # Day 4: snapshot → blur → db; Day 6: VLM annotation for CRITICAL
            for notifier in self.notifiers:
                notifier.send(event)

    def _output_fps(self) -> float:
        # Saved video plays at the rate frames were kept, so it runs at real speed.
        target = self.app.runtime.get("target_fps")
        return min(target, self.source.fps) if target else self.source.fps


class _FpsMeter:
    """Processing speed (wall clock) for the overlay only — never used as a timestamp."""

    def __init__(self, smoothing: float = 0.9):
        self.smoothing, self.value, self._last = smoothing, 0.0, None

    def tick(self) -> None:
        now = time.perf_counter()
        if self._last is not None:
            instant = 1.0 / max(now - self._last, 1e-6)
            self.value = instant if self.value == 0.0 else self.smoothing * self.value + (1 - self.smoothing) * instant
        self._last = now


def _zone_masks(zones: list[ZoneShape], shape: tuple[int, int]) -> dict[str, np.ndarray]:
    masks = {}
    for zone in zones:
        mask = np.zeros(shape, np.uint8)
        cv2.fillPoly(mask, [np.int32(zone.polygon.points)], 1)
        masks[zone.id] = mask.astype(bool)
    return masks


def _open_writer(path: str, image: np.ndarray, fps: float) -> cv2.VideoWriter:
    h, w = image.shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"cannot write video: {path}")
    return writer
