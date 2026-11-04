"""Day 5 — in-platform alerts: push events to dashboard users by role over the WebSocket.

Roles: `security` (on-site guards) and `admin` (control room). Which role gets which severity comes
from config `notifiers.routes`; a CRITICAL not acknowledged within `ack_timeout_s` is re-sent to admin.
Each camera runs in its own process (ARCHITECTURE §3): this notifier hands the event to the API process, which
routes it to the roles and pushes it over the WebSocket.
"""
from __future__ import annotations

import queue as queue_errors

from sumteo.events.models import Event

ROLES = ("security", "admin")
_STALL_LOG_S = 5.0


def put_reliably(queue, message: dict) -> None:
    """Events and state are never dropped. If the API stops reading, the camera stalls here — say so loudly instead of
    freezing in silence (camera health can't see it: the frame loop itself is waiting)."""
    while True:
        try:
            queue.put(message, timeout=_STALL_LOG_S)
            return
        except queue_errors.Full:
            print(f"\033[31mAPI not reading this camera's queue for {_STALL_LOG_S:.0f} s; "
                  f"holding a {message['kind']} message\033[0m", flush=True)


def event_dict(event: Event) -> dict:
    return {
        "id": event.id, "camera_id": event.camera_id, "type": event.type.value, "severity": event.severity.value,
        "ts": event.ts, "zone_id": event.zone_id, "track_id": event.track_id, "details": event.details,
        "snapshot_path": event.snapshot_path, "acknowledged": event.acknowledged,
        "acknowledged_by": event.acknowledged_by, "acknowledged_ts": event.acknowledged_ts, "created_at": event.created_at,
        "replay": event.replay,
    }


def roles_for(routes: dict[str, list[str]], severity: str) -> set[str]:
    """Dashboard roles in a severity's route (`console` / `kakao` are other notifiers)."""
    return {r for r in routes.get(severity, []) if r in ROLES}


class PlatformNotifier:
    def __init__(self, queue):
        self.queue = queue   # multiprocessing queue read by the API process

    def send(self, event: Event) -> None:
        put_reliably(self.queue, {"kind": "event", "event": event_dict(event)})
