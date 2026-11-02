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
python scripts/run_camera.py --camera configs/cameras/crowd_demo.yaml
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
scripts/            run_camera, calibrate, eval_crowd
dashboard/          Next.js (Day 5)
data/  models/      git-ignored
```

## Status
Day 0: skeleton and architecture.

Bridge mode (railing / climbing detection) was split out and is kept in `../bridge-safety-ai/`.
