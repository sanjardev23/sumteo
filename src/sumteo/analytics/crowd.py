"""Days 2–3 — crowd metrics and risk level per zone."""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from enum import Enum

from sumteo.events.models import Condition, EventType


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
        self._samples: deque[tuple[float, float]] = deque()  # (ts, raw people/m²)

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

    def update(self, ts: float, detection_count: int, density_count: float | None,
               median_speed_mps: float = 0.0) -> CrowdMetrics:
        """`density_count` is the density map summed inside the zone (None until the model has run)."""
        use_density = density_count is not None and density_count / self.zone_area_m2 >= self.cfg["switch_density_ppm2"]
        count = density_count if use_density else float(detection_count)
        self._samples.append((ts, count / self.zone_area_m2))
        while self._samples and self._samples[0][0] < ts - self.cfg["smoothing_s"]:
            self._samples.popleft()
        density = statistics.median(v for _, v in self._samples)
        # TODO(Day 3): flow speed, turbulence, counter-flow, rise rate, inflow / outflow
        turbulence = 0.0
        return CrowdMetrics(
            zone_id=self.zone_id, ts=ts, count=count, density_ppm2=density, flow_speed=0.0,
            median_speed_mps=median_speed_mps, turbulence=turbulence, counter_flow=0.0, rise_ppm2_per_min=0.0,
            inflow_per_min=0.0, outflow_per_min=0.0, level=self.level_for(density, turbulence),
            count_source="density" if use_density else "detection",
        )

    def conditions(self, metrics: CrowdMetrics) -> list[Condition]:
        """CROWD_LEVEL while the zone is YELLOW or higher, ALL_CLEAR while it is GREEN (the engine decides what fires)."""
        details = {"level": metrics.level.value, "density_ppm2": round(metrics.density_ppm2, 2),
                   "count": round(metrics.count, 1)}
        kind = EventType.ALL_CLEAR if metrics.level is CrowdLevel.GREEN else EventType.CROWD_LEVEL
        # TODO(Day 3): STAGNATION, DENSITY_RISING, COUNTER_FLOW, INFLOW_IMBALANCE
        return [Condition(kind, zone_id=self.zone_id, details=details)]
