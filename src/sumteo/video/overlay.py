"""Days 1–2 — drawing on the video: boxes + speeds, zones in their level color, counting lines, heatmap, metrics panel.

Hangul (관심 / 주의 / 경계 / 심각) can't be drawn by cv2.putText, so all text goes through one Pillow pass per frame.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from sumteo.analytics.crowd import CrowdLevel, CrowdMetrics
from sumteo.analytics.state import TrackStore
from sumteo.geometry.zones import ZoneShape
from sumteo.perception.detector import Detection

LEVEL_COLORS = {  # BGR
    CrowdLevel.GREEN: (90, 190, 60), CrowdLevel.YELLOW: (0, 215, 255),
    CrowdLevel.ORANGE: (0, 130, 255), CrowdLevel.RED: (40, 40, 230),
}
UNKNOWN_COLOR, LINE_COLOR, WHITE = (200, 200, 200), (255, 160, 0), (255, 255, 255)
ZONE_FILL_ALPHA, HEATMAP_ALPHA = 0.25, 0.45
_FONTS = ["/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"]


class Overlay:
    def __init__(self, font_size: int = 16):
        path = next((p for p in _FONTS if Path(p).exists()), None)
        self.font = ImageFont.truetype(path, font_size) if path else None   # None → English labels via cv2
        self._texts: list[tuple[tuple[int, int], str, tuple[int, int, int]]] = []

    def draw(self, image: np.ndarray, *, detections: list[Detection], tracks: TrackStore | None,
             zones: list[ZoneShape], metrics: dict[str, CrowdMetrics], zone_areas: dict[str, float | None],
             crossing_counts: dict[str, dict[int, int]], density_map: np.ndarray | None, show_heatmap: bool,
             fps: float, demo_levels: dict | None = None) -> None:
        if show_heatmap and density_map is not None:
            _heatmap(image, density_map)
        self._zones(image, zones, metrics, zone_areas, crossing_counts)
        self._detections(image, detections, tracks)
        self._panel(image, zones, metrics, fps, demo_levels)
        self._flush(image)

    # --- parts ---------------------------------------------------------------------------------------------------

    def _zones(self, image, zones, metrics, zone_areas, crossing_counts) -> None:
        fill = image.copy()
        for zone in zones:
            level = metrics[zone.id].level if zone.id in metrics else None
            cv2.fillPoly(fill, [np.int32(zone.polygon.points)], LEVEL_COLORS.get(level, UNKNOWN_COLOR))
        cv2.addWeighted(fill, ZONE_FILL_ALPHA, image, 1 - ZONE_FILL_ALPHA, 0, dst=image)
        for zone in zones:
            pts = np.int32(zone.polygon.points)
            m = metrics.get(zone.id)
            color = LEVEL_COLORS.get(m.level if m else None, UNKNOWN_COLOR)
            cv2.polylines(image, [pts], True, color, 2, cv2.LINE_AA)
            area = zone_areas.get(zone.id)
            label = f"{zone.id}  {self._level_text(m.level) if m else ''}" + (f"  {area:.0f} m²" if area else "")
            x, y = pts.min(axis=0)
            self._text((int(x), max(int(y) - 24, 0)), label, color)
            for line_id, line in zone.lines.items():
                a, b = tuple(map(int, line.a)), tuple(map(int, line.b))
                cv2.line(image, a, b, LINE_COLOR, 3, cv2.LINE_AA)
                counts = crossing_counts.get(line_id, {1: 0, -1: 0})
                self._text((b[0] - 150, b[1] - 26), f"{line_id.split(':')[1]}  +{counts[1]} / -{counts[-1]}", LINE_COLOR)

    def _detections(self, image, detections, tracks) -> None:
        """Box + ID per person; with a calibration also the walking speed in m/s."""
        for d in detections:
            x1, y1, x2, y2 = map(int, d.bbox)
            color = _track_color(d.track_id)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            label = str(d.track_id)
            if tracks is not None and d.track_id in tracks.tracks:
                label += f" {tracks.tracks[d.track_id].speed_mps:.1f}"
            cv2.putText(image, label, (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    def _panel(self, image, zones, metrics, fps, demo_levels) -> None:
        lines = [(f"FPS {fps:4.1f}", WHITE)]
        if demo_levels:
            lines.append((f"DEMO THRESHOLDS: yellow {demo_levels['yellow']} / orange {demo_levels['orange']} / "
                          f"red {demo_levels['red']} /m² (not the real levels)", LEVEL_COLORS[CrowdLevel.RED]))
        for zone in zones:
            m = metrics.get(zone.id)
            if m is None:
                lines.append((f"{zone.id}: not calibrated", UNKNOWN_COLOR))
                continue
            lines.append((f"{zone.id}  {self._level_text(m.level)}  {m.density_ppm2:.2f} /m²  "
                          f"{m.count:.0f} people ({m.count_source})  {m.median_speed_mps:.1f} m/s", LEVEL_COLORS[m.level]))
        height = 10 + 24 * len(lines)
        width = 20 + max(len(text) for text, _ in lines) * 9
        cv2.rectangle(image, (0, 0), (min(width, image.shape[1]), height), (0, 0, 0), -1)
        for i, (text, color) in enumerate(lines):
            self._text((8, 6 + 24 * i), text, color)

    # --- text ----------------------------------------------------------------------------------------------------

    def _level_text(self, level: CrowdLevel) -> str:
        return level.label if self.font else level.label.split(" ", 1)[1]   # "관심 Attention" → "Attention"

    def _text(self, origin: tuple[int, int], text: str, color) -> None:
        self._texts.append((origin, text, color))

    def _flush(self, image: np.ndarray) -> None:
        if self.font is None:
            for (x, y), text, color in self._texts:
                cv2.putText(image, text.replace("²", "2"), (x, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
        elif self._texts:
            pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil)
            for (x, y), text, (b, g, r) in self._texts:
                draw.text((x, y), text, font=self.font, fill=(r, g, b), stroke_width=2, stroke_fill=(0, 0, 0))
            image[:] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
        self._texts.clear()


def _heatmap(image: np.ndarray, density_map: np.ndarray) -> None:
    peak = float(density_map.max())
    if peak <= 0:
        return
    colored = cv2.applyColorMap(np.uint8(255 * np.clip(density_map / peak, 0, 1)), cv2.COLORMAP_JET)
    cv2.addWeighted(colored, HEATMAP_ALPHA, image, 1 - HEATMAP_ALPHA, 0, dst=image)


def _track_color(track_id: int) -> tuple[int, int, int]:
    # Stable per-ID color, so an ID switch is visible as a color change.
    rng = np.random.default_rng(track_id)
    return tuple(int(c) for c in rng.integers(64, 256, size=3))
