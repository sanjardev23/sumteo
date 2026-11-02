"""Day 5 — FastAPI: cameras, MJPEG stream, events, ack, metrics, WebSocket.

Run: uvicorn sumteo.api.server:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Sumteo")


@app.get("/health")
def health() -> dict:
    return {"ok": True}

# TODO(Day 5):
#   GET  /cameras
#   GET  /cameras/{camera_id}/stream      MJPEG (multipart/x-mixed-replace)
#   GET  /events?camera=&severity=
#   POST /events/{event_id}/ack
#   GET  /metrics/{camera_id}?since=
#   WS   /ws                              push events + metrics
