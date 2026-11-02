"""Per-camera processing loop. Grows day by day; see docs/PLAN.md."""
from __future__ import annotations

from sumteo.config import AppConfig, CameraConfig


class Pipeline:
    def __init__(self, app: AppConfig, camera: CameraConfig):
        self.app = app
        self.camera = camera
        # Day 1: self.source = VideoSource(...); self.tracker = PersonTracker(...);
        #        self.homography, self.zones, self.tracks = TrackStore(...)
        # Day 2: DensityEstimator, CrowdAnalyzer, self.engine = RuleEngine(...), console notifier
        # Day 3: FlowEstimator, flow rules, camera health
        # Day 4: db, blur
        # Day 5: platform notifier → API

    def run(self) -> None:
        # for frame in source.frames():
        #     detections = tracker.update(frame.image)
        #     tracks.update(frame.ts, detections, homography, zone)
        #     conditions = analyzer.update(...)
        #     for event in engine.process(frame.ts, conditions):
        #         snapshot → blur → (VLM if CRITICAL) → db → notifiers
        #     draw overlays → show / stream
        raise NotImplementedError("Day 1")
