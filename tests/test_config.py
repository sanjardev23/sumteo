from pathlib import Path

from sumteo.config import Calibration, Zone, ZoneRisk, load_config, save_camera_geometry

ROOT = Path(__file__).resolve().parents[1]


def test_camera_overrides_merge_into_defaults():
    app, camera = load_config(ROOT / "configs/cameras/crowd_demo.yaml", ROOT / "configs/default.yaml")
    assert camera.id == "crowd-demo-1"
    assert app.crowd["levels_ppm2"]["yellow"] == 1.0    # overridden by the demo camera
    assert app.crowd["switch_density_ppm2"] == 2.5      # kept from defaults


def test_calibration_is_saved_and_reloaded(tmp_path):
    camera_path = tmp_path / "cam.yaml"
    camera_path.write_text((ROOT / "configs/cameras/crowd_demo.yaml").read_text())
    zone = Zone(id="main", polygon=[(10, 10), (200, 10), (200, 100)], risk=ZoneRisk(narrow=True),
                entry_line=[(10, 50), (200, 50)])
    save_camera_geometry(camera_path, Calibration(image_points=[(0, 0), (1, 0), (1, 1), (0, 1)],
                                                  world_points=[(0, 0), (3, 0), (3, 6), (0, 6)]), [zone])

    app, camera = load_config(camera_path, ROOT / "configs/default.yaml")
    assert camera.calibration.world_points[2] == (3, 6)
    assert camera.zones[0].polygon == zone.polygon and camera.zones[0].risk.narrow
    assert camera.zones[0].exit_line == []
    assert app.crowd["levels_ppm2"]["yellow"] == 1.0    # demo overrides survive the rewrite
