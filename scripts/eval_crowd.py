"""Day 2 — counting MAE / RMSE on ShanghaiTech test sets.
Day 4 — level accuracy and alert metrics on labeled crowd videos (ARCHITECTURE §5).

    python scripts/eval_crowd.py --data data/raw/ShanghaiTech/part_B_test.parquet --weights models/dmcount_shb.pth
    python scripts/eval_crowd.py --levels --labels data/processed/crowd_levels.csv \
        --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml [--demo]

ShanghaiTech comes from the Hugging Face mirror as parquet (DATA.md §1): one row per image with the JPEG bytes
and the ground-truth head count.

Levels: one headless run per camera. Without --demo the demo-only overrides (DATA.md §2) are dropped, so every
camera runs on the real thresholds; camera properties (density weights, switch) stay. A label's level is its people
count ÷ zone area by the same thresholds the run uses; system level and count are read at the window's midpoint frame.
"""
from __future__ import annotations

import argparse
import csv
import math
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq

import yaml

from sumteo.analytics.crowd import CrowdAnalyzer, CrowdLevel, risk_factor
from sumteo.config import load_config
from sumteo.events.engine import severity_of
from sumteo.events.models import EventType, Severity
from sumteo.perception.density import DensityEstimator

DEMO_KEYS = ("levels_ppm2", "hysteresis_ppm2", "rise_ppm2_per_min", "rise_min_density")   # crowd: demo-only (DATA §2)
_SEVERITY_OF_LEVEL = {CrowdLevel.YELLOW: Severity.INFO, CrowdLevel.ORANGE: Severity.WARNING, CrowdLevel.RED: Severity.CRITICAL}


def eval_counting(data: str, weights: str, device: str, limit: int | None) -> None:
    table = pq.read_table(data, columns=["file_name", "image", "count"])
    rows = table.to_pylist()[:limit]
    estimator = DensityEstimator(weights, device)
    errors, start = [], time.perf_counter()
    for i, row in enumerate(rows, 1):
        image = cv2.imdecode(np.frombuffer(row["image"]["bytes"], np.uint8), cv2.IMREAD_COLOR)  # grayscale → 3 channels
        _, predicted = estimator.estimate(image)
        errors.append(predicted - row["count"])
        if i % 50 == 0:
            print(f"  {i}/{len(rows)}  running MAE {np.mean(np.abs(errors)):.2f}")
    errors = np.array(errors)
    print(f"{data} · {weights} · {len(errors)} images · {time.perf_counter() - start:.0f} s")
    print(f"MAE {np.mean(np.abs(errors)):.2f}  RMSE {math.sqrt(np.mean(errors ** 2)):.2f}  "
          f"mean error {np.mean(errors):+.2f} (negative = under-count)")


def _load(camera: str, demo: bool, tmp: Path):
    data = yaml.safe_load(Path(camera).read_text())
    crowd = (data.get("overrides") or {}).get("crowd", {})
    demo_used = any(k in crowd for k in DEMO_KEYS)
    if not demo:
        for key in DEMO_KEYS:
            crowd.pop(key, None)
    path = tmp / Path(camera).name
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    app, cam = load_config(path)
    app.runtime.update(show_window=False, save_path=None)
    app.storage["db_path"] = ""
    app.events["snapshot_dir"] = str(tmp / "snapshots")
    app.notifiers["console"] = False
    return app, cam, demo and demo_used


def _run(app, cam):
    """Headless run → per-frame (ts, level, count) of the camera's first zone, all events, footage seconds."""
    from sumteo.pipeline import Pipeline   # loads the models only when levels are evaluated
    pipeline = Pipeline(app, cam)
    zone = pipeline.zones[0].id
    frames, events = [], []

    def on_frame(ts, metrics, new_events):
        if zone in metrics:
            frames.append((ts, metrics[zone].level, metrics[zone].count))
        events.extend(new_events)

    pipeline.run(on_frame=on_frame)
    return pipeline, zone, frames, events


def _label_level(app, cam, zone_id: str, area: float, count: float) -> CrowdLevel:
    risk = next(z.risk for z in cam.zones if z.id == zone_id)
    return CrowdAnalyzer(app.crowd, zone_id, area, risk_factor(app.crowd, risk)).level_for(count / area, 0.0)


def eval_levels(labels: str, cameras: list[str], demo: bool) -> None:
    rows = defaultdict(list)
    with open(labels) as f:
        for row in csv.DictReader(f):
            rows[row["video"]].append(row)
    hits = off = total = 0
    count_errors, changes, alert_events, delays, false_alarms, footage = [], 0, 0, [], 0, 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for camera in cameras:
            app, cam, demo_used = _load(camera, demo, Path(tmp))
            video = Path(str(cam.source)).name
            if video not in rows:
                print(f"{camera}: no labels for {video}, skipped")
                continue
            pipeline, zone, frames, events = _run(app, cam)
            area = pipeline.zone_areas[zone]
            footage += frames[-1][0] - frames[0][0]
            labelled = []
            print(f"\n{video} ({camera}, zone {zone} {area:.1f} m², {'DEMO thresholds' if demo_used else 'real thresholds'})")
            for row in sorted(rows[video], key=lambda r: float(r["start_s"])):
                mid = (float(row["start_s"]) + float(row["end_s"])) / 2
                ts, level, count = min(frames, key=lambda f: abs(f[0] - mid))
                truth = _label_level(app, cam, zone, area, float(row["count"]))
                labelled.append((mid, float(row["start_s"]), float(row["end_s"]), truth))
                hits += level is truth
                off += abs(level.rank - truth.rank) > 1
                total += 1
                count_errors.append(count - float(row["count"]))
                print(f"  t {mid:5.1f}s  label {truth.value:6} ({row['count']:>3} people)  system {level.value:6} "
                      f"({count:5.1f})")
            # Alerts: a labeled change = the first window at a higher level (the first window counts if above GREEN).
            crowd_events = [e for e in events if e.type is EventType.CROWD_LEVEL or "CROWD_LEVEL" in e.details.get("reasons", [])]
            alert_events += sum(1 for e in events if "CROWD_LEVEL" in e.details.get("reasons", []))
            previous, since = CrowdLevel.GREEN, 0.0
            for mid, _, _, truth in labelled:
                if truth.rank > previous.rank:
                    changes += 1
                    need = _SEVERITY_OF_LEVEL[truth]
                    hit = next((e for e in crowd_events if e.ts >= since and e.severity.rank >= need.rank), None)
                    if hit:
                        delays.append(hit.ts - mid)
                    print(f"  labeled change → {truth.value} at {mid:.1f}s: "
                          + (f"alert {hit.severity.value} at {hit.ts:.1f}s ({hit.ts - mid:+.1f}s)" if hit else "no alert"))
                    since = mid
                previous = truth
            for e in events:
                if e.severity.rank >= Severity.WARNING.rank and "CROWD_LEVEL" in e.details.get("reasons", []):
                    window = next((t for _, s, end, t in labelled if s <= e.ts < end), None)
                    if window is not None and window.rank <= CrowdLevel.YELLOW.rank:
                        false_alarms += 1
                        print(f"  false alarm: {e.severity.value} at {e.ts:.1f}s on {window.value} footage")
    errors = np.array(count_errors)
    print(f"\nwindows {total}: level accuracy {hits / total:.0%}, off by > 1 level {off}, "
          f"count MAE {np.mean(np.abs(errors)):.1f} (mean error {np.mean(errors):+.1f})")
    print(f"labeled level changes {changes}: CROWD_LEVEL events {alert_events} ({alert_events / changes:.2f} per change)"
          if changes else "labeled level changes 0")
    if delays:
        print(f"mean time-to-alert {np.mean(delays):+.1f}s (each: {', '.join(f'{d:+.1f}' for d in delays)})")
    print(f"false alarms {false_alarms} in {footage:.0f} s of footage ({false_alarms / footage * 3600:.0f} per hour)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="ShanghaiTech test parquet")
    parser.add_argument("--weights", default="models/dmcount_shb.pth")
    parser.add_argument("--device", default="mps")
    parser.add_argument("--limit", type=int, help="only the first N images (quick check)")
    parser.add_argument("--levels", action="store_true", help="Day 4: level accuracy + alert metrics")
    parser.add_argument("--labels", default="data/processed/crowd_levels.csv")
    parser.add_argument("--cameras", nargs="+", help="camera YAMLs whose source videos are labeled")
    parser.add_argument("--demo", action="store_true", help="keep the cameras' demo-only thresholds")
    args = parser.parse_args()
    if args.levels:
        eval_levels(args.labels, args.cameras, args.demo)
        return
    eval_counting(args.data, args.weights, args.device, args.limit)


if __name__ == "__main__":
    main()
