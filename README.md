# 숨터 Sumteo — AI Crowd Safety Early Warning System

*숨터 — "a place to breathe". 숨터 — AI 인파 안전 조기경보 시스템.*

Video analytics that warns security staff **before** a crowd crush happens (like Itaewon, 2022).
It measures how many people stand in each square meter and how the crowd behaves — stuck, filling up fast,
pushing against itself — and raises 관심 → 주의 → 경계 → 심각 (GREEN → RED) alerts in time to act,
shown in the platform to on-site security or the admin control room depending on severity (optional KakaoTalk push).

Modeled on the AI crowd-monitoring loop Seoul districts built after Itaewon, as an open, measurable
version that runs on one laptop.

Privacy by design: faces are detected only to be blurred; no face recognition, no identities stored.

## Docs
- [Architecture](docs/ARCHITECTURE.md)
- [Data guide](docs/DATA.md)
- [Results](docs/results.md)

## Quick start
```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
pytest
python scripts/run_camera.py --camera configs/cameras/crowd_demo.yaml      # Day 1 demo: tracking, speeds, lines
python scripts/run_camera.py --camera configs/cameras/crossing_demo.yaml   # dense crossing, demo thresholds

# platform: API with both cameras, then the dashboard on http://127.0.0.1:3000
python scripts/serve.py --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml
cd dashboard && npm install && npm run dev
```

## Project layout
```
configs/            default.yaml (real thresholds) + cameras/*.yaml (source, zones, calibration, demo overrides)
src/sumteo/
  video/            VideoSource → Frame
  perception/       detector (YOLO26+ByteTrack), density (DM-Count), optical flow
  geometry/         zones, homography (pixels ↔ meters)
  analytics/        track state, CrowdAnalyzer
  events/           Event model, RuleEngine (debounce/cooldown/escalation), notifiers
  privacy/          face blur
  verify/           optional VLM double-check for CRITICAL events
  storage/          SQLite
  api/              FastAPI + WebSocket + MJPEG
  pipeline.py       per-camera loop
scripts/            run_camera, calibrate, eval_crowd, stabilize_video (stock-clip prep)
dashboard/          Next.js (Day 5)
data/  models/      git-ignored
```

## Status
Day 1 done: video in → YOLO26 + ByteTrack people tracking with stable IDs, calibrated zones and counting lines,
walking speed (m/s), standing time, time in zone and line crossings, drawn live on the video.
Measured on the demo clip: 26.5 FPS, walkers ~1.0 m/s, standing people ~0.1 m/s, zone 148 m².
The demo camera's scale is an estimate (±10%); see `docs/DATA.md` §2.

Day 2 done: people/m² per zone from YOLO counts or the DM-Count density map (whichever fits the crowd),
관심 → 주의 → 경계 → 심각 levels with hysteresis and zone risk factors, and a rule engine that sends exactly one alert per
real change (debounce, cooldown, escalation, all-clear). Measured: DM-Count MAE 7.34 on ShanghaiTech B
(`docs/results.md`). On the dense crossing demo (demo thresholds, marked on screen) the zone rises GREEN → RED in 13.5 s
with one console alert per level.

Day 3 done: optical-flow speed, turbulence and counter-flow per zone, and the rules for a stuck crowd, fast rise,
counter-flow and more-in-than-out, plus camera health (lost / frozen / dark; zones hold their last level during a fault).
Measured: calm footage fires nothing; a paused-then-covered test clip raises one camera alert; line inflow on the demo
clip matches a manual count (5 vs 5), outflow over-counts (11 vs 7–8).

Day 4 done: faces and heads are blurred before anything is shown or saved, every alert is stored in SQLite with a
blurred snapshot, and the system was measured on hand-counted clips (`docs/results.md`). Stock footage is all GREEN by
Fruin, so levels match trivially; on the demo thresholds each level change raises one alert ~2.7 s later. The
held-out clips showed that high, top-down cameras under-count (~80%) unless set up to use the density model.

Day 5 done: alerts reach the people on duty in the platform. A control-room view (live camera grid, a pop-up that stays
until someone acknowledges, alert history, density charts) and a phone view for guards, with sound and browser
notifications; an unanswered CRITICAL is re-sent to the control room as "no response" after 60 s. Measured: a rule
firing reaches both roles in under 1.5 s, and who acknowledged and when is stored.

Next, Day 6: Docker, extras and the demo.

Bridge mode (railing / climbing detection) was split out and is kept in `../bridge-safety-ai/`.
