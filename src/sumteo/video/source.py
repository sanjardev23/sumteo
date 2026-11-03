"""Days 1, 3 — video input: file, webcam index or RTSP URL; live feeds reconnect (Day 3)."""
from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Frame:
    image: np.ndarray | None   # BGR; None = placeholder while a live feed is lost (camera health)
    ts: float           # seconds since start (from frame index for files → reproducible)
    index: int


class VideoSource:
    def __init__(self, source: str | int, target_fps: float | None = None, reconnect_attempts: int = 0,
                 reconnect_wait_s: float = 1.0):
        if isinstance(source, str) and source.isdigit():
            source = int(source)            # "0" on the command line = webcam 0
        self.source = source
        self.target_fps = target_fps
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_wait_s = reconnect_wait_s
        self.is_file = isinstance(source, str) and Path(source).is_file()
        self.fps: float = 0.0               # native fps, known once frames() opens the source

    def frames(self) -> Iterator[Frame]:
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video source: {self.source!r}")
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        try:
            if self.is_file:
                yield from self._file_frames(cap)
            else:
                yield from self._live_frames(cap)
        finally:
            cap.release()

    def _file_frames(self, cap: cv2.VideoCapture) -> Iterator[Frame]:
        # Keep frame i when it starts a new 1/target_fps slot; grab() skips without decoding.
        keep_every = self.fps / self.target_fps if self.target_fps and self.target_fps < self.fps else 1.0
        next_keep, index = 0.0, 0
        while True:
            if index + 1e-9 < next_keep:
                if not cap.grab():
                    return
                index += 1
                continue
            ok, image = cap.read()
            if not ok:
                return
            yield Frame(image=image, ts=index / self.fps, index=index)
            next_keep += keep_every
            index += 1

    def _live_frames(self, cap: cv2.VideoCapture) -> Iterator[Frame]:
        # Live feeds have no reproducible clock; use wall time and drop frames we can't keep up with.
        # A failed read is retried by reopening; after `reconnect_attempts` failures a placeholder frame
        # (image None) goes out per attempt, so camera health can report "lost" while we keep trying.
        min_gap = 1.0 / self.target_fps if self.target_fps else 0.0
        start, last_ts, index, failures = time.monotonic(), -1e9, 0, 0
        while True:
            ok, image = cap.read()
            if not ok:
                failures += 1
                if failures > self.reconnect_attempts:
                    yield Frame(image=None, ts=time.monotonic() - start, index=index)
                time.sleep(self.reconnect_wait_s)
                cap.release()
                cap.open(self.source)
                continue
            failures = 0
            ts = time.monotonic() - start
            if ts - last_ts >= min_gap:
                last_ts = ts
                yield Frame(image=image, ts=ts, index=index)
            index += 1
