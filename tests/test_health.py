from pathlib import Path

import numpy as np
import yaml

from sumteo.events.engine import RuleEngine
from sumteo.video.health import CameraHealth
from sumteo.video.source import Frame

DEFAULT = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs/default.yaml").read_text())
CFG, EVENTS = DEFAULT["camera_health"], DEFAULT["events"]
FPS = 10
RNG = np.random.default_rng(0)


def _live():
    return RNG.integers(60, 200, (90, 160, 3), dtype=np.uint8)            # a new image every frame


def _feed(health, images, t0=0.0):
    """Returns (problems per frame, all conditions)."""
    problems, conditions = [], []
    for i, image in enumerate(images):
        conditions.append(health.update(Frame(image=image, ts=t0 + i / FPS, index=i)))
        problems.append(list(health.problems))
    return problems, conditions


def test_a_live_scene_is_healthy():
    problems, conditions = _feed(CameraHealth(CFG), [_live() for _ in range(5 * FPS)])
    assert all(p == [] for p in problems) and all(c == [] for c in conditions)


def test_a_frozen_feed_is_reported_after_frozen_seconds():
    still = _live()
    problems, _ = _feed(CameraHealth(CFG), [still] * ((CFG["frozen_seconds"] + 1) * FPS))
    first = next(i for i, p in enumerate(problems) if p)
    assert problems[first] == ["frozen"] and first / FPS >= CFG["frozen_seconds"]


def test_a_covered_lens_is_dark_at_once():
    dark = [np.full((90, 160, 3), 5, np.uint8) + RNG.integers(0, 3, (90, 160, 3), dtype=np.uint8) for _ in range(FPS)]
    problems, conditions = _feed(CameraHealth(CFG), dark)
    assert problems[0] == ["dark"] and conditions[0][0].details == {"problems": ["dark"]}


def test_a_lost_feed_is_reported_and_recovery_clears_it():
    health = CameraHealth(CFG)
    problems, _ = _feed(health, [None, None, _live(), _live()])
    assert problems == [["lost"], ["lost"], [], []]


def test_freeze_then_darkness_is_one_event():
    # Pausing the source, then covering the lens: one condition key all along → exactly one CAMERA_HEALTH event.
    health, engine = CameraHealth(CFG), RuleEngine("cam", EVENTS["debounce_s"], EVENTS["cooldown_s"])
    still, black = _live(), np.zeros((90, 160, 3), np.uint8)
    images = [_live() for _ in range(2 * FPS)] + [still] * (8 * FPS) + [black] * (4 * FPS) + [_live() for _ in range(FPS)]
    events = []
    for i, image in enumerate(images):
        events += engine.process(i / FPS, health.update(Frame(image=image, ts=i / FPS, index=i)))
    assert len(events) == 1 and events[0].details["problems"] == ["frozen"]
