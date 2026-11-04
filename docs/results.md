# Results

## Crowd counting (Day 2)

Full-image inference on Apple MPS, `scripts/eval_crowd.py`. The paper reports SH-B 7.4 / 11.8 and SH-A 59.7 / 95.7,
so the re-declared model and the authors' weights reproduce it.

| Dataset | Model | MAE | RMSE |
|---|---|---|---|
| ShanghaiTech B test (316 images) | DM-Count SH-B (authors' weights) | 7.34 | 11.82 |
| ShanghaiTech A test (182 images) | DM-Count SH-A (authors' weights) | 59.60 | 95.58 |

## Crowd levels and counts (Day 4, labeled crowd videos)

`scripts/eval_crowd.py --levels`. **Ground truth:** people in each zone counted by eye on zoomed grid cells of the
window's midpoint frame, by the developer agent (not the developer), without looking at the system's output; the
developer spot-checks the densest frames and one held-out window. Label level = count ÷ zone area by the thresholds
of that run. Labels and system share the zone area, so this tests **counting**, not calibration (±20% area).

**Spot-check** of the labels by the developer (counted independently, before seeing the agent's numbers):

| Frame | Developer | Agent label | Difference |
|---|---|---|---|
| crowd_02 at 15 s | 20 | 23 | +3 (+15%) |
| crowd_06 at 15 s (densest) | 78 | 69 | −9 (−12%) |
| crowd_04 at 5 s (held-out) | 58 | 63 | +5 (+9%) |

The two counters differ by 8–15% in both directions, so the labels carry about ±15% counting noise of their own; no
clear bias in these 3 checks (too few to rule one out). The labels were kept as counted (not swapped after the fact).

**Tuning set** (crowd_02 + crowd_06, real thresholds — 12 windows, 44 s of footage):

| Video | Windows | Level accuracy | Off by > 1 level | Count MAE (mean error) |
|---|---|---|---|---|
| crowd_02 (station square, detection count) | 2 × 10 s | 2 / 2 | 0 | 6.5 (−6.5): 13 vs 17, 14 vs 23 |
| crowd_06 (crossing from above, density count) | 10 × 2 s | 10 / 10 | 0 | 3.4 (+1.0) |
| **all** | 12 | **100%** | 0 | **3.9 (−0.3)** |

The 100% is **trivial**: every window is GREEN by label and by system (stock footage stays below 2 people/m²). It
shows only that nothing is raised at low density. crowd_02's detection count misses people in an occluded group at
a stall.

**Held-out set** (crowd_03 + crowd_04, real thresholds, no overrides, run **once** after tuning — 2 windows, 23 s):

| Video | Windows | Level accuracy | Count by eye | System count |
|---|---|---|---|---|
| crowd_03 (plaza from above, 269 m²) | 1 × 10 s | 1 / 1 | 65 | 9 |
| crowd_04 (same plaza, other angle, 313 m²) | 1 × 10 s | 1 / 1 | 63 | 17 |
| **all** | 2 | 100% (trivial, all GREEN) | | **MAE 51.0 (−51.0, about −80%)** |

**Held-out finding:** the count fails on high, wide views. The switch rule (§2.2) uses the detection count below
2.5 people/m², and from this height YOLO finds 1 in 4–7 people. The test cameras were set up with no camera
properties. *Diagnostic after the held-out run (not a result, nothing was changed):* the density models on the same
two frames count SH-B 24 / 18, SH-A 51 / 35, **NWPU 72 / 56** (by eye 65 / 63). So high, top-down cameras need the
camera properties crossing_demo has — `switch_density_ppm2: 0` and NWPU weights — as part of camera setup.

**Held-out on real CCTV (Day 6)** — crowd_07 = CroHD HT21-03, a fixed elevated camera over a crowded crossing
(1920×1080, 40 s), labelled heads from the dataset. Real thresholds, camera properties NWPU + switch 0, zone
223.7 m². Protocol fixed and recorded before the run (ARCHITECTURE §5), run **once**. Label = ground-truth pedestrian
heads whose estimated foot point is inside the zone, at each window's midpoint frame. Pedestrian = class 1; class 4
is left out as "Ignore" (inferred from the class order in the CroHD paper), which changed 3 windows by −1.

| Window | 0–5 s | 5–10 | 10–15 | 15–20 | 20–25 | 25–30 | 30–35 | 35–40 |
|---|---|---|---|---|---|---|---|---|
| Label (people in zone) | 71 | 138 | 208 | 243 | 216 | 161 | 123 | 86 |
| System count | 46.3 | 74.7 | 91.9 | 97.7 | 113.9 | 86.9 | 73.6 | 51.4 |
| System ÷ label | 0.65 | 0.54 | 0.44 | 0.40 | 0.53 | 0.54 | 0.60 | 0.60 |

Level accuracy 8 / 8 (**trivial**: the crowd peaks at about 1.1 people/m², GREEN on real thresholds), no false
alarms in 40 s. **Count MAE 76.2, mean error −76.2: about −49% of the mean label (155.8).**

**Finding:** on real CCTV the system follows the build-up and the clearing, but counts about half the people, and
the gap grows with the crowd (0.65 of the label at 71 people, 0.40 at 243), likely occlusion in the densest part (the
cause is not measured). The system's peak comes 5 s later than the label's (the 5 s median smoothing). So an absolute
people/m² reading from this camera is low by about a factor of 2, which matters for real thresholds. The shape over
time holds, but DENSITY_RISING compares a people/m² per minute rate with a fixed threshold, so a half count also
halves the rise rate and the rule fires late. Only the flow rules (speed, turbulence, counter-flow) don't depend on
the count.

Limits: the ground truth includes partly occluded heads, so it counts more than any camera can see; zone membership
near the edge depends on the foot-point estimate; one camera, 40 s. The density reading (count ÷ area) also carries the
area uncertainty of this calibration (about ±30%), which the count comparison above does not.

## Alerts (Day 4)

Stock footage has no real level changes, so alert timing is measured on **crossing_demo with its DEMO thresholds**
(0.30 / 0.60 / 0.75 people/m², 0.15 × real): 10 windows of 2 s, 22 s of footage, 3 labeled changes (YELLOW from the
start, ORANGE at 7 s, RED at 11 s). Time-to-alert has **2 s window resolution** (the change is placed at the midpoint
of the first window at the new level).

| Metric | Before tuning (`turbulence_red` 0.6) | After tuning (0.8) |
|---|---|---|
| Level accuracy, demo thresholds (10 windows) | 70% | 60% |
| Level-change events per labeled change (target ≈ 1) | 0.67 (ORANGE skipped: turbulence → RED) | **1.00** |
| Mean time-to-alert after labeled change | +1.7 s (+2.0, +3.5, −0.5) | **+2.7 s** (+2.0, +3.5, +2.5) |
| Off by > 1 level | 0 | 0 |

Misses are the 5 s median smoothing lagging a crowd that fills in ~10 s.

**False alarms** (ORANGE/RED on GREEN/YELLOW-labeled time): **0** in 89 s of runs (44 s tuning + 23 s held-out at real
thresholds, plus crowd_06 again on demo thresholds, 22 s) — 67 s of distinct footage. That is about a minute, not
hours, so no per-hour rate is claimed.
