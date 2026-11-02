from pathlib import Path

from sumteo.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_camera_overrides_merge_into_defaults():
    app, camera = load_config(ROOT / "configs/cameras/crowd_demo.yaml", ROOT / "configs/default.yaml")
    assert camera.id == "crowd-demo-1"
    assert app.crowd["levels_ppm2"]["yellow"] == 1.0    # overridden by the demo camera
    assert app.crowd["switch_density_ppm2"] == 2.5      # kept from defaults
