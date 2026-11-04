"""Day 6 — record one camera's run for replay mode (ARCHITECTURE §2.11): the same Pipeline at the same settings.

    python scripts/record_camera.py --camera configs/cameras/crossing_demo.yaml [--out data/recordings/<id>] \
        [--device cuda] [--overwrite]

Writes only video.mp4 (the blurred + overlaid frames as the stream shows them, 960 px wide), timeline.jsonl (video-clock
order: every kept frame's ts, one camera state per video second, every event), snapshots/ (blurred) and manifest.json.
No raw frames. One camera at a time; the run is the camera's solo test (§2.12) — check the printed levels and events.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from sumteo.api.replay import run_inputs
from sumteo.api.server import STREAM_WIDTH, camera_state
from sumteo.config import config_hash, load_config
from sumteo.events.notifiers.platform import event_dict
from sumteo.pipeline import Pipeline


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def open_video(path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    for codec in ("avc1", "mp4v"):   # H.264 where this OpenCV build has it
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer
    raise RuntimeError(f"cannot write video: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", required=True)
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--out", help="default: data/recordings/<camera id>")
    parser.add_argument("--device", help="e.g. cuda on Colab; not part of the config hash")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing recording of this camera")
    args = parser.parse_args()

    app, camera = load_config(args.camera, args.config)
    digest, inputs = config_hash(app, camera), run_inputs(app, camera)
    out = Path(args.out or f"data/recordings/{camera.id}")
    if out.exists():
        if not args.overwrite:
            raise SystemExit(f"{out} exists; pass --overwrite to replace it")
        shutil.rmtree(out)   # a recording is replaced whole, never mixed with an older run
    (out / "snapshots").mkdir(parents=True)
    if args.device:
        app.runtime["device"] = args.device
    app.runtime.update(show_window=False, save_path=None, loop=False)
    app.events["snapshot_dir"] = str(out / "snapshots")
    app.storage["db_path"] = None   # a recording never writes the platform database

    pipeline = Pipeline(app, camera)
    timeline = (out / "timeline.jsonl").open("w")
    video: list[cv2.VideoWriter] = []
    latest = [None]
    last_second = [None]
    counts = {"frames": 0, "events": 0}
    duration = [0.0]
    started = time.time()

    def write(kind: str, ts: float, **body) -> None:
        timeline.write(json.dumps({"kind": kind, "ts": round(ts, 3), **body}, ensure_ascii=False) + "\n")

    def on_image(image) -> None:
        h, w = image.shape[:2]
        if w > STREAM_WIDTH:
            image = cv2.resize(image, (STREAM_WIDTH, round(h * STREAM_WIDTH / w)), interpolation=cv2.INTER_AREA)
        latest[0] = image

    def on_frame(ts, metrics, events) -> None:
        if latest[0] is not None:   # no image while the feed is lost: no frame line, the replay holds the last one
            if not video:
                video.append(open_video(out / "video.mp4", pipeline._output_fps(), latest[0].shape[1::-1]))
            video[0].write(latest[0])
            write("frame", ts)
            counts["frames"] += 1
            latest[0] = None
        if int(ts) != last_second[0]:
            last_second[0] = int(ts)
            state = camera_state(pipeline)
            write("state", ts, camera=state)
            print(f"  {ts:6.1f}s  " + "  ".join(f"{z['id']} {z['level'] or '-'} {z['density_ppm2'] or 0:.2f}/m²"
                                                  for z in state["zones"]), flush=True)
        for event in events:
            data = event_dict(event)
            if event.snapshot_path:
                data["snapshot_path"] = f"snapshots/{Path(event.snapshot_path).name}"
            write("event", event.ts, event=data)
            counts["events"] += 1
            print(f"  {event.ts:6.1f}s  EVENT {event.severity.value} {event.type.value} {event.zone_id or ''} "
                  f"{event.details.get('reasons', '')}", flush=True)
        duration[0] = ts

    try:
        pipeline.run(on_frame=on_frame, on_image=on_image)
    finally:
        timeline.close()
        if video:
            video[0].release()
    manifest = {
        "camera_id": camera.id, "camera_config": str(args.camera), "config_hash": digest, "inputs": inputs,
        "git_commit": git_commit(),
        "device": app.runtime["device"], "fps": pipeline._output_fps(), "frames": counts["frames"],
        "events": counts["events"], "duration_s": round(duration[0], 3), "recorded_at": started,
        "processing_s": round(time.time() - started, 1),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"recorded {camera.id}: {counts['frames']} frames, {counts['events']} events, {duration[0]:.1f} s of video "
          f"in {manifest['processing_s']} s on {manifest['device']} → {out}")


if __name__ == "__main__":
    main()
