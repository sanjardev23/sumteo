# Data Guide

Nothing here needs model training from scratch. Data is for **testing, tuning thresholds and evaluation**.
All raw data goes in `data/` (git-ignored). Check each dataset's license before publishing frames from it.

## 1. Crowd datasets (counting evaluation)

| Dataset | What | Use | Where |
|---|---|---|---|
| ShanghaiTech Part A | 482 dense crowd images | dense counting MAE | Kaggle mirrors (search "ShanghaiTech crowd") / original paper page |
| ShanghaiTech Part B | 716 street images, sparse–medium | main counting MAE | same as above |
| NWPU-Crowd | 5k images, very varied | optional, also has pretrained weights | official site (registration) |
| JHU-Crowd++ | 4k images, weather/night | optional robustness check | request form on official site |
| Mall dataset | 2000 frames of a mall CCTV video | counting on real CCTV video | official CUHK page |

Pretrained weights: the DM-Count GitHub repo (cvlab-stonybrook/DM-Count) links models trained on ShanghaiTech A/B, UCF-QNRF and NWPU. Start with **SH-B** for street scenes and **SH-A / NWPU** for dense scenes.

## 2. Crowd videos (demo + level testing)

- **Pexels / Pixabay** free stock videos — search: "crowd", "festival crowd", "crowded street", "shibuya crossing", "concert crowd", "subway station rush hour". Their licenses allow free use, including in a demo video.
- Pick 3–5 videos with a **high, fixed camera** (CCTV-like). Handheld/moving cameras break optical flow and calibration.
- Label manually for level testing: every 10 s → `GREEN/YELLOW/ORANGE/RED` in `data/processed/crowd_levels.csv`:
  ```csv
  video,start_s,end_s,level
  crowd_01.mp4,0,10,GREEN
  crowd_01.mp4,10,20,YELLOW
  ```
- Keep 1–2 videos as a held-out test set; tune thresholds only on the others.

### Calibrating stock videos (scale is an estimate)
Stock footage has no object of known size, so the ground square's real size is **estimated, not measured**:
1. Vanishing points of two floor-line families (tile joints), assuming a level camera (no roll, principal point at the
   image centre) → focal length and camera height.
2. Scale from the median height of many YOLO person boxes, assuming an average person height of 1.65 m.
3. Check: the projected 1 m grid runs parallel to the floor lines.

Uncertainty is about ±10% in length and speed (mostly the 1.65 m assumption), so about ±20% in areas and people/m²
(area scales with length squared).
The independent sanity check is the Day 1 walking speed (~1.0–1.5 m/s). Record each camera's estimate here.

| Camera | Ground square | Zone area | Lines | Basis |
|---|---|---|---|---|
| `crowd_demo` (crowd_02) | 6 × 6 m (reprojects to 36.0 m²) | `main` 148.3 m² | entry = white floor line, 13.8 m | vanishing points → focal ≈ 1243 px (55° HFOV), height ≈ 6.5 m; scale from 477 person boxes |

> Don't use real disaster footage (e.g. Itaewon) in the demo. Mention the event in the problem statement only.

## 3. Seoul real-time city data (optional, context only)

- data.seoul.go.kr → "서울시 실시간 도시데이터" (real-time city data). Free API key → `SEOUL_API_KEY` in `.env`.
- ~120 hotspots, 4-level congestion label (여유 / 보통 / 약간 붐빔 / 붐빔), estimated from mobile signals,
  updated every 5 min with ~15 min delay. Not a camera count — use it only as wider-area context, never as ground truth.
- Check the official API docs for field names before coding against them.

## 4. Extra (optional)
| Dataset | Use |
|---|---|
| CUHK Avenue | normal walking scenes with a few abnormal clips — false-alarm testing |

## 5. Folder layout
```
data/
├── raw/          downloaded videos + datasets (as downloaded)
├── processed/    extracted frames, crowd_levels.csv
└── snapshots/    event snapshots (blurred) written by the pipeline
```
