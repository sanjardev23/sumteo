"""Day 5 — no CRITICAL goes unanswered: one not acknowledged within `ack_timeout_s` is re-sent to admin, once.

Acknowledgement is human time, so this runs on the wall clock (injectable for tests), not on video timestamps.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable


class AckTracker:
    def __init__(self, timeout_s: float, clock: Callable[[], float] = time.monotonic):
        self.timeout_s = timeout_s
        self.clock = clock
        self._pending: dict[str, float] = {}   # event id → when it was sent
        self._lock = threading.Lock()          # queue readers track, the API loop acks and polls

    def track(self, event_id: str, severity: str, acknowledged: bool = False) -> None:
        if severity == "CRITICAL" and not acknowledged:
            with self._lock:
                self._pending[event_id] = self.clock()

    def ack(self, event_id: str) -> None:
        with self._lock:
            self._pending.pop(event_id, None)

    def due(self) -> list[str]:
        """Ids of CRITICAL events past the timeout without an acknowledgement; each is returned once."""
        now = self.clock()
        with self._lock:
            late = [eid for eid, sent in self._pending.items() if now - sent >= self.timeout_s]
            for eid in late:
                del self._pending[eid]
            return late
