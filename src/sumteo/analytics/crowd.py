"""Days 2–3 — crowd metrics and risk level per zone."""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from enum import Enum

from sumteo.events.models import Condition, EventType
from sumteo.perception.flow import ZoneFlow


class CrowdLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"

    @property
    def label(self) -> str:
        """Korean national crisis-level name shown to operators."""
        return {"GREEN": "관심 Attention", "YELLOW": "주의 Caution", "ORANGE": "경계 Alert", "RED": "심각 Serious"}[self.value]

    @property
    def rank(self) -> int:
        return _ORDER.index(self)


_ORDER = [CrowdLevel.GREEN, CrowdLevel.YELLOW, CrowdLevel.ORANGE, CrowdLevel.RED]


@dataclass
class CrowdMetrics:
    zone_id: str
    ts: float
    count: float
    density_ppm2: float
    flow_speed: float
    median_speed_mps: float
    turbulence: float      # 0 = everyone moves the same way, 1 = chaotic
    counter_flow: float    # share of movement against the main direction
    rise_ppm2_per_min: float
    inflow_per_min: float
    outflow_per_min: float
    level: CrowdLevel
    count_source: str = "detection"  # which method gave `count`: detection / density
    stagnant_s: float = 0.0          # how long the zone has been at ≥ stagnation_min_level and slow

    @property
    def speed_mps(self) -> float:
        """The zone speed the rules use: track speed where detection counts the zone, optical flow where tracks
        are too few to trust (the density model counts it)."""
        return self.flow_speed if self.count_source == "density" else self.median_speed_mps


def risk_factor(cfg: dict, risk) -> float:
    """Product of the factors of the zone's risk flags (slope, narrow, ...), never below `risk_factor_floor`."""
    factor = 1.0
    for flag, value in cfg["risk_factors"].items():
        if getattr(risk, flag, False):
            factor *= value
    return max(factor, cfg["risk_factor_floor"])


class CrowdAnalyzer:
    """One per zone. Turns per-frame counts into smoothed people/m², a level with hysteresis, and conditions."""

    def __init__(self, cfg: dict, zone_id: str, zone_area_m2: float, risk_factor: float = 1.0):
        self.cfg = cfg
        self.zone_id = zone_id
        self.zone_area_m2 = zone_area_m2
        self.thresholds = {
            CrowdLevel.YELLOW: cfg["levels_ppm2"]["yellow"] * risk_factor,
            CrowdLevel.ORANGE: cfg["levels_ppm2"]["orange"] * risk_factor,
            CrowdLevel.RED: cfg["levels_ppm2"]["red"] * risk_factor,
        }
        self.base_level = CrowdLevel.GREEN   # density-only level; hysteresis works on this
        self._samples: deque[tuple[float, float]] = deque()   # (ts, raw people/m²)
        self._flow_samples = {name: deque() for name in ("speed", "turbulence", "counter")}  # (ts, raw value)
        self._smoothed: deque[tuple[float, float]] = deque()  # (ts, smoothed people/m²) for the rise rate
        self._crossings: deque[tuple[float, bool]] = deque()  # (ts, into_zone)
        self._slow_since: float | None = None

    def level_for(self, density_ppm2: float, turbulence: float) -> CrowdLevel:
        """Up at a threshold, down only `hysteresis_ppm2` below it. Stateful: call once per update."""
        target = CrowdLevel.GREEN
        for level in (CrowdLevel.YELLOW, CrowdLevel.ORANGE, CrowdLevel.RED):
            if density_ppm2 >= self.thresholds[level]:
                target = level
        if target.rank >= self.base_level.rank:
            self.base_level = target
        else:
            hysteresis = self.cfg["hysteresis_ppm2"]
            while self.base_level is not CrowdLevel.GREEN and density_ppm2 < self.thresholds[self.base_level] - hysteresis:
                self.base_level = _ORDER[self.base_level.rank - 1]
        if self.base_level is CrowdLevel.ORANGE and turbulence > self.cfg["turbulence_red"]:
            return CrowdLevel.RED
        return self.base_level

    def update(self, ts: float, detection_count: int, density_count: float | None, median_speed_mps: float = 0.0,
               flow: ZoneFlow | None = None, crossings: list[tuple[float, bool]] = ()) -> CrowdMetrics:
        """`density_count` is the density map summed inside the zone (None until the model has run); `flow` the
        zone's latest optical flow; `crossings` this frame's line crossings of the zone as (ts, into_zone)."""
        cfg = self.cfg
        use_density = density_count is not None and density_count / self.zone_area_m2 >= cfg["switch_density_ppm2"]
        count = density_count if use_density else float(detection_count)
        density = _push_median(self._samples, ts, count / self.zone_area_m2, cfg["smoothing_s"])
        # Flow is smoothed like density: one turbulent frame must not turn ORANGE into RED.
        flow = flow or ZoneFlow()
        window, fs = cfg["smoothing_s"], self._flow_samples
        flow_speed = _push_median(fs["speed"], ts, flow.speed_mps, window)
        turbulence = _push_median(fs["turbulence"], ts, flow.turbulence, window)
        counter_flow = _push_median(fs["counter"], ts, flow.counter_flow, window)
        level = self.level_for(density, turbulence)
        metrics = CrowdMetrics(
            zone_id=self.zone_id, ts=ts, count=count, density_ppm2=density, flow_speed=flow_speed,
            median_speed_mps=median_speed_mps, turbulence=turbulence, counter_flow=counter_flow,
            rise_ppm2_per_min=self._rise(ts, density), inflow_per_min=0.0, outflow_per_min=0.0, level=level,
            count_source="density" if use_density else "detection",
        )
        metrics.inflow_per_min, metrics.outflow_per_min = self._flows(ts, crossings)
        dense = level.rank >= CrowdLevel[cfg["stagnation_min_level"]].rank
        if dense and metrics.speed_mps < cfg["stagnation_speed_mps"]:
            self._slow_since = ts if self._slow_since is None else self._slow_since
            metrics.stagnant_s = ts - self._slow_since
        else:
            self._slow_since = None
        return metrics

    def _rise(self, ts: float, density: float) -> float:
        """Least-squares slope of the smoothed density over `rise_window_s`, per minute. 0 until the samples span one
        `smoothing_s`, so start-up noise can't look like a fast rise."""
        samples = self._smoothed
        samples.append((ts, density))
        while samples[0][0] < ts - self.cfg["rise_window_s"]:
            samples.popleft()
        if samples[-1][0] - samples[0][0] < self.cfg["smoothing_s"]:
            return 0.0
        t = [s[0] for s in samples]
        d = [s[1] for s in samples]
        return statistics.linear_regression(t, d).slope * 60

    def _flows(self, ts: float, crossings) -> tuple[float, float]:
        # Divided by the full window even at start-up, so a few early crossings aren't extrapolated to a high rate.
        window = self.cfg["inflow_window_s"]
        self._crossings.extend(crossings)
        while self._crossings and self._crossings[0][0] < ts - window:
            self._crossings.popleft()
        inflow = sum(1 for _, into in self._crossings if into)
        return inflow * 60 / window, (len(self._crossings) - inflow) * 60 / window

    def conditions(self, metrics: CrowdMetrics) -> list[Condition]:
        """Every rule of ARCHITECTURE §2.6 that holds right now; ALL_CLEAR only while GREEN with nothing else active.
        The engine decides what fires."""
        cfg, level = self.cfg, metrics.level
        details = {"level": level.value, "density_ppm2": round(metrics.density_ppm2, 2), "count": round(metrics.count, 1)}
        found = []
        if level is not CrowdLevel.GREEN:
            found.append(EventType.CROWD_LEVEL)
        if metrics.stagnant_s >= cfg["stagnation_seconds"]:
            found.append(EventType.STAGNATION)
            details["speed_mps"] = round(metrics.speed_mps, 2)
        if metrics.rise_ppm2_per_min > cfg["rise_ppm2_per_min"] and metrics.density_ppm2 >= cfg["rise_min_density"]:
            found.append(EventType.DENSITY_RISING)
            details["rise_ppm2_per_min"] = round(metrics.rise_ppm2_per_min, 2)
        if metrics.counter_flow > cfg["counter_flow_warn"] and level is not CrowdLevel.GREEN:
            found.append(EventType.COUNTER_FLOW)
            details["counter_flow"] = round(metrics.counter_flow, 2)
        inflow, outflow = metrics.inflow_per_min, metrics.outflow_per_min
        if inflow >= cfg["inflow_min_per_min"] and inflow > cfg["inflow_ratio"] * outflow:
            found.append(EventType.INFLOW_IMBALANCE)
            details.update(inflow_per_min=round(inflow, 1), outflow_per_min=round(outflow, 1))
        if not found:
            found.append(EventType.ALL_CLEAR)
        return [Condition(kind, zone_id=self.zone_id, details=details) for kind in found]


def _push_median(samples: deque, ts: float, value: float, window_s: float) -> float:
    samples.append((ts, value))
    while samples[0][0] < ts - window_s:
        samples.popleft()
    return statistics.median(v for _, v in samples)
