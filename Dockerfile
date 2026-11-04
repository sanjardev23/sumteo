# Day 6 — the API for the replay-only demo (ARCHITECTURE §2.11, §3): plays data/recordings/ with no models, so the
# image has no torch, ultralytics or weights. Live cameras run natively with scripts/serve.py (Docker on a Mac has no MPS).
FROM python:3.12-slim

WORKDIR /app
# The replay path needs only these (pyproject's torch / ultralytics load only in the live worker).
RUN pip install --no-cache-dir opencv-python-headless numpy "pydantic>=2" pyyaml fastapi "uvicorn[standard]" httpx python-dotenv

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY configs ./configs
COPY scripts/serve.py ./scripts/serve.py

EXPOSE 8000
CMD ["python", "scripts/serve.py", "--host", "0.0.0.0", "--replay", \
     "data/recordings/crowd-demo-1", "data/recordings/crossing-demo-1", \
     "data/recordings/test-crowd-03", "data/recordings/test-crowd-04"]
