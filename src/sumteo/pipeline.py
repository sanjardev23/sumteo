"""Per-camera processing loop. Grows day by day; see docs/PLAN.md."""
from __future__ import annotations

import time

import cv2
import numpy as np

from sumteo.analytics.state import TrackStore
from sumteo.config import AppConfig, CameraConfig
from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import ZoneShape
from sumteo.perception.detector import Detection, PersonTracker
from sumteo.video.source import VideoSource

QUIT_KEYS = (ord("q"), 27)  # q / Esc
ZONE_COLOR, LINE_COLOR = (0, 200, 0), (255, 160, 0)


class Pipeline:
    def __init__(self, app: AppConfig, camera: CameraConfig):
        self.app = app
        self.camera = camera
        runtime, models = app.runtime, app.models
        self.source = VideoSource(camera.source, target_fps=runtime.get("target_fps"))
        self.tracker = PersonTracker(
            models["detector"], models["detector_imgsz"], models["detector_conf"], models["tracker"], runtime["device"],
        )
        calibration = camera.calibration
        self.homography = (Homography(calibration.image_points, calibration.world_points)
                           if len(calibration.image_points) == 4 else None)
        self.zones = [ZoneShape.from_config(z) for z in camera.zones if len(z.polygon) >= 3]
        self.zone_areas = {z.id: self.homography.polygon_area_m2(z.polygon.points) if self.homography else None
                           for z in self.zones}
        tracking = app.tracking
        self.tracks = TrackStore(tracking["lost_after_s"], tracking["speed_window_s"], tracking["still_speed_mps"],
                                 tracking["line_band_m"])
        # Day 2: DensityEstimator, CrowdAnalyzer, self.engine = RuleEngine(...), console notifier
        # Day 3: FlowEstimator, flow rules, camera health
        # Day 4: db, blur
        # Day 5: platform notifier → API

    def run(self) -> None:
        show = self.app.runtime.get("show_window", True)
        save_path = self.app.runtime.get("save_path")
        writer: cv2.VideoWriter | None = None
        fps = _FpsMeter()
        try:
            for frame in self.source.frames():
                detections = self.tracker.update(frame.image)
                self.tracks.update(frame.ts, detections, self.homography, self.zones)
                # Day 2+: conditions = analyzer.update(...); for event in engine.process(frame.ts, conditions): ...
                fps.tick()
                _draw_zones(frame.image, self.zones, self.zone_areas, self.tracks.crossing_counts, detections)
                _draw_detections(frame.image, detections, self.tracks if self.homography else None)
                _draw_status(frame.image, fps.value, len(detections))
                if save_path:
                    writer = writer or _open_writer(save_path, frame.image, self._output_fps())
                    writer.write(frame.image)
                if show:
                    cv2.imshow(self.camera.name or self.camera.id, frame.image)
                    if cv2.waitKey(1) & 0xFF in QUIT_KEYS:
                        break
        finally:
            if writer is not None:
                writer.release()
            if show:
                cv2.destroyAllWindows()

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


def _open_writer(path: str, image: np.ndarray, fps: float) -> cv2.VideoWriter:
    h, w = image.shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"cannot write video: {path}")
    return writer


def _track_color(track_id: int) -> tuple[int, int, int]:
    # Stable per-ID color, so an ID switch is visible as a color change.
    rng = np.random.default_rng(track_id)
    return tuple(int(c) for c in rng.integers(64, 256, size=3))


def _draw_detections(image: np.ndarray, detections: list[Detection], tracks: TrackStore | None) -> None:
    """Box + ID per person; with a calibration also the walking speed in m/s."""
    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox)
        color = _track_color(d.track_id)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = str(d.track_id)
        if tracks is not None and d.track_id in tracks.tracks:
            label += f" {tracks.tracks[d.track_id].speed_mps:.1f}"
        cv2.putText(image, label, (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def _draw_zones(image: np.ndarray, zones: list[ZoneShape], areas: dict[str, float | None],
                crossing_counts: dict[str, dict[int, int]], detections: list[Detection]) -> None:
    """Zone outlines with area and people inside; counting lines with crossings per direction."""
    for zone in zones:
        pts = np.int32(zone.polygon.points)
        cv2.polylines(image, [pts], True, ZONE_COLOR, 2, cv2.LINE_AA)
        inside = sum(zone.polygon.contains(d.foot_point) for d in detections)
        area = areas.get(zone.id)
        text = f"{zone.id}  {inside} people" + (f"  {area:.0f} m2" if area else "")
        x, y = pts.min(axis=0)
        _text_box(image, text, (int(x), int(y) - 8), ZONE_COLOR)
        for line_id, line in zone.lines.items():
            a, b = tuple(map(int, line.a)), tuple(map(int, line.b))
            cv2.line(image, a, b, LINE_COLOR, 3, cv2.LINE_AA)
            counts = crossing_counts.get(line_id, {1: 0, -1: 0})
            _text_box(image, f"{line_id.split(':')[1]}  +{counts[1]} / -{counts[-1]}", (b[0] - 150, b[1] - 10), LINE_COLOR)


def _text_box(image: np.ndarray, text: str, origin: tuple[int, int], color) -> None:
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    x, y = max(origin[0], 0), max(origin[1], h + 4)
    cv2.rectangle(image, (x - 3, y - h - 5), (x + w + 3, y + 4), (0, 0, 0), -1)
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)


def _draw_status(image: np.ndarray, fps: float, people: int) -> None:
    text = f"FPS {fps:4.1f}  people {people}"
    cv2.rectangle(image, (0, 0), (230, 28), (0, 0, 0), -1)
    cv2.putText(image, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
