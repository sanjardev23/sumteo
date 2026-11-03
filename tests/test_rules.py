"""Day 3 rules (ARCHITECTURE §2.6) on fake metric sequences: each fires when it should and stays quiet when it shouldn't."""
from pathlib import Path

import pytest
import yaml

from sumteo.analytics.crowd import CrowdAnalyzer, CrowdLevel
from sumteo.events.engine import RuleEngine, severity_of
from sumteo.events.models import EventType, Severity
from sumteo.perception.flow import ZoneFlow

DEFAULT = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/default.yaml").read_text())
CFG, EVENTS = DEFAULT["crowd"], DEFAULT["events"]
AREA = 100.0   # m², so a count of 300 = 3.0 people/m² (YELLOW, above the 2.5 switch → density count)
STEP = 0.5     # two updates per second


def _feed(analyzer, seconds, t0=0.0, count=300.0, speed=1.0, flow=None, crossings_at=lambda t: []):
    """Same zone state every STEP for `seconds`; returns (all metrics, condition types per update)."""
    out, types = [], []
    for i in range(round(seconds / STEP)):
        t = t0 + i * STEP
        m = analyzer.update(t, detection_count=int(count), density_count=count, median_speed_mps=speed,
                            flow=flow or ZoneFlow(speed_mps=speed), crossings=crossings_at(t))
        out.append(m)
        types.append({c.type for c in analyzer.conditions(m)})
    return out, types


def _analyzer():
    return CrowdAnalyzer(CFG, "z", zone_area_m2=AREA)


# --- STAGNATION ----------------------------------------------------------------------------------------------------

def test_dense_and_stuck_for_long_enough_is_stagnation():
    _, types = _feed(_analyzer(), CFG["stagnation_seconds"] + 2, speed=0.05)
    assert EventType.STAGNATION not in types[0]
    assert EventType.STAGNATION in types[-1]


def test_dense_but_moving_is_not_stagnation():
    _, types = _feed(_analyzer(), CFG["stagnation_seconds"] * 2, speed=1.0)
    assert all(EventType.STAGNATION not in t for t in types)


def test_stuck_but_sparse_is_not_stagnation():
    _, types = _feed(_analyzer(), CFG["stagnation_seconds"] * 2, count=50.0, speed=0.0)   # 0.5 /m², GREEN
    assert all(EventType.STAGNATION not in t for t in types)


def test_moving_again_resets_the_stagnation_timer():
    # Flow speed is a median over smoothing_s, so "moving again" means for longer than one smoothing window.
    analyzer, stuck, moving = _analyzer(), CFG["stagnation_seconds"] - 2, CFG["smoothing_s"] + 1
    _feed(analyzer, stuck, speed=0.05)
    _feed(analyzer, moving, t0=stuck, speed=1.0)
    _, types = _feed(analyzer, stuck, t0=stuck + moving, speed=0.05)
    assert all(EventType.STAGNATION not in t for t in types)


def test_stagnation_is_critical_from_orange():
    analyzer = _analyzer()
    _, _ = _feed(analyzer, CFG["stagnation_seconds"] + 2, count=450.0, speed=0.05)     # 4.5 /m², ORANGE
    m = analyzer.update(40.0, 450, 450.0, 0.05, ZoneFlow(speed_mps=0.05))
    stagnation = [c for c in analyzer.conditions(m) if c.type is EventType.STAGNATION][0]
    assert m.level is CrowdLevel.ORANGE and severity_of(stagnation) is Severity.CRITICAL


def test_zone_speed_follows_the_count_source():
    analyzer = _analyzer()
    sparse = analyzer.update(0.0, 50, 50.0, median_speed_mps=0.1, flow=ZoneFlow(speed_mps=1.3))
    assert sparse.count_source == "detection" and sparse.speed_mps == 0.1               # tracks
    dense = _analyzer().update(0.0, 50, 300.0, median_speed_mps=0.0, flow=ZoneFlow(speed_mps=1.3))
    assert dense.count_source == "density" and dense.speed_mps == 1.3                  # flow: tracks are too few


def test_stagnation_timer_runs_across_a_count_source_switch():
    # Density hovering at the switch: the speed source flips every update, but both say "stuck".
    analyzer, types = _analyzer(), []
    for i in range(round((CFG["stagnation_seconds"] + 2) / STEP)):
        count = 260.0 if i % 2 else 240.0                                                # 2.6 ↔ 2.4 /m², YELLOW
        m = analyzer.update(i * STEP, int(count), count, median_speed_mps=0.05, flow=ZoneFlow(speed_mps=0.1))
        types.append({c.type for c in analyzer.conditions(m)})
    assert EventType.STAGNATION in types[-1]


# --- DENSITY_RISING ------------------------------------------------------------------------------------------------

def _ramp(analyzer, start, per_min, seconds):
    types = []
    for i in range(round(seconds / STEP)):
        t = i * STEP
        count = (start + per_min * t / 60) * AREA
        m = analyzer.update(t, int(count), count, 1.0, ZoneFlow(speed_mps=1.0))
        types.append({c.type for c in analyzer.conditions(m)})
    return m, types


def test_fast_rise_is_density_rising():
    m, types = _ramp(_analyzer(), start=2.0, per_min=2 * CFG["rise_ppm2_per_min"], seconds=30)
    assert m.rise_ppm2_per_min == pytest.approx(2 * CFG["rise_ppm2_per_min"], rel=0.1)
    assert EventType.DENSITY_RISING in types[-1]


def test_slow_rise_or_low_density_is_not_density_rising():
    _, slow = _ramp(_analyzer(), start=2.0, per_min=CFG["rise_ppm2_per_min"] / 2, seconds=30)
    _, sparse = _ramp(_analyzer(), start=0.2, per_min=2 * CFG["rise_ppm2_per_min"], seconds=30)  # stays < 2.0 /m²
    assert all(EventType.DENSITY_RISING not in t for t in slow + sparse)


def test_rise_is_zero_until_one_smoothing_window():
    m, _ = _ramp(_analyzer(), start=2.0, per_min=10.0, seconds=CFG["smoothing_s"] - 1)
    assert m.rise_ppm2_per_min == 0.0


# --- COUNTER_FLOW --------------------------------------------------------------------------------------------------

def test_counter_flow_fires_only_from_yellow():
    collide = ZoneFlow(speed_mps=1.0, turbulence=0.5, counter_flow=CFG["counter_flow_warn"] + 0.1)
    _, dense = _feed(_analyzer(), 3, flow=collide)
    _, sparse = _feed(_analyzer(), 3, count=50.0, flow=collide)
    assert EventType.COUNTER_FLOW in dense[-1]
    assert all(EventType.COUNTER_FLOW not in t for t in sparse)


def test_one_stream_is_not_counter_flow():
    _, types = _feed(_analyzer(), 3, flow=ZoneFlow(speed_mps=1.0, counter_flow=0.05))
    assert all(EventType.COUNTER_FLOW not in t for t in types)


def test_turbulent_orange_zone_is_red():
    m, _ = _feed(_analyzer(), 3, count=450.0, flow=ZoneFlow(speed_mps=1.0, turbulence=CFG["turbulence_red"] + 0.1))
    assert m[-1].level is CrowdLevel.RED


# --- INFLOW_IMBALANCE ----------------------------------------------------------------------------------------------

def _crossings(in_per_min, out_per_min):
    """A crossings_at(t) feeding the given rates (one update = STEP seconds)."""
    def at(t):
        n_in = int((t + STEP) * in_per_min / 60) - int(t * in_per_min / 60)
        n_out = int((t + STEP) * out_per_min / 60) - int(t * out_per_min / 60)
        return [(t, True)] * n_in + [(t, False)] * n_out
    return at


def test_filling_zone_is_inflow_imbalance():
    m, types = _feed(_analyzer(), 60, count=50.0, crossings_at=_crossings(40, 10))
    assert m[-1].inflow_per_min == pytest.approx(40, abs=1) and m[-1].outflow_per_min == pytest.approx(10, abs=1)
    assert EventType.INFLOW_IMBALANCE in types[-1]


def test_balanced_or_light_traffic_is_not_inflow_imbalance():
    _, balanced = _feed(_analyzer(), 60, count=50.0, crossings_at=_crossings(40, 30))
    _, light = _feed(_analyzer(), 60, count=50.0, crossings_at=_crossings(CFG["inflow_min_per_min"] - 10, 0))
    assert all(EventType.INFLOW_IMBALANCE not in t for t in balanced + light)


def test_inflow_rate_uses_the_full_window_at_start_up():
    m, _ = _feed(_analyzer(), 10, count=50.0, crossings_at=_crossings(60, 0))       # 10 people in the first 10 s
    assert m[-1].inflow_per_min == pytest.approx(10 * 60 / CFG["inflow_window_s"], abs=1)


# --- ALL_CLEAR and the engine --------------------------------------------------------------------------------------

def test_all_clear_only_when_green_and_nothing_else_holds():
    _, calm = _feed(_analyzer(), 3, count=50.0)
    _, filling = _feed(_analyzer(), 60, count=50.0, crossings_at=_crossings(40, 0))
    assert calm[-1] == {EventType.ALL_CLEAR}
    assert filling[-1] == {EventType.INFLOW_IMBALANCE}


def test_crowd_level_and_stagnation_go_out_as_one_critical_event():
    analyzer, engine, events = _analyzer(), RuleEngine("cam", EVENTS["debounce_s"], EVENTS["cooldown_s"]), []
    for i in range(round((CFG["stagnation_seconds"] + 3) / STEP)):
        m = analyzer.update(i * STEP, 450, 450.0, 0.05, ZoneFlow(speed_mps=0.05))     # ORANGE and stuck
        events += engine.process(i * STEP, analyzer.conditions(m))
    assert [e.severity for e in events] == [Severity.WARNING, Severity.CRITICAL]
    assert events[1].details["reasons"] == ["STAGNATION"]


def test_calm_sparse_sequence_fires_nothing_above_info():
    analyzer, engine, events = _analyzer(), RuleEngine("cam", EVENTS["debounce_s"], EVENTS["cooldown_s"]), []
    for i in range(round(120 / STEP)):
        count = 30.0 + 10 * (i % 7) / 7                                                   # 0.3–0.4 /m², walking
        m = analyzer.update(i * STEP, int(count), count, 1.1, ZoneFlow(speed_mps=1.1, turbulence=0.7, counter_flow=0.5),
                            crossings=_crossings(12, 10)(i * STEP))
        events += engine.process(i * STEP, analyzer.conditions(m))
    assert all(e.severity is Severity.INFO for e in events)


def test_one_turbulent_moment_does_not_turn_orange_red():
    analyzer, levels = _analyzer(), []
    for i in range(round(10 / STEP)):
        turbulence = CFG["turbulence_red"] + 0.2 if i == 12 else 0.1                # one spike at 6 s
        m = analyzer.update(i * STEP, 450, 450.0, 1.0, ZoneFlow(speed_mps=1.0, turbulence=turbulence))
        levels.append(m.level)
    assert CrowdLevel.RED not in levels
