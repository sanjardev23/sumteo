"""Day 1 — interactive calibration on the first frame of a camera's source.

    python scripts/calibrate.py --camera configs/cameras/crowd_demo.yaml

Steps: click 4 ground points → type their real-world coords (meters) → for each zone: click its
polygon (Enter to close), then optionally its entry line and exit line (2 clicks each, Enter to skip)
→ next zone or finish. Writes calibration / zones (polygon, entry_line, exit_line) back into the
camera YAML (ARCHITECTURE §2.4). Zone risk flags are edited by hand in the YAML.
"""
# TODO(Day 1): cv2.setMouseCallback-based tool


if __name__ == "__main__":
    raise NotImplementedError("Day 1")
