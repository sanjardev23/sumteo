"""Day 2 — counting MAE / RMSE on ShanghaiTech test sets.
Day 4 — level accuracy on labeled crowd videos.

    python scripts/eval_crowd.py --data data/raw/ShanghaiTech/part_B_test.parquet --weights models/dmcount_shb.pth
    python scripts/eval_crowd.py --levels data/processed/crowd_levels.csv

ShanghaiTech comes from the Hugging Face mirror as parquet (DATA.md §1): one row per image with the JPEG bytes
and the ground-truth head count.
"""
from __future__ import annotations

import argparse
import math
import time

import cv2
import numpy as np
import pyarrow.parquet as pq

from sumteo.perception.density import DensityEstimator


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="ShanghaiTech test parquet")
    parser.add_argument("--weights", default="models/dmcount_shb.pth")
    parser.add_argument("--device", default="mps")
    parser.add_argument("--limit", type=int, help="only the first N images (quick check)")
    parser.add_argument("--levels", help="Day 4: labeled crowd-level CSV")
    args = parser.parse_args()
    if args.levels:
        # TODO(Day 4): run labeled videos headless, compare predicted level per 10 s window with the label
        raise NotImplementedError("Day 4")
    eval_counting(args.data, args.weights, args.device, args.limit)


if __name__ == "__main__":
    main()
