from pathlib import Path

import yaml

from sumteo.events.engine import RuleEngine
from sumteo.events.models import Condition, EventType, Severity

EVENTS = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/default.yaml").read_text())["events"]
DEBOUNCE, COOLDOWN = EVENTS["debounce_s"], EVENTS["cooldown_s"]
STEP = 0.1  # 10 updates per second


def _engine() -> RuleEngine:
    return RuleEngine("cam", debounce_s=DEBOUNCE, cooldown_s=COOLDOWN)


def _level(level: str, zone: str = "z") -> Condition:
    if level == "GREEN":
        return Condition(EventType.ALL_CLEAR, zone_id=zone, details={"level": level})
    return Condition(EventType.CROWD_LEVEL, zone_id=zone, details={"level": level})


def _run(engine, t0, seconds, conditions):
    """Feed the same conditions every STEP for `seconds`; return (events, end time)."""
    events, n = [], round(seconds / STEP)
    for i in range(n):
        events += engine.process(t0 + i * STEP, list(conditions))
    return events, t0 + n * STEP


def test_severity_rank_orders_escalation():
    assert Severity.INFO.rank < Severity.WARNING.rank < Severity.CRITICAL.rank


def test_flicker_shorter_than_debounce_does_not_fire():
    engine, t, events = _engine(), 0.0, []
    for _ in range(5):                                   # ORANGE for 0.5 s, then gone, five times
        e, t = _run(engine, t, DEBOUNCE / 2, [_level("ORANGE")]); events += e
        e, t = _run(engine, t, 0.3, []); events += e
    assert events == []


def test_condition_fires_once_after_debounce():
    events, _ = _run(_engine(), 0.0, 30, [_level("ORANGE")])
    assert len(events) == 1
    assert events[0].severity is Severity.WARNING and events[0].ts >= DEBOUNCE


def test_cooldown_blocks_repeats():
    engine = _engine()
    first, t = _run(engine, 0.0, 3, [_level("YELLOW")])
    _, t = _run(engine, t, 2, [])                        # condition stops briefly...
    again, t = _run(engine, t, 3, [_level("YELLOW")])    # ...and comes back inside the cooldown
    assert len(first) == 1 and again == []
    _, t = _run(engine, t, COOLDOWN, [])
    after, _ = _run(engine, t, 3, [_level("YELLOW")])    # after the cooldown it alerts again
    assert len(after) == 1


def test_escalation_fires_even_inside_cooldown():
    engine = _engine()
    events, t = _run(engine, 0.0, 3, [_level("YELLOW")])
    for level in ("ORANGE", "RED"):
        e, t = _run(engine, t, 3, [_level(level)]); events += e
    assert [e.severity for e in events] == [Severity.INFO, Severity.WARNING, Severity.CRITICAL]


def test_stepping_down_is_silent_but_rising_again_alerts():
    engine, events, t = _engine(), [], 0.0
    for level in ("ORANGE", "YELLOW", "ORANGE"):          # one activation of CROWD_LEVEL, never GREEN
        e, t = _run(engine, t, 5, [_level(level)])
        events += e
    assert [(e.details["level"], e.severity) for e in events] == [("ORANGE", Severity.WARNING), ("ORANGE", Severity.WARNING)]


def test_conditions_at_the_same_moment_are_one_combined_event():
    both = [_level("RED"), Condition(EventType.STAGNATION, zone_id="z", details={"level": "RED"})]
    events, _ = _run(_engine(), 0.0, 3, both)
    assert len(events) == 1
    assert events[0].severity is Severity.CRITICAL
    assert set(events[0].details["reasons"]) == {"CROWD_LEVEL", "STAGNATION"}


def test_zones_are_independent():
    events, _ = _run(_engine(), 0.0, 3, [_level("ORANGE", "a"), _level("YELLOW", "b")])
    assert sorted((e.zone_id, e.severity) for e in events) == [("a", Severity.WARNING), ("b", Severity.INFO)]


def test_one_all_clear_after_a_warning():
    engine = _engine()
    _, t = _run(engine, 0.0, 3, [_level("ORANGE")])
    clear, t = _run(engine, t, 30, [_level("GREEN")])
    assert [(e.type, e.severity) for e in clear] == [(EventType.ALL_CLEAR, Severity.INFO)]


def test_no_all_clear_when_the_zone_only_reached_info():
    engine = _engine()
    _, t = _run(engine, 0.0, 3, [_level("YELLOW")])
    clear, _ = _run(engine, t, 30, [_level("GREEN")])
    assert clear == []


def test_after_an_all_clear_a_new_rise_alerts_and_clears_again():
    engine, events, t = _engine(), [], 0.0
    for level in ("ORANGE", "GREEN", "ORANGE", "GREEN"):     # all within one cooldown
        e, t = _run(engine, t, 5, [_level(level)]); events += e
    assert [e.type for e in events] == [EventType.CROWD_LEVEL, EventType.ALL_CLEAR] * 2
