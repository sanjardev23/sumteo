"""Day 6 — replay mode (ARCHITECTURE §2.11): pacing, stale-config refusal, replayed events on the live platform path."""
import hashlib
import json
import queue
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from sumteo.api.replay import Replay, StaleRecording, load_recording
from sumteo.api.server import camera_state
from sumteo.config import config_hash, load_config
from sumteo.events.escalation import AckTracker
from sumteo.storage.db import Storage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "configs/default.yaml"
CAMERA = ROOT / "configs/cameras/crowd_demo.yaml"


class FakeTime:
    """Clock that only moves when the replay sleeps."""

    def __init__(self):
        self.now = 100.0

    def clock(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s


def _recording(tmp_path: Path, hash_: str | None = None) -> Path:
    rec = tmp_path / "rec"
    (rec / "snapshots").mkdir(parents=True)
    writer = cv2.VideoWriter(str(rec / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 2, (64, 48))
    for i in range(3):
        writer.write(np.full((48, 64, 3), 40 * i, np.uint8))
    writer.release()
    cv2.imwrite(str(rec / "snapshots/abc.jpg"), np.zeros((48, 64, 3), np.uint8))
    app, camera = load_config(CAMERA, DEFAULT)
    zone = {"id": "main", "level": "RED", "density_ppm2": 5.2, "count": 40.0, "speed_mps": 0.2}
    entries = [
        {"kind": "frame", "ts": 0.0}, {"kind": "state", "ts": 0.0, "camera": {"id": camera.id, "mode": "live", "zones": [zone]}},
        {"kind": "frame", "ts": 0.5},
        {"kind": "event", "ts": 0.5, "event": {"id": "abc", "camera_id": camera.id, "type": "CROWD_LEVEL", "severity": "CRITICAL",
                                             "ts": 0.5, "zone_id": "main", "track_id": None, "details": {"level": "RED"},
                                             "snapshot_path": "snapshots/abc.jpg", "acknowledged": False, "created_at": 1.0}},
        {"kind": "frame", "ts": 1.0},
    ]
    (rec / "timeline.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    manifest = {"camera_id": camera.id, "camera_config": str(CAMERA), "config_hash": hash_ or config_hash(app, camera),
                "git_commit": "0123456789", "device": "cuda", "fps": 2.0, "frames": 3, "events": 1, "duration_s": 1.0}
    (rec / "manifest.json").write_text(json.dumps(manifest))
    return rec


def _drain(q: queue.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_config_hash_ignores_where_a_run_happens_but_not_what_it_computes():
    app, camera = load_config(CAMERA, DEFAULT)
    base = config_hash(app, camera)
    app.runtime["device"] = "cuda"
    app.events["snapshot_dir"] = "/content/snapshots"
    assert config_hash(app, camera) == base                      # Colab recording still matches the Mac
    app.crowd["levels_ppm2"] = {**app.crowd["levels_ppm2"], "red": 9.9}
    assert config_hash(app, camera) != base


def test_stale_recording_refuses_to_start(tmp_path):
    rec = _recording(tmp_path, hash_="0" * 64)
    with pytest.raises(StaleRecording, match="stale, re-record"):
        load_recording(rec, DEFAULT)
    assert load_recording(_recording(tmp_path / "ok"), DEFAULT)["camera_id"] == "crowd-demo-1"


def test_different_file_at_the_same_path_makes_the_recording_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("weights.pt").write_bytes(b"colab weights")
    rec = _recording(tmp_path / "r")
    manifest = json.loads((rec / "manifest.json").read_text())
    manifest["inputs"] = {"weights.pt": hashlib.sha256(b"colab weights").hexdigest(), "not_here.pth": "0" * 64}
    (rec / "manifest.json").write_text(json.dumps(manifest))
    assert load_recording(rec, DEFAULT)                          # same file; a file missing here is skipped (Docker)
    Path("weights.pt").write_bytes(b"mac weights")
    with pytest.raises(StaleRecording, match="different file at weights.pt"):
        load_recording(rec, DEFAULT)


def test_replay_is_paced_by_the_wall_clock(tmp_path):
    fake, out = FakeTime(), queue.Queue()
    sent = []
    replay = Replay(_recording(tmp_path), out, None, tmp_path / "snaps", clock=fake.clock, sleep=fake.sleep)
    original = replay._send
    replay._send = lambda entry, ts, video: (sent.append((entry["kind"], ts, fake.now - 100.0)), original(entry, ts, video))
    replay.run(loops=1)
    assert [k for k, _, _ in sent] == ["frame", "state", "frame", "event", "frame"]
    assert all(at >= ts - 1e-9 for _, ts, at in sent)            # nothing goes out before its video time
    assert sent[-1][2] == pytest.approx(1.0)                      # real speed: 1 s of video took 1 s
    assert sum(m["kind"] == "frame" for m in _drain(out)) == 3


def test_replayed_events_are_new_tagged_rows_that_ack_and_escalate_like_live_ones(tmp_path):
    fake, out, storage = FakeTime(), queue.Queue(), Storage(str(tmp_path / "db.sqlite"))
    Replay(_recording(tmp_path), out, storage, tmp_path / "snaps", clock=fake.clock, sleep=fake.sleep).run(loops=2)
    msgs = _drain(out)
    events = [m["event"] for m in msgs if m["kind"] == "event"]
    states = [m["camera"] for m in msgs if m["kind"] == "state"]
    assert len(events) == 2 and all(e["replay"] for e in events)
    assert len({e["id"] for e in events} | {"abc"}) == 3         # each loop re-emits with a new id
    assert events[1]["ts"] == pytest.approx(0.5 + 1.0 + 0.5)      # the video clock keeps counting: period = 1 s + 1 frame
    assert all(s["mode"] == "replay" for s in states)
    stored = storage.event(events[0]["id"])
    assert stored["replay"] is True and Path(stored["snapshot_path"]).exists()
    assert storage.metrics("crowd-demo-1")[0]["level"] == "RED"   # the density chart gets replayed rows
    assert storage.acknowledge(events[0]["id"], "admin", 1.0)["acknowledged"] is True
    tracker = AckTracker(timeout_s=0)
    for e in events:
        tracker.track(e["id"], e["severity"], e["acknowledged"])
    assert set(tracker.due()) == {e["id"] for e in events}


def test_live_camera_state_says_live():
    camera = SimpleNamespace(id="cam", name="Cam", location=None)
    pipeline = SimpleNamespace(zones=[], metrics={}, analyzers={}, zone_areas={}, active={}, camera=camera,
                               health=SimpleNamespace(problems=set()), demo_levels=None)
    assert camera_state(pipeline)["mode"] == "live"


def test_old_database_gets_the_replay_column(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, type TEXT NOT NULL, severity TEXT "
                 "NOT NULL, ts REAL NOT NULL, track_id INTEGER, zone_id TEXT, details TEXT, snapshot_path TEXT, verified "
                 "INTEGER, acknowledged INTEGER NOT NULL DEFAULT 0, acknowledged_by TEXT, acknowledged_ts REAL, created_at REAL)")
    conn.execute("INSERT INTO events (id, camera_id, type, severity, ts, created_at) VALUES ('old', 'c', 'CROWD_LEVEL', "
                 "'INFO', 1.0, 1.0)")
    conn.commit()
    conn.close()
    assert Storage(str(path)).event("old")["replay"] is False     # old rows count as live
