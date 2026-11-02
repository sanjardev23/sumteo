import cv2
import numpy as np
import pytest

from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import Line, Polygon

# A 10 m × 5 m ground rectangle seen by a high camera: the far edge (y = 0 m) looks narrower than the near edge.
WORLD = [(0, 0), (10, 0), (10, 5), (0, 5)]
IMAGE = [(500, 200), (800, 200), (1000, 500), (300, 500)]


def _to_image(world_pts):
    H_inv = cv2.getPerspectiveTransform(np.float32(WORLD), np.float32(IMAGE))
    return [tuple(p) for p in cv2.perspectiveTransform(np.float64([world_pts]), H_inv)[0]]


# --- zones -------------------------------------------------------------------------------------

def test_polygon_inside_outside_and_edge():
    square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert square.contains((5, 5))
    assert not square.contains((15, 5))
    assert square.contains((10, 5))          # on the border counts as inside


def test_concave_polygon():
    l_shape = Polygon([(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)])
    assert l_shape.contains((2, 8))
    assert not l_shape.contains((8, 8))      # the cut-out corner


def test_polygon_needs_three_points():
    with pytest.raises(ValueError):
        Polygon([(0, 0), (1, 1)])


def test_line_side_and_crossing():
    line = Line((0, 0), (10, 0))
    assert line.side((5, 3)) == -line.side((5, -3)) != 0
    assert line.side((5, 0)) == 0
    path = [(5, -2), (5, -1), (5, 1), (5, 2)]   # a person walking across once
    sides = [line.side(p) for p in path]
    assert sum(a != b for a, b in zip(sides, sides[1:])) == 1


# --- homography --------------------------------------------------------------------------------

def test_calibration_points_map_back_to_meters():
    h = Homography(IMAGE, WORLD)
    for img, world in zip(IMAGE, WORLD):
        assert h.to_world(img) == pytest.approx(world, abs=1e-6)


def test_zone_area_in_square_meters():
    h = Homography(IMAGE, WORLD)
    assert h.polygon_area_m2(IMAGE) == pytest.approx(50.0)
    inner = _to_image([(2, 1), (6, 1), (6, 3), (2, 3)])         # 4 m × 2 m inside the rectangle
    assert h.polygon_area_m2(inner) == pytest.approx(8.0)


def test_same_pixel_step_is_more_meters_far_away():
    # Why pixels can't go into thresholds: 50 px near the camera ≠ 50 px far away.
    h = Homography(IMAGE, WORLD)
    near = abs(h.to_world((650, 480))[0] - h.to_world((700, 480))[0])
    far = abs(h.to_world((650, 220))[0] - h.to_world((700, 220))[0])
    assert far > 1.5 * near


def test_homography_needs_four_points():
    with pytest.raises(ValueError):
        Homography(IMAGE[:3], WORLD[:3])
