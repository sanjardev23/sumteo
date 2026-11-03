# Results

## Crowd counting (Day 2)

Full-image inference on Apple MPS, `scripts/eval_crowd.py`. The paper reports SH-B 7.4 / 11.8 and SH-A 59.7 / 95.7,
so the re-declared model and the authors' weights reproduce it.

| Dataset | Model | MAE | RMSE |
|---|---|---|---|
| ShanghaiTech B test (316 images) | DM-Count SH-B (authors' weights) | 7.34 | 11.82 |
| ShanghaiTech A test (182 images) | DM-Count SH-A (authors' weights) | 59.60 | 95.58 |

## Crowd levels (Day 4, labeled crowd videos)

| Video | Level accuracy | Off by more than one level |
|---|---|---|
| | | |

## Alerts (Day 4)

| Metric | Value |
|---|---|
| Level-change events per labeled change (target ≈ 1) | |
| False alarms per hour (ORANGE/RED on GREEN/YELLOW footage) | |
| Mean time-to-alert after labeled level change (s) | |
