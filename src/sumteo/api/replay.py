"""Day 6 — replay mode (ARCHITECTURE §2.11): play a recorded run through the live platform path, loading no models.

A replay worker reads `data/recordings/<id>/` (written by scripts/record_camera.py), paces it by the wall clock at real
speed and sends the same frame / state / event messages a live camera worker sends, so the API, WebSocket, pop-ups,
acks and escalation treat it the same. Re-emitted events are new rows (new id, created_at now, replay = 1); replayed
rows are never used for measured numbers. Looping keeps the video clock counting, as for file sources.
"""
from __future__ import annotations

import hashlib
import json
import queue as queue_errors
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import cv2

from sumteo.config import AppConfig, CameraConfig, config_hash, load_config
from sumteo.events.models import Event, EventType, Severity
from sumteo.events.notifiers.platform import event_dict, put_reliably
from sumteo.storage.db import Storage

JPEG_QUALITY = 75   # same as the live stream


class StaleRecording(RuntimeError):
    """The recording was made with settings the camera no longer has; showing it would show outdated results."""


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_inputs(app: AppConfig, camera: CameraConfig) -> dict[str, str]:
    """sha256 of the files a run reads (weights, clip): the same path on Colab and the Mac must be the same file."""
    paths = [app.models["detector"], app.models["density"], camera.source]
    if app.privacy.get("blur_faces"):
        paths.append(app.models["face_detector"])
    return {str(p): file_sha256(p) for p in paths if isinstance(p, str) and Path(p).is_file()}


def load_recording(rec_dir: str | Path, default_path: str = "configs/default.yaml") -> dict:
    """The recording's manifest, after checking it still matches its camera's current config and, where the files
    exist here, the same weights and clip. A replay-only machine (Docker) has no weights: those checks are skipped."""
    rec = Path(rec_dir)
    manifest = json.loads((rec / "manifest.json").read_text())
    app, camera = load_config(manifest["camera_config"], default_path)
    if manifest["camera_id"] != camera.id or manifest["config_hash"] != config_hash(app, camera):
        raise StaleRecording(f"{rec}: recording is stale, re-record ({manifest['camera_config']} changed since "
                             f"commit {manifest['git_commit'][:8]})")
    differ = [p for p, sha in manifest.get("inputs", {}).items() if Path(p).is_file() and file_sha256(p) != sha]
    if differ:
        raise StaleRecording(f"{rec}: recording is stale, re-record (different file at {', '.join(differ)})")
    return manifest


class Replay:
    """Plays one recording into `out` (a queue). `clock` / `sleep` are injectable so pacing is testable."""

    def __init__(self, rec_dir: str | Path, out, storage: Storage | None, snapshot_dir: str | Path,
                 repeat_alerts_s: float = 0.0,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.rec = Path(rec_dir)
        self.manifest = json.loads((self.rec / "manifest.json").read_text())
        self.entries = [json.loads(line) for line in (self.rec / "timeline.jsonl").open()]
        self.out, self.storage, self.snapshot_dir = out, storage, Path(snapshot_dir)
        self.clock, self.sleep = clock, sleep
        # Repeat limit (§2.11): like the rule engine's cooldown, a (zone, type) that fired within `repeat_alerts_s` (video
        # clock, which keeps counting across loops) is held back unless it comes at a higher severity.
        self.repeat_alerts_s = repeat_alerts_s
        self._last_emitted: dict[tuple, tuple[float, int]] = {}   # (zone, type) → (ts, severity rank)
        # One loop lasts the clip plus one frame, so the next loop's first frame doesn't land on the last one.
        self.period = self.manifest["duration_s"] + 1.0 / self.manifest["fps"]

    def run(self, loops: int | None = None) -> None:
        start, loop = self.clock(), 0
        while loops is None or loop < loops:
            offset = loop * self.period
            video = cv2.VideoCapture(str(self.rec / "video.mp4"))
            try:
                for entry in self.entries:
                    ts = entry["ts"] + offset
                    wait = start + ts - self.clock()
                    if wait > 0:
                        self.sleep(wait)
                    self._send(entry, ts, video)
            finally:
                video.release()
            loop += 1

    def _send(self, entry: dict, ts: float, video: cv2.VideoCapture) -> None:
        if entry["kind"] == "frame":
            ok, image = video.read()
            if ok:
                ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                try:
                    self.out.put_nowait({"kind": "frame", "jpeg": jpeg.tobytes()})
                except queue_errors.Full:
                    pass   # like a live worker: frames may drop, state and events never
        elif entry["kind"] == "state":
            state = {**entry["camera"], "mode": "replay"}
            if self.storage:
                self.storage.add_replayed_zones(state["id"], ts, state["zones"])
            put_reliably(self.out, {"kind": "state", "camera": state})
        elif entry["kind"] == "event" and self._due(entry["event"], ts):
            put_reliably(self.out, {"kind": "event", "event": event_dict(self._reemit(entry["event"], ts))})

    def _due(self, recorded: dict, ts: float) -> bool:
        key, rank = (recorded["zone_id"], recorded["type"]), Severity(recorded["severity"]).rank
        last = self._last_emitted.get(key)
        if last and ts - last[0] < self.repeat_alerts_s and rank <= last[1]:
            return False
        self._last_emitted[key] = (ts, rank)
        return True

    def _reemit(self, recorded: dict, ts: float) -> Event:
        event = Event(camera_id=recorded["camera_id"], type=EventType(recorded["type"]),
                      severity=Severity(recorded["severity"]), ts=ts, track_id=recorded["track_id"],
                      zone_id=recorded["zone_id"], details=recorded["details"], replay=True)
        if recorded.get("snapshot_path"):
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            target = self.snapshot_dir / f"{event.id}.jpg"
            shutil.copyfile(self.rec / recorded["snapshot_path"], target)
            event.snapshot_path = str(target)
        if self.storage:
            self.storage.add_event(event)
        return event


def replay_main(rec_dir: str, default_path: str, out) -> None:
    """Entry point of a replay worker process (the API checked the recording before starting it)."""
    manifest = json.loads((Path(rec_dir) / "manifest.json").read_text())
    app, _ = load_config(manifest["camera_config"], default_path)
    Replay(rec_dir, out, Storage(app.storage["db_path"]), app.events["snapshot_dir"],
           repeat_alerts_s=app.replay.get("repeat_alerts_s", 0.0)).run()
