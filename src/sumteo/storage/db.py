"""Days 4–5 — SQLite storage for events and per-second crowd metrics; Day 5: queries and acknowledgements.
Day 6: a `replay` column on both tables marks rows re-emitted from a recorded run (§2.11)."""
from __future__ import annotations

import json
import sqlite3
import time
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
    acknowledged_ts REAL,
    created_at REAL,           -- wall clock (epoch s); ts is the video clock
    replay INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS crowd_metrics (
    camera_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    ts REAL NOT NULL,
    count REAL, density_ppm2 REAL, flow_speed REAL, median_speed_mps REAL, turbulence REAL, counter_flow REAL,
    rise_ppm2_per_min REAL, inflow_per_min REAL, outflow_per_min REAL, level TEXT,
    wall_ts REAL,              -- wall clock (epoch s)
    replay INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_camera_ts ON events(camera_id, ts);
CREATE INDEX IF NOT EXISTS idx_metrics_camera_ts ON crowd_metrics(camera_id, ts);
"""


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    for table in ("events", "crowd_metrics"):   # databases from before Day 6 get the column, old rows count as live
        if "replay" not in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN replay INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    return conn


class Storage:
    def __init__(self, path: str):
        self.conn = connect(path)

    def add_event(self, event) -> None:
        self.conn.execute(
            "INSERT INTO events (id, camera_id, type, severity, ts, track_id, zone_id, details, snapshot_path, verified,"
            " acknowledged, acknowledged_by, acknowledged_ts, created_at, replay)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event.id, event.camera_id, event.type.value, event.severity.value, event.ts, event.track_id, event.zone_id,
             json.dumps(event.details, ensure_ascii=False), event.snapshot_path,
             None if event.verified is None else int(event.verified), int(event.acknowledged), event.acknowledged_by,
             event.acknowledged_ts, event.created_at, int(event.replay)),
        )
        self.conn.commit()

    def add_metrics(self, camera_id: str, metrics) -> None:
        """One row per zone; the pipeline calls this once per second."""
        now = time.time()
        self.conn.executemany(
            "INSERT INTO crowd_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            [(camera_id, m.zone_id, m.ts, m.count, m.density_ppm2, m.flow_speed, m.median_speed_mps, m.turbulence,
              m.counter_flow, m.rise_ppm2_per_min, m.inflow_per_min, m.outflow_per_min, m.level.value, now)
             for m in metrics],
        )
        self.conn.commit()

    def add_replayed_zones(self, camera_id: str, ts: float, zones: list[dict]) -> None:
        """Replay (§2.11): one row per zone of a recorded camera state, so the density chart works; marked replay."""
        now = time.time()
        self.conn.executemany(
            "INSERT INTO crowd_metrics (camera_id, zone_id, ts, count, density_ppm2, median_speed_mps, level, wall_ts,"
            " replay) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            [(camera_id, z["id"], ts, z["count"], z["density_ppm2"], z["speed_mps"], z["level"], now)
             for z in zones if z.get("level")],
        )
        self.conn.commit()

    def acknowledge(self, event_id: str, role: str, at: float) -> dict | None:
        """Store who acknowledged and when (first acknowledgement wins). Returns the event, None if unknown."""
        self.conn.execute("UPDATE events SET acknowledged = 1, acknowledged_by = ?, acknowledged_ts = ? "
                          "WHERE id = ? AND acknowledged = 0", (role, at, event_id))
        self.conn.commit()
        return self.event(event_id)

    def mark_escalated(self, event_id: str, at: float) -> None:
        row = self.event(event_id)
        if row:
            details = {**row["details"], "escalated": "no response", "escalated_at": at}
            self.conn.execute("UPDATE events SET details = ? WHERE id = ?", (json.dumps(details, ensure_ascii=False), event_id))
            self.conn.commit()

    def event(self, event_id: str) -> dict | None:
        rows = self._events("WHERE id = ?", (event_id,))
        return rows[0] if rows else None

    def events(self, camera: str | None = None, severity: str | None = None, limit: int = 200) -> list[dict]:
        where, args = [], []
        if camera:
            where.append("camera_id = ?"); args.append(camera)
        if severity:
            where.append("severity = ?"); args.append(severity)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return self._events(f"{clause} ORDER BY created_at DESC LIMIT ?", (*args, limit))

    def open_alerts(self, severities: set[str], since: float) -> list[dict]:
        """Unacknowledged events of these severities created since a wall-clock time, newest first."""
        marks = ", ".join("?" * len(severities))
        return self._events(f"WHERE acknowledged = 0 AND severity IN ({marks}) AND created_at >= ? ORDER BY created_at DESC",
                            (*severities, since)) if severities else []

    def metrics(self, camera: str, since: float = 0.0) -> list[dict]:
        """Rows of one camera since a wall-clock time (epoch s), oldest first."""
        cur = self.conn.execute("SELECT zone_id, ts, wall_ts, count, density_ppm2, level FROM crowd_metrics "
                                "WHERE camera_id = ? AND wall_ts >= ? ORDER BY wall_ts", (camera, since))
        return [dict(zip(("zone_id", "ts", "wall_ts", "count", "density_ppm2", "level"), r)) for r in cur.fetchall()]

    def _events(self, clause: str, args: tuple) -> list[dict]:
        cols = ("id", "camera_id", "type", "severity", "ts", "track_id", "zone_id", "details", "snapshot_path",
                "verified", "acknowledged", "acknowledged_by", "acknowledged_ts", "created_at", "replay")
        cur = self.conn.execute(f"SELECT {', '.join(cols)} FROM events {clause}", args)
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        for row in rows:
            row["details"] = json.loads(row["details"] or "{}")
            row["acknowledged"] = bool(row["acknowledged"])
            row["replay"] = bool(row["replay"])
        return rows

    def close(self) -> None:
        self.conn.close()
