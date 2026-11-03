"""Day 5 — run the API with its camera workers (video files loop, so the demo keeps going).

    python scripts/serve.py --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml

Then the dashboard: cd dashboard && npm run dev → http://127.0.0.1:3000
"""
from __future__ import annotations

import argparse

import uvicorn

from sumteo.api.server import create_app
from sumteo.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cameras", nargs="+", required=True)
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    defaults, _ = load_config(args.cameras[0], args.config)
    uvicorn.run(create_app(args.cameras, args.config), host=defaults.api["host"], port=defaults.api["port"],
                log_level="warning")


if __name__ == "__main__":
    main()
