"""Days 2–3 — crowd metrics and risk level per zone."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CrowdLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"

    @property
    def label(self) -> str:
        """Korean national crisis-level name shown to operators."""
        return {"GREEN": "관심 Attention", "YELLOW": "주의 Caution", "ORANGE": "경계 Alert", "RED": "심각 Serious"}[self.value]


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


class CrowdAnalyzer:
    def __init__(self, cfg: dict, zone_area_m2: float):
        self.cfg = cfg
        self.zone_area_m2 = zone_area_m2

    def level_for(self, density_ppm2: float, turbulence: float) -> CrowdLevel:
        # TODO(Day 2): thresholds from cfg["levels_ppm2"] × zone risk factor; ORANGE + turbulence > cfg["turbulence_red"] → RED;
        #              hysteresis: leave a level only below threshold - cfg["hysteresis_ppm2"]
        raise NotImplementedError("Day 2")

    def update(self, ts, detections, density_map, flow) -> CrowdMetrics:
        # TODO(Days 2–3): hybrid count (detection vs density above switch_density_ppm2), flow stats, level
        raise NotImplementedError("Days 2-3")
