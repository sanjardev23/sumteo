"""Event data model shared by analyzers, rule engine, storage, API and notifiers."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return ["INFO", "WARNING", "CRITICAL"].index(self.value)


class EventType(str, Enum):
    CROWD_LEVEL = "CROWD_LEVEL"
    STAGNATION = "STAGNATION"
    DENSITY_RISING = "DENSITY_RISING"
    COUNTER_FLOW = "COUNTER_FLOW"
    INFLOW_IMBALANCE = "INFLOW_IMBALANCE"
    CAMERA_HEALTH = "CAMERA_HEALTH"
    ALL_CLEAR = "ALL_CLEAR"


DEFAULT_SEVERITY = {
    EventType.STAGNATION: Severity.WARNING,       # CRITICAL when the level is ORANGE or RED
    EventType.DENSITY_RISING: Severity.WARNING,
    EventType.COUNTER_FLOW: Severity.WARNING,
    EventType.INFLOW_IMBALANCE: Severity.WARNING,
    EventType.CAMERA_HEALTH: Severity.WARNING,
    EventType.ALL_CLEAR: Severity.INFO,
    # CROWD_LEVEL severity depends on the level: YELLOW→INFO, ORANGE→WARNING, RED→CRITICAL
}


@dataclass
class Condition:
    """A rule that is true right now for a zone (or track); the RuleEngine decides if it becomes an Event."""
    type: EventType
    zone_id: str | None = None
    track_id: int | None = None
    details: dict = field(default_factory=dict)


@dataclass
class Event:
    camera_id: str
    type: EventType
    severity: Severity
    ts: float
    track_id: int | None = None
    zone_id: str | None = None
    details: dict = field(default_factory=dict)
    snapshot_path: str | None = None
    verified: bool | None = None        # VLM check result (Day 6), None = not checked
    acknowledged: bool = False
    acknowledged_by: str | None = None  # role that acknowledged: security / admin
    acknowledged_ts: float | None = None
    # `ts` is the video clock (reproducible rules); people and the dashboard need wall time.
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
