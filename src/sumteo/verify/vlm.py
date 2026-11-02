"""Day 6 (optional) — ask a vision LLM to double-check CRITICAL snapshots.

Only annotates the event (verified + reason); it never suppresses a CRITICAL alert.
Snapshots must already be face-blurred before they are sent.
"""
from __future__ import annotations

from sumteo.events.models import Event


def verify_event(event: Event) -> tuple[bool, str]:
    # TODO(Day 6): send snapshot + question for event.type, parse yes/no + one-line reason
    raise NotImplementedError("Day 6")
