"""Day 1 — per-track history: speed (m/s), still time, time per zone, line crossings."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from sumteo.geometry.zones import Line

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


@dataclass
class Crossing:
    ts: float
    line_id: str
    track_id: int
    direction: int  # the side the track moved to: +1 / -1


class TrackStore:
    def __init__(self, lost_after_s: float, speed_window_s: float, still_speed_mps: float, line_band_m: float):
        self.lost_after_s = lost_after_s
        self.speed_window_s = speed_window_s
        self.still_speed_mps = still_speed_mps
        self.line_band_m = line_band_m
        self.tracks: dict[int, TrackState] = {}
        self.crossing_counts: dict[str, dict[int, int]] = {}  # line id → {+1: n, -1: n}

    def update(self, ts: float, detections, homography, zones: list) -> list[Crossing]:
        """Returns the line crossings that happened in this frame. Without a homography there are no meters,
        so speeds stay 0 and lines are not counted; zone timers still work in pixels."""
        world_lines = {
            line_id: Line(homography.to_world(line.a), homography.to_world(line.b))
            for zone in zones for line_id, line in zone.lines.items()
        } if homography else {}
        crossings: list[Crossing] = []
        for det in detections:
            foot_px = det.foot_point
            foot_m = homography.to_world(foot_px) if homography else None
            track = self.tracks.get(det.track_id)
            if track is None:
                track = self.tracks[det.track_id] = TrackState(det.track_id, first_seen=ts, last_seen=ts)
            dt = ts - track.last_seen
            track.last_seen = ts
            track.history.append((ts, foot_px, foot_m))

            speed = self._speed(track, ts)
            if speed is not None:
                track.speed_mps = speed
                track.still_seconds = track.still_seconds + dt if speed < self.still_speed_mps else 0.0
            for zone in zones:
                if zone.polygon.contains(foot_px):
                    track.seconds_in_zone[zone.id] = track.seconds_in_zone.get(zone.id, 0.0) + dt
            position = self._median_position(track, ts) if world_lines else None
            if position is not None:
                crossings += self._crossings(ts, track, position, world_lines)

        for track_id in [tid for tid, t in self.tracks.items() if ts - t.last_seen > self.lost_after_s]:
            del self.tracks[track_id]
        return crossings

    def _window(self, track: TrackState, ts: float) -> list[tuple[float, Point]] | None:
        """(ts, foot_m) samples of the last speed window, or None while there is too little history (under half
        a window) to tell walking from foot-point noise."""
        window = [(t, m) for t, _, m in track.history if m is not None and t >= ts - self.speed_window_s]
        if not window or window[-1][0] - window[0][0] < self.speed_window_s / 2:
            return None
        return window

    def _speed(self, track: TrackState, ts: float) -> float | None:
        # Net displacement over the window: foot-point jitter cancels out instead of adding up.
        window = self._window(track, ts)
        if window is None:
            return None
        (t0, p0), (t1, p1) = window[0], window[-1]
        return math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / (t1 - t0)

    def _median_position(self, track: TrackState, ts: float) -> Point | None:
        # When a person is half-hidden their box shrinks and the foot point jumps up to ~1.5 m for a frame;
        # the median over the speed window ignores those jumps (a real crossing is counted ~half a window late).
        window = self._window(track, ts)
        if window is None:
            return None
        xs, ys = sorted(m[0] for _, m in window), sorted(m[1] for _, m in window)
        return (xs[len(xs) // 2], ys[len(ys) // 2])

    def _crossings(self, ts: float, track: TrackState, foot_m: Point, world_lines: dict[str, Line]) -> list[Crossing]:
        found = []
        for line_id, line in world_lines.items():
            if line.distance(foot_m) < self.line_band_m:
                continue  # too close to the line to trust the side; keep the last one
            side = line.side(foot_m)
            previous = track.last_side.get(line_id)
            track.last_side[line_id] = side
            if previous is not None and side != previous and line.within_ends(foot_m):
                found.append(Crossing(ts, line_id, track.track_id, side))
                counts = self.crossing_counts.setdefault(line_id, {1: 0, -1: 0})
                counts[side] += 1
        return found
