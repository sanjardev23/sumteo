"""Day 4 — SQLite storage for events and per-second crowd metrics."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    ts REAL NOT NULL,
    track_id INTEGER,
    zone_id TEXT,
    details TEXT,              -- JSON
    snapshot_path TEXT,
    verified INTEGER,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT,
    acknowledged_ts REAL
);
CREATE TABLE IF NOT EXISTS crowd_metrics (
    camera_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    ts REAL NOT NULL,
    count REAL, density_ppm2 REAL, flow_speed REAL, median_speed_mps REAL, turbulence REAL, counter_flow REAL,
    rise_ppm2_per_min REAL, inflow_per_min REAL, outflow_per_min REAL, level TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_camera_ts ON events(camera_id, ts);
CREATE INDEX IF NOT EXISTS idx_metrics_camera_ts ON crowd_metrics(camera_id, ts);
"""


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn


class Storage:
    def __init__(self, path: str):
        self.conn = connect(path)

    def add_event(self, event) -> None:
        self.conn.execute(
            "INSERT INTO events (id, camera_id, type, severity, ts, track_id, zone_id, details, snapshot_path, verified,"
            " acknowledged, acknowledged_by, acknowledged_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event.id, event.camera_id, event.type.value, event.severity.value, event.ts, event.track_id, event.zone_id,
             json.dumps(event.details, ensure_ascii=False), event.snapshot_path,
             None if event.verified is None else int(event.verified), int(event.acknowledged), event.acknowledged_by,
             event.acknowledged_ts),
        )
        self.conn.commit()

    def add_metrics(self, camera_id: str, metrics) -> None:
        """One row per zone; the pipeline calls this once per second."""
        self.conn.executemany(
            "INSERT INTO crowd_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(camera_id, m.zone_id, m.ts, m.count, m.density_ppm2, m.flow_speed, m.median_speed_mps, m.turbulence,
              m.counter_flow, m.rise_ppm2_per_min, m.inflow_per_min, m.outflow_per_min, m.level.value) for m in metrics],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
