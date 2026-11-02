"""Day 2 — colored console output for events."""
from __future__ import annotations

from sumteo.events.models import Event, Severity

_COLORS = {Severity.INFO: "\033[36m", Severity.WARNING: "\033[33m", Severity.CRITICAL: "\033[31m"}


class ConsoleNotifier:
    def send(self, event: Event) -> None:
        who = f"track {event.track_id}" if event.track_id is not None else f"zone {event.zone_id}"
        print(f"{_COLORS[event.severity]}[{event.ts:7.1f}s] {event.severity.value:8} {event.type.value:16} {who} {event.details}\033[0m")
