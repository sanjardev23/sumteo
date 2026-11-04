# Data Guide

Nothing here needs model training from scratch. Data is for **testing, tuning thresholds and evaluation**.
All raw data goes in `data/` (git-ignored). Check each dataset's license before publishing frames from it.

## 1. Crowd datasets (counting evaluation)

| Dataset | What | Use | Where |
|---|---|---|---|
| ShanghaiTech Part A | 482 dense crowd images | dense counting MAE | Hugging Face parquet mirror (below) |
| ShanghaiTech Part B | 716 street images, sparse–medium | main counting MAE | same as above |
| NWPU-Crowd | 5k images, very varied | optional, also has pretrained weights | official site (registration) |
| JHU-Crowd++ | 4k images, weather/night | optional robustness check | request form on official site |
| Mall dataset | 2000 frames of a mall CCTV video | counting on real CCTV video | official CUHK page |
| CroHD (Head Tracking 21) | 9 crowded CCTV sequences with a head box per person per frame | crowd_07 (§2): demo clip + per-frame count check on real CCTV | [MOTChallenge HT21](https://motchallenge.net/data/Head_Tracking_21/) |

ShanghaiTech A + B are loaded from the Hugging Face parquet mirror
[KTAEHWA/shanghaitech-crowd-counting](https://huggingface.co/datasets/KTAEHWA/shanghaitech-crowd-counting);
`scripts/eval_crowd.py` reads the parquet files directly (`pyarrow` is in the dev extras).

Pretrained weights: the DM-Count GitHub repo (cvlab-stonybrook/DM-Count, MIT) links the authors' models on Google Drive
([folder](https://drive.google.com/drive/folders/10U7F4iW_aPICM5-qJq21SXLLkzlum9tX)), saved as
`models/dmcount_shb / sha / nwpu / qnrf.pth`. **SH-B** is the default (street scenes); **SH-A** for dense cameras; **NWPU** for very high, top-down views with tiny
people (§2.2, `crossing_demo`).

## 2. Crowd videos (demo + level testing)

- **Pexels / Pixabay** free stock videos — search: "crowd", "festival crowd", "crowded street", "shibuya crossing", "concert crowd", "subway station rush hour". Their licenses allow free use, including in a demo video.
- **CroHD / MOTChallenge HT21** (Sundararaman et al., CVPR 2021) — research CCTV footage, **CC BY-NC-SA 3.0**:
  non-commercial only, credit required, anything made from it (demo video, screenshots) shares the same licence; some
  sequences come from third-party sources whose terms may also apply. The README and the demo credit CroHD /
  MOTChallenge. The footage stays in `data/` (git-ignored); the project's AGPL-3.0 licence covers the code only.
- Pick 3–5 videos with a **high, fixed camera** (CCTV-like). Handheld/moving cameras break optical flow and calibration.
- Label for level testing in `data/processed/crowd_levels.csv`: per window, the people **count** in each zone by eye
  (zoomed grid cells of the window's midpoint frame, without looking at the system's output), and the level derived
  from count ÷ zone area with the thresholds that run uses (ARCHITECTURE §5). Windows are 10 s; crowd_06 uses 2 s. crowd_07 needs no hand counts: CroHD gives a head box per person per frame.
  ```csv
  video,start_s,end_s,count,level
  crowd_02.mp4,0,10,14,GREEN
  crowd_02.mp4,10,20,15,GREEN
  ```
  (illustrative rows). Who counted is recorded: the developer agent counts, the user spot-checks some frames
  independently. Day 4 spot-checks differed by 8–15% both ways, so labels carry about **±15%** counting noise
  (ARCHITECTURE §5). Labels are kept as first counted, never swapped after a spot-check.
- **Split:** tuning = crowd_02 + crowd_06; held-out = crowd_03 + crowd_04, run **once** after tuning. crowd_05 is out. crowd_06 has been removed since (below); the Day 4 numbers that used it
  stand as measured. **crowd_07 is held-out** (user decision, Day 6: "Run once, held-out") — the first count check on real CCTV, run
  once with the protocol in ARCHITECTURE §5; its labels are the CroHD head boxes, not hand counts.

Clips (stock, plus one research-dataset clip; none of a real disaster; map positions in the camera YAML `location:` are demo positions
around Itaewon Station — ARCHITECTURE §2.12):

| Clip | Camera config | Notes |
|---|---|---|
| crowd_01 | — | Pexels 20017503 (Osaka plaza); people ~26 px wide, too small for stable IDs; removed from `data/raw` (unused, Day 6) |
| crowd_02 | `crowd_demo.yaml` | Pexels 20660921; Day 1 demo: tracking, speeds, line crossings |
| crowd_03 | `test_crowd_03.yaml` | Pexels 37439458; held-out; same plaza as crowd_04, from above; real thresholds, no overrides — run once (Day 4). **Day 6 (user decision, demo recording only):** counting overrides only — `models.density` NWPU + `switch_density_ppm2` 0, the camera properties the held-out finding called for; real thresholds, no DEMO tag; the Day 4 numbers stand as measured with the old config; YOLO finds 1 in 4–7 people here |
| crowd_04 | `test_crowd_04.yaml` | Pexels 37439460; held-out; real thresholds, no overrides — run once (Day 4). Day 6: same counting overrides as crowd_03 (NWPU + switch 0), demo recording only |
| crowd_05 | — | Pexels 5544073; dense Shibuya at night, but the view moves, so a fixed zone slides over the ground; not evaluated; removed (unused, Day 6) |
| crowd_06 | `crossing_demo.yaml` | Day 2 dense demo: [Pexels 37570306](https://www.pexels.com/video/aerial-view-of-shibuya-crossing-in-tokyo-37570306/), Shibuya scramble from a tall building, crosswalks filling over 21.6 s; stabilized (below). **Replaced on Day 6** (user: "very low quality"); deleted once crowd_07 passes its solo test |
| crowd_07 | `crossing_demo.yaml` | Day 6 dense demo: CroHD **HT21-03** "Crowded pedestrian crossing", 1920×1080, 25 fps, all 1,000 frames (40 s) encoded from the original JPEGs. Fixed camera (`cam_motion=False`, measured shift < 2 px; HT21-02 / HT21-15 pan ~800 px, unusable). Labels: `data/processed/crowd_07_heads.txt` (CroHD ground-truth head boxes, MOT format, 257,939 boxes); heads per frame every 5 s 142 → 337 → 183, so the crowd builds up, peaks and clears. Zone counts: each head-box centre is lowered to a foot point by 1.65 m × the **horizontal** px-per-m at the foot row (estimated at the head row, re-read at the foot row, recomputed once); heads whose foot point falls inside the ground zone polygon are counted |

Pexels clips (free licence) re-download from `https://www.pexels.com/download/video/<id>/?w=1920&h=1080`; the IDs are
also in `data/raw/SOURCES.md`. None of crowd_01–05 shows density rising, which is why crowd_06 was added; crowd_07 replaced it on Day 6 (a sharp fixed
CCTV view instead of a stabilized drone crop).

**Stabilizing hand-held stock clips** — `scripts/stabilize_video.py`, a one-time prep step for stock clips only (real
CCTV is fixed). It aligns every frame to frame 0 (ORB + RANSAC, translation only), crops the uncovered border and
resizes. crowd_06 (4K portrait, ~7% drift, no zoom) → 1080×2046, residual shift < 1 px. crowd_03 / crowd_04 (10–13 px
drift, no zoom) → 1920×1070; the originals (`crowd_03_orig.mp4` / `crowd_04_orig.mp4`, the unstabilized downloads of 37439458 / 37439460) were
removed on Day 6 as unused.

### Calibrating stock videos (scale is an estimate)
Stock footage has no object of known size, so the ground square's real size is **estimated, not measured**:
1. Vanishing points of two floor-line families (tile joints), assuming a level camera (no roll, principal point at the
   image centre) → focal length and camera height.
2. Scale from the median height of many YOLO person boxes, assuming an average person height of 1.65 m.
3. Check: the projected 1 m grid runs parallel to the floor lines.

Uncertainty is about ±10% in length and speed (mostly the 1.65 m assumption), so about ±20% in areas and people/m²
(area scales with length squared).
The independent sanity check is the Day 1 walking speed (~1.0–1.5 m/s). Record each camera's estimate here.

**When the two-VP method can't work** (crowd_03 / crowd_04): the cross lines are horizontal in the image, so their
vanishing point is at infinity and the focal length can't be solved from two VPs. Instead: horizon = the row of the
receding lines' VP; focal = the value that makes person heights independent of distance; scale from 1.65 m people.
The focal length is only weakly constrained above ~2400 px, so crowd_03 (f ≈ 2800) may be off by more than the usual
±20% in area — the walking-speed check is the guard.

| Camera | Ground square | Zone area | Lines | Basis |
|---|---|---|---|---|
| `crowd_demo` (crowd_02) | 6 × 6 m (reprojects to 36.0 m²) | `main` 148.3 m² | entry (602,510)–(1104,571), 12.9 m (was 13.8 m; clipped to the zone's slanted sides): moved 2.5 m from the zone's far edge toward its centre on Day 3 (see *Counting lines*) | vanishing points → focal ≈ 1243 px (55° HFOV), height ≈ 6.5 m; scale from 477 person boxes |
| `test_crowd_03` (crowd_03) | 6 × 6 m (from the metrology) | `exit1` (was `plaza`, renamed Day 6) 269.2 m² (planned 264.4; one corner 2 px off) | — | horizon + "person height independent of distance" → f ≈ 2800 px, tilt 36°, camera ≈ 35 m; scale from 1.65 m people; check: walking 1.23 m/s |
| `test_crowd_04` (crowd_04) | 6 × 6 m (from the metrology) | `food-street` (was `plaza`, renamed Day 6) 312.8 m² | — | same method → f ≈ 2300 px, tilt 29°, camera ≈ 26 m; check: walking 1.13 m/s |
| `crossing_demo` (crowd_07) | 6.3 × 4.2 m on the near crosswalk band: image (488,795) (1404,795) (1437,1022) (408,1022) | `crossing` 223.7 m², polygon (100,330) (1880,330) (1910,1025) (330,1025) | none | **along** the band: stripes 74 px + 74 px, period 147 px at row 1020 / 131 px at row 815 = 0.9 m (45 + 45 cm, Japanese standard — **assumed**: CroHD gives no location); the 1.12 ratio matches the horizon from the stripe vanishing point (1.11). **Across** the band: from people 230–265 px tall at 1.6–1.7 m → look-down ≈ 22° (17–26°), width 4.2 m (3.4–5.4 m, **±25%**), consistent with the 4 m minimum crosswalk width. Checks: a person at row 655 → 1.69 m; shoulders 0.45–0.55 m; far zone (feet at rows 287–501, 7 people) 1.50–1.64 m, mean ≈ 1.57 m — plausible for a mixed crowd, so the far edge stays at row 330 (this checks the along-band scale, not the across-band width). Area is about **±30%** (±10% along × ±25% across), larger than the other cameras; the zone reaches row 330, far above the calibrated band (rows 795–1022), so the far part is extrapolated |
| `crossing_demo` (crowd_06, Day 2–5, removed) | 6 × 6 m, image (273,852) (447,852) (451,998) (261,998); 1 m grid follows the zebra stripes | `crossing` 79.4 m² (first estimate 85.9 m², ~8% tighter after the guided click — within ±10%) | none | zebra stripes: 45 cm stripe + 45 cm gap = 0.9 m period (Japanese standard), measured by FFT on two crosswalks at the same image height; local affine fit ~33 px/m across, ~25 px/m up/down, tilt ≈ 49°, crosswalks 31° apart; scale grows ~13% from y 780 to 1220; check: shoulders ≈ 13 px ≈ 0.45 m |

**Counting lines** — put them where people stay tracked on **both** sides, closer to the camera than the zone's far
edge, not where walkers disappear into a background crowd. crowd_02's first line (620,492)–(1120,548) sat on the far
edge: outward walkers vanished into the crowd behind it within ~0.7 m, so the 1 s median + 0.3 m band never registered
the far side (by eye OUT ~15, system 5). Moved 2.5 m toward the centre (computed with the homography, clipped to the
zone edges): by eye IN 5 / system 5, OUT 7–8 / system 11. A 5 m move gave more back-and-forth double counts.

**`crossing_demo` overrides.** Two kinds, kept apart. Camera properties are the same for crowd_07 (NWPU, switch 0);
the demo-only values were re-done for crowd_07 on Day 6 (below the crowd_06 ones).

*Camera properties (real — a real top-down camera would need the same):*
- `crowd.switch_density_ppm2` 0.0 — always the density count; from this height YOLO finds ~1 in 4 people
- `models.density` = `models/dmcount_nwpu.pth` — on a busy patch counted by eye at ~150: NWPU 154 (1×) / 152 (2×),
  SH-A 140 → 84 (scale-sensitive), SH-B 5, YOLO 34. Tiny top-down people need NWPU.
- Pacing (crowd_07, Day 6, user decision "lower the frame target"): `runtime.target_fps` 5, `models.flow_every_n_frames` 1
  (0.2 s pairs), `models.density_every_n_frames` 10 (2 s), so the camera keeps up in real time (ARCHITECTURE §4). Side
  effects, stated, not changed: the ByteTrack 30-frame buffer now lasts 6 s (2 s at 15 fps), and `turbulence_red` 0.8
  was tuned with ~0.13 s flow pairs, so it may not mean the same here. Other cameras stay at 15 / 2 / 15.
  **Recorded (Colab, Day 6):** GREEN → YELLOW 4 s → `DENSITY_RISING` 6.0 s → ORANGE 11 s → RED 17 s → `COUNTER_FLOW`
  19.2 s → RED until 35 s → ORANGE 36 s → YELLOW 37–39 s. Density alone falls below RED − hysteresis at 29 s; RED holds
  6 s longer through "ORANGE + turbulence > 0.8 → RED" — the 0.2 s flow pairs read the clearing crowd as turbulent
  (inferred from the level logic; turbulence isn't logged in the state). Over-warning, the safe direction; stated, not
  changed.

*Demo-only, not danger:* a normal busy crossing (~1 person/m²) is GREEN by Fruin, which is correct. To make the clip
walk through every level:
- crowd_06 (Day 2–5): `crowd.levels_ppm2` = real × 0.15 (0.30 / 0.60 / 0.75), `hysteresis_ppm2` 0.06
- crowd_06: `crowd.rise_ppm2_per_min` 0.15, `rise_min_density` 0.3 — the rise rule scaled the same × 0.15, so the demo shows
  `DENSITY_RISING` before ORANGE
- **crowd_07 (Day 6):** one factor, real × 0.085 — levels 0.17 / 0.34 / 0.425, `hysteresis_ppm2` 0.034,
  `rise_ppm2_per_min` 0.085, `rise_min_density` 0.17. The demo run reads 0.13 → 0.46 → 0.23 /m² (the crowd_06 values
  would peak at YELLOW). An offline replay of those densities through `level_for` (no turbulence rule) gives GREEN →
  YELLOW 2.0 s → ORANGE 10.5 s → RED 14.5 s → ORANGE 28.6 s → YELLOW 35.6 s; to be confirmed on the dashboard. Set
  after the held-out check; the demo run's counts were not compared with the ground truth.

Anything shown from this camera must say it runs on demo thresholds — the overlay and dashboard show a red
"DEMO THRESHOLDS" line automatically (ARCHITECTURE §2.1, §2.12).

> **Real disasters — footage vs location.** Never use real disaster footage (e.g. Itaewon) in data, demos or tests
> (CLAUDE.md hard rule, unchanged). **User decision (Day 6):** the demo *location* may be Itaewon — the dashboard map and
> the simulated camera positions sit around Itaewon Station — on these conditions:
> - all footage stays stock or public research footage from elsewhere; every camera is labeled "stock clip (<source>),
>   demo position" (crowd_07: "CroHD HT21-03 (MOTChallenge, CC BY-NC-SA 3.0), demo position")
> - the 2022 event itself is not shown, re-enacted or replayed in the demo. **Landing-page story (user decision, Day 6,
>   "Our own illustrations + licensed photos"):** the landing page may tell what happened and why, with cited facts
>   (deaths, alley width, measured density, the official findings) and licensed photos taken **after** the event —
>   memorials and Seoul's later AI people-counting system. Never: photos or video from the night, the scene in its
>   aftermath (debris), Google / news images, legible victims' names or personal messages, count-up or playful motion
>   on the facts, or a diagram or animation that models the Itaewon alley filling up (that would be a re-enactment;
>   density diagrams stay generic). Wording stays honest: "built to give staff minutes back", never "would have
>   prevented it" or "saves lives" as a claim, plus the limit that on dense real CCTV it counts about half the people.
>   Each photo keeps its licence: CC BY-SA images credited (author, licence, link); the KOGL Type 4 image (출처표시 +
>   상업적 이용금지 + 변경금지) served byte-identical, shown whole (no crop or overlay), non-commercial, credited.
>   Files in `dashboard/public/landing/` with `CREDITS.md`; the project's AGPL-3.0 licence doesn't cover them.
> - demo thresholds keep their DEMO tag, so a demo RED is never presented as a real reading of Itaewon
> - **camera positions** (user decision, Day 6): one camera at the alley entrance on Itaewon-ro (Exit 1) — on the main
>   road, **not inside the alley** — and the others on the nearest busy streets. The alley-entrance camera runs a
>   real-threshold clip (test_crowd_03 — real thresholds, counting overrides only (NWPU + switch 0, Day 6), ~0.24
>   people/m² by eye, stays GREEN, no DEMO tag); the demo RED
>   (crossing_demo) is placed elsewhere, so a demo RED never shows at the site
>
> (This replaces the earlier "mention the event in the problem statement only": the event still isn't shown, but the
> location is used.)

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
├── processed/    extracted frames, crowd_levels.csv, crowd_07_heads.txt (CroHD HT21-03 ground truth)
├── snapshots/    event snapshots (blurred) written by the pipeline
└── recordings/   replay-mode runs, one folder per camera: blurred video, timeline, snapshots, manifest (ARCHITECTURE §2.11)
```
