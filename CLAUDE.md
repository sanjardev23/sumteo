# CLAUDE.md

**숨터 Sumteo** — AI crowd-safety early warning system (Python package `sumteo`). Crowd-crush early warning from video. Per camera zone: count people, compute people/m² and crowd-flow
turbulence, raise GREEN → YELLOW → ORANGE → RED alerts in time for staff to act. Crowd only — bridge mode
was split out to `../bridge-safety-ai/`; do not bring it back here.

## Source of truth
- `docs/ARCHITECTURE.md` — what the system does: layers, metrics, rules, thresholds, API.
- `docs/PLAN.md` — the 6-day plan with checkboxes. "Start day N" means: read PLAN.md + ARCHITECTURE.md, then work through
  that day's checkboxes in order. A Day is finished only when its **"Done when"** passes.
- `docs/DATA.md` — datasets, labeling format, folder layout.
- New ideas or rules: agree on them with the user, write them into ARCHITECTURE.md / PLAN.md **first**, then code them.
- If the code and the docs disagree, stop and ask which one is right. Don't silently pick one.
- No calendar dates in docs, journal or code comments. Refer to time by plan day ("Day 4"), never "Nov 10".

## Commands
```bash
uv venv --python 3.12 && source .venv/bin/activate && uv pip install -e ".[dev]"   # setup
pytest                                                                              # tests
python scripts/run_camera.py --camera configs/cameras/crowd_demo.yaml [--save out.mp4] [--no-window]
python scripts/calibrate.py --camera configs/cameras/crowd_demo.yaml
python scripts/eval_crowd.py ...                                                    # see the script docstring
```

## Hard rules
- **Thresholds live in config only.** Real values go in `configs/default.yaml`. Demo-only values go under `overrides:` in
  `configs/cameras/*_demo.yaml` and must never leak into the defaults. No magic numbers in analyzers.
- **Privacy:** face *detection* only, to blur. Never face recognition, never store identities. Snapshots are blurred
  before they are saved, pushed to KakaoTalk or sent to a VLM. Raw video is not stored by default.
- **The VLM check only annotates.** It never suppresses or downgrades a CRITICAL alert; a human always sees it.
- **Thresholds are research-based (Fruin), not Seoul's official numbers** — never claim they are.
- **No real disaster footage** (e.g. Itaewon) in data, demos or tests. Use stock crowd videos.
- **Honest results:** `docs/results.md` gets only numbers that were actually measured. Held-out videos are run once, after tuning.
- `data/` and `models/` are git-ignored; never commit datasets, videos or weights.
- Ultralytics is AGPL. Keep it behind `PersonTracker` (`perception/detector.py`) so the detector can be swapped in one file.

## Code conventions (match the existing skeleton)
- Python 3.12. `from __future__ import annotations` at the top of every module.
- Every module docstring starts with the Day that builds it: `"""Day 3 — ..."""`.
- Unbuilt parts are stubs: `# TODO(Day N): ...` + `raise NotImplementedError("Day N")`. Replace a stub when its Day comes; don't build ahead.
- `@dataclass` for runtime data (`Frame`, `Detection`, `CrowdMetrics`, `Condition`, `Event`); Pydantic only in `config.py`.
  Config sections stay plain dicts until a module needs typed fields.
- Analyzers return `Condition`s; only `RuleEngine` turns them into `Event`s (debounce, cooldown, escalation).
- File sources take timestamps from the frame index (not the wall clock), so runs are reproducible.
- Metric units: meters, m/s, people/m² — via the camera's homography. Pixels never go into thresholds.
- Small, focused modules; comments only where the *why* isn't obvious.

## Testing
- Unit-test logic without models or video: zones, homography, `CrowdAnalyzer.level_for` (incl. risk factors, hysteresis),
  every rule in ARCHITECTURE §2.6, `RuleEngine` (flicker doesn't fire, cooldown blocks repeats, escalation fires,
  combined alerts, all-clear). Feed fake metric sequences — stock videos rarely show real danger.
- Model-dependent checks (MAE, level accuracy) are scripts in `scripts/`, not pytest.
- Run `pytest` before saying a Day is done.

## End of each Day
1. The Day's "Done when" passes (say how you checked it) and `pytest` passes.
2. Commit — only after the developer approves the message.
3. Write `docs/journal/day-N.md` (local only, git-ignored — never stage it): done (3–5 lines), deferred, and the day's
   3 interview questions from PLAN.md with short answers.
4. Tick the day's checkboxes in `docs/PLAN.md` and update `README.md` → Status.
