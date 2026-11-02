"""Run one camera worker.

    python scripts/run_camera.py --camera configs/cameras/crowd_demo.yaml [--save out.mp4] [--no-window]
"""
from __future__ import annotations

import argparse

from sumteo.config import load_config
from sumteo.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", required=True)
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--save", help="write the annotated video to this path")
    parser.add_argument("--no-window", action="store_true")
    args = parser.parse_args()

    app, camera = load_config(args.camera, args.config)
    if args.no_window:
        app.runtime["show_window"] = False
    if args.save:
        app.runtime["save_path"] = args.save
    Pipeline(app, camera).run()


if __name__ == "__main__":
    main()
