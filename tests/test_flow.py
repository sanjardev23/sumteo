import cv2
import numpy as np
import pytest

from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import Polygon
from sumteo.perception.flow import FlowEstimator, zone_flow, zone_grid

# Fake top-down camera: 1 m = 100 px. Flow fields are at scale 1.0, in pixels per second.
HOMOGRAPHY = Homography([(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (1, 0), (1, 1), (0, 1)])
SHAPE = (200, 400)
POINTS = zone_grid(Polygon([(0, 0), (400, 0), (400, 200), (0, 200)]), SHAPE)
MOVING = 0.3


def _field(vx, vy):
    flow = np.zeros((*SHAPE, 2), np.float32)
    flow[..., 0], flow[..., 1] = vx, vy
    return flow


def test_one_stream_is_calm():
    f = zone_flow(_field(120, 0), 1.0, POINTS, HOMOGRAPHY, None, MOVING)     # everyone walks right at 1.2 m/s
    assert f.speed_mps == pytest.approx(1.2, rel=0.01)
    assert f.turbulence == pytest.approx(0.0, abs=1e-6) and f.counter_flow == 0.0


def test_two_opposite_streams_are_counter_flow():
    flow = _field(120, 0)
    flow[:, :180, 0] = -120                                                  # left 45% walks the other way
    f = zone_flow(flow, 1.0, POINTS, HOMOGRAPHY, None, MOVING)
    assert f.counter_flow == pytest.approx(0.45, abs=0.03)
    assert f.turbulence > 0.8


def test_nothing_moving_gives_zeros():
    f = zone_flow(_field(5, 0), 1.0, POINTS, HOMOGRAPHY, None, MOVING)        # 0.05 m/s: below "moving"
    assert f.turbulence == 0.0 and f.counter_flow == 0.0 and f.speed_mps < MOVING


def test_density_weighting_ignores_empty_ground():
    flow = _field(0, 0)
    flow[:, :100, 0] = 100                                                   # only the people (left quarter) move
    density = np.zeros(SHAPE, np.float32)
    density[:, :100] = 0.01
    assert zone_flow(flow, 1.0, POINTS, HOMOGRAPHY, None, MOVING).speed_mps == pytest.approx(0.25, abs=0.02)
    assert zone_flow(flow, 1.0, POINTS, HOMOGRAPHY, density, MOVING).speed_mps == pytest.approx(1.0, rel=0.01)


def test_estimator_measures_a_shift_in_pixels_per_second():
    rng = np.random.default_rng(0)
    texture = cv2.GaussianBlur(rng.integers(0, 255, (240, 320), dtype=np.uint8), (0, 0), 3)
    image = cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR)
    shifted = np.roll(image, 4, axis=1)                                      # 4 px right in 0.1 s = 40 px/s
    estimator = FlowEstimator(scale=0.5)
    assert estimator.update(image, 0.0) is None
    flow = estimator.update(shifted, 0.1)
    assert flow.shape[:2] == (120, 160)
    assert np.median(flow[20:-20, 20:-20, 0]) == pytest.approx(40, rel=0.15)
    assert abs(np.median(flow[20:-20, 20:-20, 1])) < 4


def test_flow_on_a_roi_lines_up_with_full_frame_points():
    flow = _field(0, 0)[:100, :200]                       # roi = x 100–300, y 50–150 at scale 1
    flow[:, 100:, 0] = 120                                # the roi's right half (x ≥ 200 in the image) moves
    points = zone_grid(Polygon([(200, 60), (290, 60), (290, 140), (200, 140)]), SHAPE)
    f = zone_flow(flow, 1.0, points, HOMOGRAPHY, None, MOVING, origin=(100, 50))
    assert f.speed_mps == pytest.approx(1.2, rel=0.01)
