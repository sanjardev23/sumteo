"""Day 2 — turn per-frame conditions into events: debounce, cooldown, escalation."""
from __future__ import annotations

from dataclasses import dataclass

from sumteo.events.models import DEFAULT_SEVERITY, Condition, Event, EventType, Severity

_LEVEL_SEVERITY = {"YELLOW": Severity.INFO, "ORANGE": Severity.WARNING, "RED": Severity.CRITICAL}


def severity_of(condition: Condition) -> Severity:
    level = condition.details.get("level")
    if condition.type is EventType.CROWD_LEVEL:
        return _LEVEL_SEVERITY[level]
    if condition.type is EventType.STAGNATION and level in ("ORANGE", "RED"):
        return Severity.CRITICAL
    return DEFAULT_SEVERITY[condition.type]


@dataclass
class _KeyState:
    rank: int            # severity rank the condition has right now
    rank_since: float    # when it got that rank (debounce runs per severity)
    fired_rank: int = -1 # highest rank delivered in this activation (-1 = nothing yet)


class RuleEngine:
    def __init__(self, camera_id: str, debounce_s: float, cooldown_s: float):
        self.camera_id = camera_id
        self.debounce_s = debounce_s
        self.cooldown_s = cooldown_s
        self._active: dict[tuple, _KeyState] = {}             # key → state while the condition holds
        self._last_fired: dict[tuple, tuple[float, int]] = {}  # key → (ts, severity rank); survives the condition
        self._zone_alert_rank: dict[str | None, int] = {}      # highest rank fired per zone since its last all-clear

    def process(self, ts: float, conditions: list[Condition]) -> list[Event]:
        """Key = (zone or track, type). A key fires once per activation after holding `debounce_s`; a higher severity
        fires at once, even inside the cooldown; a key that comes back within `cooldown_s` at the same or a lower
        severity is blocked. Everything that fires for one zone in one call goes out as one combined event."""
        firing: dict[str | None, list[tuple[Condition, Severity]]] = {}
        seen = set()
        for cond in conditions:
            key = (("track", cond.track_id) if cond.track_id is not None else cond.zone_id, cond.type)
            seen.add(key)
            severity = severity_of(cond)
            state = self._active.get(key)
            if state is None or state.rank != severity.rank:
                fired = state.fired_rank if state else -1
                state = self._active[key] = _KeyState(severity.rank, ts, fired)
            if ts - state.rank_since < self.debounce_s:
                continue
            if state.fired_rank > severity.rank:
                state.fired_rank = severity.rank    # quietly stepped down; a later rise alerts again
            if state.fired_rank >= severity.rank:
                continue
            if self._blocked(key, severity, ts, state):
                continue
            if cond.type is EventType.ALL_CLEAR and self._zone_alert_rank.get(cond.zone_id, -1) < Severity.WARNING.rank:
                state.fired_rank = severity.rank    # zone never reached WARNING: nothing to clear
                continue
            state.fired_rank = severity.rank
            firing.setdefault(cond.zone_id, []).append((cond, severity))

        for key in [k for k in self._active if k not in seen]:
            del self._active[key]
        return [self._combine(ts, zone_id, items) for zone_id, items in firing.items()]

    def _blocked(self, key: tuple, severity: Severity, ts: float, state: _KeyState) -> bool:
        # Cooldown only applies to a fresh activation; inside one, a rise is an escalation and always fires.
        # ALL_CLEAR has no cooldown: it is already gated by the zone having alerted, and must never be swallowed.
        if key[1] is EventType.ALL_CLEAR:
            return False
        last = self._last_fired.get(key)
        if state.fired_rank == -1 and last and ts - last[0] < self.cooldown_s and severity.rank <= last[1]:
            state.fired_rank = severity.rank        # count it as delivered so it doesn't fire when the cooldown ends
            return True
        return False

    def _combine(self, ts: float, zone_id: str | None, items: list[tuple[Condition, Severity]]) -> Event:
        items.sort(key=lambda item: item[1].rank, reverse=True)
        top, severity = items[0]
        for cond, sev in items:
            key = (("track", cond.track_id) if cond.track_id is not None else cond.zone_id, cond.type)
            self._last_fired[key] = (ts, sev.rank)
        if top.type is EventType.ALL_CLEAR:
            # The zone is declared calm: a new rise is a new situation, so old cooldowns no longer apply.
            self._zone_alert_rank[zone_id] = -1
            self._last_fired = {k: v for k, v in self._last_fired.items() if k[0] != zone_id}
        else:
            self._zone_alert_rank[zone_id] = max(self._zone_alert_rank.get(zone_id, -1), severity.rank)
        details = dict(top.details)
        details["reasons"] = [cond.type.value for cond, _ in items]
        return Event(camera_id=self.camera_id, type=top.type, severity=severity, ts=ts,
                     track_id=top.track_id, zone_id=zone_id, details=details)
