"""Day 2 — turn per-frame conditions into events: debounce, cooldown, escalation."""
from __future__ import annotations

from sumteo.events.models import Event


class RuleEngine:
    def __init__(self, camera_id: str, debounce_s: float, cooldown_s: float):
        self.camera_id = camera_id
        self.debounce_s = debounce_s
        self.cooldown_s = cooldown_s
        self._active_since: dict[tuple, float] = {}   # key → first ts the condition was true
        self._last_fired: dict[tuple, tuple[float, int]] = {}  # key → (ts, severity rank)

    def process(self, ts: float, conditions: list) -> list[Event]:
        # TODO(Day 2):
        #  - key = (track_id or zone_id, type)
        #  - fire only after the condition holds debounce_s
        #  - don't refire same key within cooldown_s, unless severity is higher (escalation)
        #  - forget keys whose condition stopped
        raise NotImplementedError("Day 2")
