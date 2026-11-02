"""Day 1 — per-track history: speed (m/s), still time, time per zone, line crossings."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


Point = tuple[float, float]


@dataclass
class TrackState:
    track_id: int
    history: deque = field(default_factory=lambda: deque(maxlen=300))  # (ts, foot_px, foot_m)
    first_seen: float = 0.0
    last_seen: float = 0.0
    speed_mps: float = 0.0
    still_seconds: float = 0.0
    seconds_in_zone: dict[str, float] = field(default_factory=dict)  # zone id → seconds inside it
    last_side: dict[str, int] = field(default_factory=dict)          # line id ("<zone>:entry" / "<zone>:exit") → last Line.side()


class TrackStore:
    def __init__(self, lost_after_s: float, speed_window_s: float, still_speed_mps: float):
        self.lost_after_s = lost_after_s
        self.speed_window_s = speed_window_s
        self.still_speed_mps = still_speed_mps
        self.tracks: dict[int, TrackState] = {}

    def update(self, ts: float, detections, homography, zones: list) -> None:
        # TODO(Day 1): append positions, recompute speed over window, still timer, per-zone timers,
        #              entry/exit crossings per zone, drop lost tracks
        raise NotImplementedError("Day 1")
