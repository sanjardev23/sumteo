"""Day 6 — Seoul city data (ARCHITECTURE §2.13): parsing, off without a key, errors never leak the key."""
import asyncio

import httpx
import pytest

from sumteo.city.seoul import CityData, parse

ANSWER = {"SeoulRtd.citydata_ppltn": [{
    "AREA_NM": "이태원 관광특구", "AREA_CD": "POI012", "AREA_CONGEST_LVL": "약간 붐빔",
    "AREA_CONGEST_MSG": "사람이 몰려있을 수 있어요.", "AREA_PPLTN_MIN": "12000", "AREA_PPLTN_MAX": "14000",
    "PPLTN_TIME": "2026-11-05 21:20"}]}
CFG = {"enabled": True, "area": "이태원 관광특구", "poll_seconds": 300}


def test_parse_keeps_the_label_range_and_time():
    city = parse(ANSWER)
    assert city["level_ko"] == "약간 붐빔" and city["level_en"] == "Slightly crowded"
    assert (city["people_min"], city["people_max"]) == (12000, 14000)
    assert city["measured_at"] == "2026-11-05 21:20"


def test_parse_raises_on_an_error_answer():
    with pytest.raises(ValueError, match="인증키"):
        parse({"RESULT": {"RESULT.CODE": "INFO-100", "RESULT.MESSAGE": "인증키가 유효하지 않습니다."}})


def test_off_without_key_or_area():
    assert CityData(CFG, None).view()["status"] == "off"
    assert CityData({**CFG, "area": ""}, "k").view()["status"] == "off"
    assert CityData({**CFG, "enabled": False}, "k").view()["status"] == "off"


def _poll(city: CityData, handler) -> None:
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await city.poll_once(client)
    asyncio.run(go())


def test_poll_keeps_the_last_good_answer_and_never_shows_the_key():
    city = CityData(CFG, "SECRET-KEY")
    assert city.view()["status"] == "waiting"
    _poll(city, lambda request: httpx.Response(200, json=ANSWER))
    assert city.view()["status"] == "ok" and city.view()["level_en"] == "Slightly crowded"

    def down(request):
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)
    _poll(city, down)
    view = city.view()
    assert view["status"] == "ok" and view["level_ko"] == "약간 붐빔" and view["error"] == "ConnectError"
    assert "SECRET-KEY" not in str(view)
