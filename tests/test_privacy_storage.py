import json
from pathlib import Path

import numpy as np
import pytest

from sumteo.analytics.crowd import CrowdLevel, CrowdMetrics
from sumteo.events.models import Event, EventType, Severity
from sumteo.geometry.calibration import Homography
from sumteo.privacy.blur import FaceBlur, head_sigma_px
from sumteo.storage.db import Storage

FACE_MODEL = Path(__file__).resolve().parents[1] / "models/face_detection_yunet_2023mar.onnx"
needs_model = pytest.mark.skipif(not FACE_MODEL.exists(), reason="YuNet model not downloaded (models/ is git-ignored)")


def _noise(h=200, w=300):
    return np.random.default_rng(0).integers(0, 255, (h, w, 3), dtype=np.uint8)


@needs_model
def test_head_band_of_each_person_is_blurred_and_the_rest_is_not():
    image, original = _noise(), _noise()
    FaceBlur(str(FACE_MODEL), head_fraction=0.2).apply(image, [(100, 50, 140, 150)])   # head band y 50–70
    head, legs, background = (slice(52, 68), slice(105, 135)), (slice(110, 150), slice(105, 135)), (slice(0, 30), slice(0, 60))
    assert image[head].std() < original[head].std() / 3          # noise smoothed away
    assert np.array_equal(image[legs], original[legs])
    assert np.array_equal(image[background], original[background])


@needs_model
def test_soft_zone_blur_stays_inside_the_zone():
    image, original = _noise(), _noise()
    zone = [(150, 100), (290, 100), (290, 190), (150, 190)]
    FaceBlur(str(FACE_MODEL), head_fraction=0.2).apply(image, [], [(zone, 3.0)])
    assert image[110:180, 160:280].std() < original[110:180, 160:280].std() / 3
    assert np.array_equal(image[:95], original[:95])


def test_head_sigma_follows_the_camera_scale():
    hom = Homography([(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (1, 0), (1, 1), (0, 1)])   # 100 px/m
    assert head_sigma_px(hom, [(0, 0), (200, 0), (200, 200), (0, 200)], 0.25) == pytest.approx(12.5)


def test_events_and_metrics_are_stored(tmp_path):
    store = Storage(str(tmp_path / "db" / "safety.db"))
    event = Event("cam", EventType.CROWD_LEVEL, Severity.WARNING, 12.5, zone_id="z",
                  details={"level": "ORANGE", "reasons": ["CROWD_LEVEL"]}, snapshot_path="data/snapshots/x.jpg")
    store.add_event(event)
    m = CrowdMetrics("z", 13.0, 450.0, 4.5, 0.6, 0.7, 0.2, 0.1, 0.5, 12.0, 6.0, CrowdLevel.ORANGE)
    store.add_metrics("cam", [m])
    row = store.conn.execute("SELECT type, severity, zone_id, details, snapshot_path, acknowledged FROM events").fetchone()
    assert row[:3] == ("CROWD_LEVEL", "WARNING", "z") and json.loads(row[3])["level"] == "ORANGE"
    assert row[4] == "data/snapshots/x.jpg" and row[5] == 0
    assert store.conn.execute("SELECT zone_id, density_ppm2, level FROM crowd_metrics").fetchall() == [("z", 4.5, "ORANGE")]


def test_open_alerts_are_the_unacknowledged_ones_since_a_time(tmp_path):
    store = Storage(str(tmp_path / "safety.db"))
    old = Event("cam", EventType.CROWD_LEVEL, Severity.CRITICAL, 1.0, zone_id="z", created_at=100.0)
    open_ = Event("cam", EventType.CROWD_LEVEL, Severity.CRITICAL, 2.0, zone_id="z", created_at=200.0)
    acked = Event("cam", EventType.STAGNATION, Severity.WARNING, 3.0, zone_id="z", created_at=210.0)
    info = Event("cam", EventType.CROWD_LEVEL, Severity.INFO, 4.0, zone_id="z", created_at=220.0)
    for e in (old, open_, acked, info):
        store.add_event(e)
    store.acknowledge(acked.id, "security", 230.0)
    assert [e["id"] for e in store.open_alerts({"WARNING", "CRITICAL"}, since=150.0)] == [open_.id]
