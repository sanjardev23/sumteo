"""Per-camera processing loop. Grows day by day; see docs/PLAN.md."""
from __future__ import annotations

import time

import cv2
import numpy as np

from sumteo.config import AppConfig, CameraConfig
from sumteo.perception.detector import Detection, PersonTracker
from sumteo.video.source import VideoSource

QUIT_KEYS = (ord("q"), 27)  # q / Esc


class Pipeline:
    def __init__(self, app: AppConfig, camera: CameraConfig):
        self.app = app
        self.camera = camera
        runtime, models = app.runtime, app.models
        self.source = VideoSource(camera.source, target_fps=runtime.get("target_fps"))
        self.tracker = PersonTracker(
            models["detector"], models["detector_imgsz"], models["detector_conf"], models["tracker"], runtime["device"],
        )
        # Day 1: self.homography, self.zones, self.tracks = TrackStore(...)
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
                # TODO(Day 1): tracks.update(frame.ts, detections, homography, zones)
                # Day 2+: conditions = analyzer.update(...); for event in engine.process(frame.ts, conditions): ...
                fps.tick()
                _draw_detections(frame.image, detections)
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


def _draw_detections(image: np.ndarray, detections: list[Detection]) -> None:
    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox)
        color = _track_color(d.track_id)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, str(d.track_id), (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def _draw_status(image: np.ndarray, fps: float, people: int) -> None:
    text = f"FPS {fps:4.1f}  people {people}"
    cv2.rectangle(image, (0, 0), (230, 28), (0, 0, 0), -1)
    cv2.putText(image, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
