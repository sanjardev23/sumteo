from pathlib import Path

import pytest
import yaml

from sumteo.analytics.crowd import CrowdAnalyzer, CrowdLevel, risk_factor
from sumteo.config import ZoneRisk

CFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/default.yaml").read_text())["crowd"]
G, Y, O, R = CrowdLevel.GREEN, CrowdLevel.YELLOW, CrowdLevel.ORANGE, CrowdLevel.RED


def _levels(densities, factor=1.0, turbulence=0.0):
    analyzer = CrowdAnalyzer(CFG, "z", zone_area_m2=100.0, risk_factor=factor)
    return [analyzer.level_for(d, turbulence) for d in densities]


def test_level_edges():
    # default thresholds: yellow 2, orange 4, red 5 people/m²
    assert _levels([1.99]) == [G]
    assert _levels([2.0]) == [Y]
    assert _levels([4.0]) == [O]
    assert _levels([5.0]) == [R]


def test_risk_factors_lower_thresholds_with_a_floor():
    steep_narrow = risk_factor(CFG, ZoneRisk(slope=True, narrow=True))
    assert steep_narrow == pytest.approx(0.85 * 0.9)
    assert _levels([3.8], factor=steep_narrow) == [O] and _levels([3.83], factor=steep_narrow) == [R]
    everything = risk_factor(CFG, ZoneRisk(slope=True, narrow=True, bottleneck=True))
    assert everything == CFG["risk_factor_floor"]                   # 0.85 × 0.9 × 0.9 = 0.69 → floored at 0.7
    assert risk_factor(CFG, ZoneRisk()) == 1.0


def test_hysteresis_stops_flipping_at_a_threshold():
    assert _levels([4.05, 3.95, 4.05, 3.95, 3.7]) == [O, O, O, O, O]   # 3.95 ↔ 4.05 doesn't flip
    assert _levels([4.05, 3.59]) == [O, Y]                              # leaves ORANGE only under 4.0 - 0.4
    assert _levels([5.2, 1.0]) == [R, G]                                # a big drop goes down several levels


def test_turbulence_turns_orange_red_without_moving_the_base_level():
    analyzer = CrowdAnalyzer(CFG, "z", zone_area_m2=100.0)
    assert analyzer.level_for(4.2, turbulence=CFG["turbulence_red"] + 0.1) is R
    assert analyzer.base_level is O
    assert analyzer.level_for(4.2, turbulence=0.0) is O


def test_hybrid_count_switches_to_density_only_when_dense():
    analyzer = CrowdAnalyzer(CFG, "z", zone_area_m2=100.0)
    assert analyzer.update(0.0, detection_count=40, density_count=None).count_source == "detection"
    sparse = analyzer.update(0.1, detection_count=40, density_count=60.0)   # density says 0.6 /m², below the switch
    assert (sparse.count, sparse.count_source) == (40, "detection")
    dense = analyzer.update(0.2, detection_count=90, density_count=300.0)   # 3.0 /m²: detection is saturating
    assert (dense.count, dense.count_source) == (300.0, "density")


def test_density_is_median_over_the_smoothing_window():
    analyzer = CrowdAnalyzer(CFG, "z", zone_area_m2=10.0)
    for i in range(20):
        metrics = analyzer.update(i * 0.25, detection_count=10, density_count=None)   # 1.0 /m²
    spike = analyzer.update(5.0, detection_count=60, density_count=None)              # one bad frame: 6.0 /m²
    assert spike.density_ppm2 == pytest.approx(1.0) and spike.level is G
    later = [analyzer.update(5.0 + i * 0.25, detection_count=30, density_count=None) for i in range(1, 30)]
    assert later[-1].density_ppm2 == pytest.approx(3.0)                              # old samples age out
    assert metrics.zone_id == "z"
