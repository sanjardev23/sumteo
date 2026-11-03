"""Day 1 — interactive calibration on the first frame of a camera's source.

    python scripts/calibrate.py --camera configs/cameras/crowd_demo.yaml

Steps: click 4 ground points → type their real-world coords (meters) → for each zone: click its
polygon (Enter to close), then optionally its entry line and exit line (2 clicks each, Enter to skip)
→ next zone or finish. Writes calibration / zones (polygon, entry_line, exit_line) back into the
camera YAML (ARCHITECTURE §2.4). Zone risk flags are edited by hand in the YAML.

Keys in the window: left click = add point, Backspace = undo last point, Enter = done, Esc = quit without saving.
After the 4 ground points a 1 m grid is drawn on the floor: if it doesn't follow the floor, press r and redo.
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

from sumteo.config import Calibration, Zone, ZoneRisk, load_config, save_camera_geometry
from sumteo.geometry.calibration import Homography
from sumteo.video.source import VideoSource

WINDOW = "calibrate"
ENTER, BACKSPACE, ESC = {10, 13, 3}, {8, 127}, 27
GROUND, ZONE, ENTRY, EXIT, GRID = (0, 255, 255), (0, 200, 0), (255, 160, 0), (60, 60, 255), (255, 255, 255)

Point = tuple[float, float]


class Clicker:
    """Collects mouse clicks on top of a base image until Enter. A magnifier shows the area under the cursor."""

    def __init__(self, base: np.ndarray):
        self.base = base
        self.points: list[Point] = []
        self.max_points: int | None = None
        self.cursor: tuple[int, int] | None = None
        cv2.setMouseCallback(WINDOW, self._on_mouse)

    def _on_mouse(self, event, x, y, *_):
        self.cursor = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN and (self.max_points is None or len(self.points) < self.max_points):
            self.points.append((x, y))

    def collect(self, prompt: str, color, min_points: int, max_points: int | None = None,
                closed: bool = False, optional: bool = False) -> list[Point]:
        """Enter finishes once `min_points` are clicked; with `optional`, Enter on no points skips (returns [])."""
        self.points, self.max_points = [], max_points
        print(f"  → {prompt}")
        while True:
            canvas = self.base.copy()
            _draw_shape(canvas, self.points, color, closed=closed and len(self.points) >= 3)
            _banner(canvas, prompt)
            if self.cursor:
                _magnifier(canvas, self.base, self.cursor)
            cv2.imshow(WINDOW, canvas)
            key = cv2.waitKey(20) & 0xFF
            if key == ESC:
                sys.exit("aborted — nothing saved")
            if key in BACKSPACE and self.points:
                self.points.pop()
            if key in ENTER:
                if len(self.points) >= min_points or (optional and not self.points):
                    return [(float(x), float(y)) for x, y in self.points]
                print(f"    need {min_points} points, have {len(self.points)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", required=True)
    args = parser.parse_args()

    _, camera = load_config(args.camera)
    frame = next(VideoSource(camera.source).frames()).image
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    h_px, w_px = frame.shape[:2]
    scale = min(1.0, 1600 / w_px)
    cv2.resizeWindow(WINDOW, int(w_px * scale), int(h_px * scale))

    base = frame.copy()
    clicker = Clicker(base)

    print("\n1) Ground calibration")
    while True:
        image_points = clicker.collect(
            "Click 4 ground points in order (e.g. far-left, far-right, near-right, near-left), then Enter",
            GROUND, min_points=4, max_points=4, closed=True,
        )
        world_points = _ask_world_points()
        homography = Homography(image_points, world_points)
        check = base.copy()
        _draw_grid(check, homography, world_points)
        _draw_shape(check, image_points, GROUND, closed=True)
        if _confirm(check, "1 m grid drawn on the floor. Enter = looks right, r = redo"):
            break
    _draw_shape(base, image_points, GROUND, closed=True)

    print("\n2) Zones")
    old = {z.id: z for z in camera.zones}
    defaults = [z.id for z in camera.zones]
    zones: list[Zone] = []
    while True:
        default_id = defaults[len(zones)] if len(zones) < len(defaults) else f"zone{len(zones) + 1}"
        zone_id = input(f"Zone id [{default_id}]: ").strip() or default_id
        polygon = clicker.collect(f"Zone '{zone_id}': click its corners on the ground, Enter to close",
                                  ZONE, min_points=3, closed=True)
        area = homography.polygon_area_m2(polygon)
        print(f"    area: {area:.1f} m²")
        _draw_shape(base, polygon, ZONE, closed=True)
        _label(base, polygon, f"{zone_id}  {area:.0f} m2", ZONE)

        entry = clicker.collect(f"'{zone_id}' ENTRY line: 2 clicks + Enter, or Enter to skip",
                                ENTRY, min_points=2, max_points=2, optional=True)
        _draw_shape(base, entry, ENTRY)
        exit_ = clicker.collect(f"'{zone_id}' EXIT line: 2 clicks + Enter, or Enter to skip",
                                EXIT, min_points=2, max_points=2, optional=True)
        _draw_shape(base, exit_, EXIT)

        risk = old[zone_id].risk if zone_id in old else ZoneRisk()
        zones.append(Zone(id=zone_id, polygon=polygon, risk=risk, entry_line=entry, exit_line=exit_))
        if input("Another zone? [y/N]: ").strip().lower() != "y":
            break

    cv2.destroyAllWindows()
    save_camera_geometry(args.camera, Calibration(image_points=image_points, world_points=world_points), zones)
    print(f"\nSaved to {args.camera}:")
    for z in zones:
        print(f"  {z.id}: {homography.polygon_area_m2(z.polygon):.1f} m², "
              f"entry line {'yes' if z.entry_line else 'no'}, exit line {'yes' if z.exit_line else 'no'}")


def _ask_world_points() -> list[Point]:
    while True:
        raw = input("Rectangle 'width depth' in meters (point 1→2 = width, 2→3 = depth), or Enter to type each point: ")
        try:
            if raw.strip():
                w, d = map(float, raw.split())
                return [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)]
            return [tuple(map(float, input(f"  point {i + 1} 'x y' (m): ").split())) for i in range(4)]
        except ValueError:
            print("    could not read that — use numbers like: 6 12")


def _confirm(canvas: np.ndarray, prompt: str) -> bool:
    print(f"  → {prompt}")
    _banner(canvas, prompt)
    while True:
        cv2.imshow(WINDOW, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key == ESC:
            sys.exit("aborted — nothing saved")
        if key in ENTER:
            return True
        if key == ord("r"):
            return False


def _draw_grid(canvas: np.ndarray, homography: Homography, world_points: list[Point]) -> None:
    # Project 1 m world lines back into the image; they should follow the floor's perspective.
    to_image = np.linalg.inv(homography.H)
    xs, ys = [p[0] for p in world_points], [p[1] for p in world_points]
    x0, x1, y0, y1 = np.floor(min(xs)), np.ceil(max(xs)), np.floor(min(ys)), np.ceil(max(ys))
    segments = [((x, y0), (x, y1)) for x in np.arange(x0, x1 + 1)] + [((x0, y), (x1, y)) for y in np.arange(y0, y1 + 1)]
    for a, b in segments:
        pa, pb = cv2.perspectiveTransform(np.float64([[a, b]]), to_image)[0]
        cv2.line(canvas, tuple(map(int, pa)), tuple(map(int, pb)), GRID, 1, cv2.LINE_AA)


def _draw_shape(canvas: np.ndarray, points: list[Point], color, closed: bool = False) -> None:
    pts = np.int32(points)
    if len(pts) >= 2:
        cv2.polylines(canvas, [pts], closed, color, 2, cv2.LINE_AA)
    for i, (x, y) in enumerate(pts):
        cv2.circle(canvas, (int(x), int(y)), 5, color, -1, cv2.LINE_AA)
        cv2.putText(canvas, str(i + 1), (int(x) + 6, int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


def _label(canvas: np.ndarray, polygon: list[Point], text: str, color) -> None:
    cx, cy = np.mean(np.float32(polygon), axis=0)
    cv2.putText(canvas, text, (int(cx), int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)


def _magnifier(canvas: np.ndarray, source: np.ndarray, cursor: tuple[int, int], radius: int = 30, zoom: int = 5) -> None:
    # Top-right inset, 5× zoom around the cursor with a crosshair — tile corners are only ~10 px apart.
    h, w = source.shape[:2]
    x, y = min(max(cursor[0], radius), w - radius), min(max(cursor[1], radius), h - radius)
    patch = cv2.resize(source[y - radius:y + radius, x - radius:x + radius], None, fx=zoom, fy=zoom,
                       interpolation=cv2.INTER_NEAREST)
    size = patch.shape[0]
    cx, cy = (cursor[0] - x + radius) * zoom, (cursor[1] - y + radius) * zoom
    cv2.line(patch, (cx, 0), (cx, size), (0, 0, 255), 1)
    cv2.line(patch, (0, cy), (size, cy), (0, 0, 255), 1)
    cv2.rectangle(patch, (0, 0), (size - 1, size - 1), (255, 255, 255), 2)
    canvas[40:40 + size, w - size - 6:w - 6] = patch
    cv2.rectangle(canvas, (w - size - 6, 40 + size), (w - 6, 66 + size), (0, 0, 0), -1)
    cv2.putText(canvas, f"x {cursor[0]}  y {cursor[1]}", (w - size, 59 + size), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 1, cv2.LINE_AA)


def _banner(canvas: np.ndarray, text: str) -> None:
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 34), (0, 0, 0), -1)
    cv2.putText(canvas, text, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)


if __name__ == "__main__":
    main()
