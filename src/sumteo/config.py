"""Load configs/default.yaml + a camera YAML, applying the camera's `overrides:`."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

Point = tuple[float, float]


class Calibration(BaseModel):
    image_points: list[Point] = []
    world_points: list[Point] = []


class ZoneRisk(BaseModel):
    slope: bool = False
    narrow: bool = False
    bottleneck: bool = False


class Zone(BaseModel):
    id: str
    polygon: list[Point] = []
    risk: ZoneRisk = ZoneRisk()
    entry_line: list[Point] = []
    exit_line: list[Point] = []


class CameraConfig(BaseModel):
    id: str
    name: str = ""
    source: str | int
    calibration: Calibration = Calibration()
    zones: list[Zone] = []


class AppConfig(BaseModel):
    """Merged settings. Sections stay plain dicts until each Day's module needs typed fields."""
    runtime: dict
    models: dict
    tracking: dict
    crowd: dict
    camera_health: dict
    events: dict
    notifiers: dict
    verify: dict
    privacy: dict
    storage: dict
    api: dict
    city_data: dict


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def save_camera_geometry(camera_path: str | Path, calibration: Calibration, zones: list[Zone]) -> None:
    """Write calibration + zones into a camera YAML (scripts/calibrate.py). Other keys, e.g. `overrides:`, are kept;
    YAML comments are not."""
    path = Path(camera_path)
    data = yaml.safe_load(path.read_text())
    data["calibration"] = calibration.model_dump(mode="json")
    data["zones"] = [zone.model_dump(mode="json") for zone in zones]
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=None, allow_unicode=True)
    path.write_text("# calibration and zones are written by scripts/calibrate.py; risk flags are edited by hand\n" + body)


def load_config(camera_path: str | Path, default_path: str | Path = "configs/default.yaml") -> tuple[AppConfig, CameraConfig]:
    default = yaml.safe_load(Path(default_path).read_text())
    camera = yaml.safe_load(Path(camera_path).read_text())
    overrides = camera.pop("overrides", None) or {}
    return AppConfig(**_deep_merge(default, overrides)), CameraConfig(**camera)
