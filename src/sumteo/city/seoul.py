"""Day 6 — Seoul real-time city data (§2.13): the city's congestion label for one hotspot, shown next to our live level.

data.seoul.go.kr `citydata_ppltn` (free key, `SEOUL_API_KEY`): a 4-step label estimated from mobile signals, updated
every 5 min with ~15 min delay. It is the wider, slower view: it never changes a camera's level or raises an alert."""
from __future__ import annotations

import asyncio
import time
from urllib.parse import quote

import httpx

URL = "http://openapi.seoul.go.kr:8088/{key}/json/citydata_ppltn/1/1/{area}"
LEVEL_EN = {"여유": "Relaxed", "보통": "Normal", "약간 붐빔": "Slightly crowded", "붐빔": "Crowded"}


def parse(payload: dict) -> dict:
    """One `citydata_ppltn` answer → the fields the dashboard shows. Raises ValueError on an error answer."""
    rows = payload.get("SeoulRtd.citydata_ppltn") or []
    if not rows:
        result = payload.get("RESULT") or {}
        raise ValueError(result.get("RESULT.MESSAGE") or "no data for this area")
    row = rows[0]
    level = row.get("AREA_CONGEST_LVL")
    return {"area": row.get("AREA_NM"), "level_ko": level, "level_en": LEVEL_EN.get(level, level),
            "message": row.get("AREA_CONGEST_MSG"), "people_min": _int(row.get("AREA_PPLTN_MIN")),
            "people_max": _int(row.get("AREA_PPLTN_MAX")), "measured_at": row.get("PPLTN_TIME")}


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class CityData:
    """Polls one hotspot every `poll_seconds` while the API runs; `view()` is what GET /city returns."""

    def __init__(self, cfg: dict, key: str | None):
        self.area = cfg.get("area") or ""
        self.poll_s = float(cfg.get("poll_seconds", 300))
        self.key = key or ""
        self.enabled = bool(cfg.get("enabled") and self.key and self.area)
        self.latest: dict | None = None
        self.error: str | None = None
        self.fetched_at: float | None = None

    def view(self) -> dict:
        if not self.enabled:
            return {"status": "off", "area": self.area}
        if self.latest is None:
            return {"status": "error" if self.error else "waiting", "area": self.area, "error": self.error}
        # A failed poll keeps the last good answer, marked with the error, rather than hiding it.
        return {"status": "ok", **self.latest, "fetched_at": self.fetched_at, "error": self.error}

    async def poll_once(self, client: httpx.AsyncClient) -> None:
        try:
            r = await client.get(URL.format(key=quote(self.key, safe=""), area=quote(self.area, safe="")))
            r.raise_for_status()
            self.latest, self.error, self.fetched_at = parse(r.json()), None, time.time()
        except ValueError as e:
            self.error = str(e)
        except httpx.HTTPError as e:
            self.error = type(e).__name__   # never str(e): the request URL holds the key

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                await self.poll_once(client)
                await asyncio.sleep(self.poll_s)
