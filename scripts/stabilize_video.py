"""Day 2 — one-time prep for stock clips filmed by hand from a building: lock every frame to the first one and shrink.

    python scripts/stabilize_video.py --input c_37570306.mp4 --output data/raw/crowd_06.mp4 --width 1080

Zones and calibration are drawn on the first frame, so a camera that drifts slides them across the ground. Each frame
is aligned to frame 0 with a translation estimated from ORB features (RANSAC ignores the moving crowd), the border
the drift uncovers is cropped, and the result is resized. Aligning to frame 0, not to the previous frame, means
small errors don't add up into drift. Not for live cameras: real CCTV is fixed.
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np

ANALYSIS_WIDTH = 540   # features are matched on a small copy: fast, and enough for a translation
MAX_FEATURES = 3000
KEEP_MATCHES = 400


def _translation(orb, matcher, ref, frame_small) -> np.ndarray:
    k0, d0 = ref
    k1, d1 = orb.detectAndCompute(frame_small, None)
    matches = sorted(matcher.match(d0, d1), key=lambda m: m.distance)[:KEEP_MATCHES]
    src = np.float32([k0[m.queryIdx].pt for m in matches])
    dst = np.float32([k1[m.trainIdx].pt for m in matches])
    affine, _ = cv2.estimateAffinePartial2D(dst, src, method=cv2.RANSAC)
    return affine[:, 2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1080)
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.input)
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = ANALYSIS_WIDTH / w
    orb, matcher = cv2.ORB_create(MAX_FEATURES), cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    # Pass 1: shift of every frame relative to frame 0 (full-resolution pixels).
    shifts, ref = [], None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
        if ref is None:
            ref = orb.detectAndCompute(small, None)
            shifts.append(np.zeros(2))
        else:
            shifts.append(_translation(orb, matcher, ref, small) / scale)
    shifts = np.array(shifts)
    margin_x, margin_y = int(np.ceil(np.abs(shifts[:, 0]).max())), int(np.ceil(np.abs(shifts[:, 1]).max()))
    crop_w, crop_h = w - 2 * margin_x, h - 2 * margin_y
    out_w = args.width
    out_h = int(round(crop_h * out_w / crop_w / 2)) * 2
    print(f"{len(shifts)} frames, max shift x {margin_x}px y {margin_y}px → crop {crop_w}x{crop_h} → {out_w}x{out_h}")

    # Pass 2: shift back, crop the uncovered border, resize, write.
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
    for (dx, dy) in shifts:
        ok, frame = cap.read()
        if not ok:
            break
        aligned = cv2.warpAffine(frame, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h), flags=cv2.INTER_LINEAR)
        crop = aligned[margin_y:margin_y + crop_h, margin_x:margin_x + crop_w]
        writer.write(cv2.resize(crop, (out_w, out_h), interpolation=cv2.INTER_AREA))
    writer.release()
    print(f"wrote {args.output} ({n} frames at {fps:.0f} fps)")


if __name__ == "__main__":
    main()
