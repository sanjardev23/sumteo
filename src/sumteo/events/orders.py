"""Day 6 — orders, control room → guards (ARCHITECTURE §2.8): a fixed bilingual instruction tied to a camera.

Only admin sends; only security moves the status, forward only: sent → on_my_way → done. Orders are human actions:
never recorded, replayed or used for measured numbers. The texts themselves live in dashboard/lib/i18n.ts.
"""
from __future__ import annotations

TEXT_KEYS = ("go_to_camera", "redirect_exit", "stop_entry", "open_lane", "clear_blockage")
STATUSES = ("sent", "on_my_way", "done")
NOTE_MAX = 140
SENDER_ROLE = "admin"
STATUS_ROLE = "security"


def is_forward(current: str, new: str) -> bool:
    return new in STATUSES and STATUSES.index(new) > STATUSES.index(current)
