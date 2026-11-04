"""Day 5 — run the API with its camera workers (video files loop, so the demo keeps going).

    python scripts/serve.py --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml

Day 6 — replay mode (ARCHITECTURE §2.11): recorded cameras play with no models; at most one live camera on a laptop.

    python scripts/serve.py --replay data/recordings/crossing-demo-1 data/recordings/test-crowd-03 \
        [--cameras configs/cameras/crowd_demo.yaml]

Then the dashboard: cd dashboard && npm run dev → http://127.0.0.1:3000
"""
from __future__ import annotations

import argparse

import uvicorn

from sumteo.api.replay import StaleRecording, load_recording
from sumteo.api.server import create_app
from sumteo.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cameras", nargs="*", default=[], help="live camera YAMLs")
    parser.add_argument("--replay", nargs="*", default=[], help="recording folders (scripts/record_camera.py)")
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    if not args.cameras and not args.replay:
        parser.error("give --cameras and/or --replay")
    try:
        app = create_app(args.cameras, args.config, args.replay)
    except StaleRecording as error:
        raise SystemExit(str(error)) from None
    first = args.cameras[0] if args.cameras else load_recording(args.replay[0], args.config)["camera_config"]
    api = load_config(first, args.config)[0].api
    # MJPEG streams never end on their own: without a limit a stop waits forever and leaves the camera workers running.
    uvicorn.run(app, host=api["host"], port=api["port"], log_level="warning", timeout_graceful_shutdown=3)


if __name__ == "__main__":
    main()
