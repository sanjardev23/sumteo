"""Day 4 — SQLite storage for events and per-second crowd metrics."""
from __future__ import annotations

import sqlite3

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
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn
