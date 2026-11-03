from dataclasses import dataclass

import pytest

from sumteo.analytics.state import TrackStore
from sumteo.geometry.calibration import Homography
from sumteo.geometry.zones import Line, Polygon, ZoneShape

FPS = 15
PX_PER_M = 100  # fake top-down camera: 1 m = 100 px
HOMOGRAPHY = Homography([(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (1, 0), (1, 1), (0, 1)])
# Zone 0–10 m × 0–10 m, entry line along y = 5 m from x = 2 m to x = 8 m.
ZONE = ZoneShape("z", Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000)]), {"z:entry": Line((200, 500), (800, 500))})


@dataclass
class FakeDetection:
    track_id: int
    foot_point: tuple[float, float]


def _store() -> TrackStore:
    return TrackStore(lost_after_s=2.0, speed_window_s=1.0, still_speed_mps=0.3, line_band_m=0.3)


def _run(store, path_m, track_id=1, homography=HOMOGRAPHY, zones=(ZONE,), t0=0.0):
    """Feed one track along `path_m` (meters, one point per frame, starting at time `t0`); return all crossings."""
    crossings = []
    for i, (x, y) in enumerate(path_m):
        det = FakeDetection(track_id, (x * PX_PER_M, y * PX_PER_M))
        crossings += store.update(t0 + i / FPS, [det], homography, list(zones))
    return crossings


def _walk(start, velocity, seconds):
    return [(start[0] + velocity[0] * i / FPS, start[1] + velocity[1] * i / FPS) for i in range(int(seconds * FPS))]


def test_walking_speed():
    store = _store()
    _run(store, _walk((3, 1), (1.2, 0), seconds=3))
    track = store.tracks[1]
    assert track.speed_mps == pytest.approx(1.2, abs=0.01)
    assert track.still_seconds == 0.0


def test_standing_with_jitter_is_still():
    store = _store()
    jitter = [(0.02, 0), (-0.02, 0.01), (0, -0.02), (0.01, 0.02)]   # ±2 cm foot-point noise
    _run(store, [(4 + jitter[i % 4][0], 2 + jitter[i % 4][1]) for i in range(3 * FPS)])
    track = store.tracks[1]
    assert track.speed_mps < 0.2
    assert track.still_seconds == pytest.approx(2.4, abs=0.1)        # still from the first full half-window


def test_time_in_zone():
    store = _store()
    _run(store, _walk((9, 3), (0.5, 0), seconds=4))                  # leaves the 10 m zone after 2 s
    assert store.tracks[1].seconds_in_zone["z"] == pytest.approx(2.0, abs=1 / FPS + 1e-9)


def test_one_walk_through_is_one_crossing_with_direction():
    store = _store()
    crossings = _run(store, _walk((5, 3), (0, 1.2), seconds=4))      # y 3 m → 7.8 m, across the line at 5 m
    assert len(crossings) == 1
    back = _run(store, _walk((5, 7.8), (0, -1.2), seconds=4), t0=4.0)        # same person walks back
    assert len(back) == 1 and back[0].direction == -crossings[0].direction
    assert store.crossing_counts["z:entry"] == {1: 1, -1: 1}


def test_jitter_on_the_line_does_not_count():
    store = _store()
    wobble = [(5, 5 + (0.2 if i % 2 else -0.2)) for i in range(3 * FPS)]   # standing on the line, ±20 cm
    assert _run(store, [(5, 3)] + wobble) == []


def test_walking_past_the_end_does_not_count():
    store = _store()
    assert _run(store, _walk((9, 3), (0, 1.2), seconds=4)) == []     # crosses y = 5 m at x = 9 m, past the 8 m end


def test_lost_track_is_dropped():
    store = _store()
    _run(store, _walk((3, 3), (1, 0), seconds=1))
    store.update(1.0 + 2.5, [], HOMOGRAPHY, [ZONE])
    assert 1 not in store.tracks


def test_without_calibration_no_speed_or_crossings_but_zone_time():
    store = _store()
    crossings = _run(store, _walk((5, 3), (0, 1.2), seconds=4), homography=None)
    assert crossings == []
    assert store.tracks[1].speed_mps == 0.0
    assert store.tracks[1].seconds_in_zone["z"] > 3.5


def test_one_frame_foot_jumps_do_not_count():
    # Walking along the line 1 m away; every 5th frame the box is occluded and the foot point jumps 1.5 m across it.
    store = _store()
    path = [(3 + 0.8 * i / FPS, 4.0 if i % 5 else 5.5) for i in range(5 * FPS)]
    assert _run(store, path) == []
