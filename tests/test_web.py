from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import TALK_TITLE
from talkfollow import web
from talkfollow.limits import BriefingCache, DemoLimits, LimitReached

BRIEF = {"title": TALK_TITLE, "speaker": "Alex", "keywords": "agentic engineering"}


def demo(fake_client, *, daily_briefings=10):
    return TestClient(web.create_app(lambda: fake_client, daily_briefings=daily_briefings))


def searches(fake_client):
    return len(fake_client.requests)


def test_home_shows_the_form(fake_client):
    page = demo(fake_client).get("/")

    assert page.status_code == 200
    assert '<form action="/brief"' in page.text
    assert searches(fake_client) == 0


def test_brief_renders_the_briefing(fake_client):
    page = demo(fake_client).get("/brief", params=BRIEF)

    assert page.status_code == 200
    assert "<h2>About this talk</h2>" in page.text
    assert 'href="https://conf.example.org/talks/42/"' in page.text
    assert searches(fake_client) == 3


def test_repeat_brief_comes_from_the_cache(fake_client):
    client = demo(fake_client)
    client.get("/brief", params=BRIEF)
    again = client.get("/brief", params={**BRIEF, "title": f"  {TALK_TITLE.upper()} "})

    assert again.status_code == 200
    assert searches(fake_client) == 3


def test_failed_briefings_are_not_cached(fake_client):
    for engine in fake_client.responses:
        fake_client.responses[engine] = {"error": "Invalid API key."}
    client = demo(fake_client)
    client.get("/brief", params=BRIEF)
    client.get("/brief", params=BRIEF)

    assert searches(fake_client) == 6


def test_visitor_limit_returns_429(fake_client):
    client = demo(fake_client, daily_briefings=100)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    for n in range(web.BRIEFINGS_PER_VISITOR_PER_HOUR):
        client.get("/brief", params={"title": f"topic {n}"}, headers=headers)

    page = client.get("/brief", params={"title": "one more"}, headers=headers)
    other_visitor = client.get(
        "/brief", params={"title": "one more"}, headers={"X-Forwarded-For": "198.51.100.2"}
    )

    assert page.status_code == 429
    assert "in the last hour" in page.text
    assert other_visitor.status_code == 200


def test_daily_limit_returns_429(fake_client):
    client = demo(fake_client, daily_briefings=1)
    client.get("/brief", params={"title": "first"})

    page = client.get("/brief", params={"title": "second"})

    assert page.status_code == 429
    assert "Please try again tomorrow" in page.text


@pytest.mark.parametrize(
    "params",
    [
        {"title": "   "},
        {"title": "x" * (web.MAX_TITLE_LENGTH + 1)},
        {"title": "ok", "speaker": "x" * (web.MAX_FIELD_LENGTH + 1)},
    ],
)
def test_invalid_input_returns_400(fake_client, params):
    page = demo(fake_client).get("/brief", params=params)

    assert page.status_code == 400
    assert searches(fake_client) == 0


def test_missing_api_key_returns_503(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    page = TestClient(web.create_app()).get("/brief", params={"title": "asyncio"})

    assert page.status_code == 503


def test_user_input_and_result_html_are_escaped(fake_client):
    fake_client.responses["google_light"]["organic_results"][0]["snippet"] = (
        "<script>alert(1)</script> agentic"
    )
    page = demo(fake_client).get("/brief", params={**BRIEF, "speaker": '"><b>x</b>'})

    assert "<script>" not in page.text
    assert "<b>x</b>" not in page.text


def test_sample_briefing_needs_no_searches(fake_client):
    page = demo(fake_client).get("/example")

    assert page.status_code == 200
    assert "free-threaded Python" in page.text
    assert searches(fake_client) == 0


def test_healthz(fake_client):
    assert demo(fake_client).get("/healthz").text == "ok"


def test_cache_entries_expire():
    now = [0.0]
    cache = BriefingCache(ttl_seconds=10, clock=lambda: now[0])
    cache.put("key", "briefing")
    now[0] = 9
    assert cache.get("key") == "briefing"
    now[0] = 10
    assert cache.get("key") is None


def test_limits_reset_each_hour_and_each_day():
    now, today = [0.0], [date(2026, 10, 20)]
    limits = DemoLimits(
        daily_briefings=2,
        briefings_per_visitor_per_hour=1,
        clock=lambda: now[0],
        today=lambda: today[0],
    )
    limits.reserve("ip")
    with pytest.raises(LimitReached):
        limits.reserve("ip")

    now[0] = 3600
    limits.reserve("ip")
    with pytest.raises(LimitReached):
        limits.reserve("other-ip")

    today[0] = date(2026, 10, 21)
    limits.reserve("other-ip")
