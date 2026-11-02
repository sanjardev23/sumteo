"""Day 5 — in-platform alerts: push events to dashboard users by role over the WebSocket.

Roles: `security` (on-site guards) and `admin` (control room). Which role gets which severity comes
from config `notifiers.routes`; a CRITICAL not acknowledged within `ack_timeout_s` is re-sent to admin.
"""
from __future__ import annotations

from sumteo.events.models import Event


class PlatformNotifier:
    def __init__(self, role: str):
        self.role = role

    def send(self, event: Event) -> None:
        # TODO(Day 5): publish {role, event} to the in-memory pub/sub that feeds WS /ws?role=
        raise NotImplementedError("Day 5")
