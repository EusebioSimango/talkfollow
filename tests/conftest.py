from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from talkfollow.queries import TalkQuery

FIXTURES = Path(__file__).parent / "fixtures"
TALK_TITLE = "Ramping up agentic engineering in the age of AI-fatigue"


def load_fixture(engine: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{engine}.json").read_text(encoding="utf-8"))


class FakeClient:
    """Stands in for serpapi.Client so tests spend no credits; answers by engine."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {
            engine: load_fixture(engine) for engine in ("google_light", "google_news", "youtube")
        }
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.requests.append(dict(params))
        response = self.responses[params["engine"]]
        if isinstance(response, Exception):
            raise response
        return response

    def request_for(self, engine: str) -> dict[str, Any]:
        return next(r for r in self.requests if r["engine"] == engine)


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def talk_query() -> TalkQuery:
    return TalkQuery(TALK_TITLE, speaker="Alex", keywords="agentic engineering")
