"""Run the web, news and YouTube searches in parallel through serpapi-search-tools."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

from serpapi_search_tools import (
    SearchResultFormat,
    SerpApiSearchError,
    news_search,
    videos_search,
    web_search,
)

from talkfollow.budget import BudgetedClient, SearchClient, SearchFailed
from talkfollow.models import Section, SectionResult
from talkfollow.queries import TalkQuery

MAX_SEARCHES_PER_RUN = 3
DEFAULT_RESULT_LIMIT = 5

# SerpApi reports an empty result page through the "error" field with this wording.
_NO_RESULTS_MARKER = "hasn't returned any results"


def official_client(api_key: str, timeout: float = 30.0) -> SearchClient:
    import serpapi

    return serpapi.Client(api_key=api_key, timeout=timeout)


class TalkSearcher:
    def __init__(
        self,
        client: SearchClient,
        *,
        country: str = "za",
        language: str = "en",
        result_limit: int = DEFAULT_RESULT_LIMIT,
        max_searches: int = MAX_SEARCHES_PER_RUN,
    ) -> None:
        self._client = BudgetedClient(client, max_calls=max_searches)
        options = {
            "provider": "function",
            "client": self._client,
            "response_format": SearchResultFormat.JSON,
            "result_limit": result_limit,
            "default_params": {"gl": country, "hl": language},
        }
        self._tools: dict[Section, Callable[..., str]] = {
            Section.WEB: web_search(
                allowed_engines=["google_light"], default_engine="google_light", **options
            ),
            Section.NEWS: news_search(**options),
            Section.VIDEOS: videos_search(**options),
        }

    @property
    def engines_called(self) -> list[str]:
        return self._client.engines_called

    def run(
        self, query: TalkQuery, sections: Iterable[Section] = tuple(Section)
    ) -> dict[Section, SectionResult]:
        """Search every requested section at once; results come back in Section order."""
        wanted = set(sections)
        ordered = [section for section in Section if section in wanted]
        if not ordered:
            return {}
        with ThreadPoolExecutor(max_workers=len(ordered)) as pool:
            futures = {
                section: pool.submit(self._search, section, query.for_section(section))
                for section in ordered
            }
        return {section: futures[section].result() for section in ordered}

    def _search(self, section: Section, query: str) -> SectionResult:
        try:
            payload = json.loads(self._tools[section](query=query))
        except SerpApiSearchError as exc:
            return SectionResult(section, query, error=_failure_message(exc))
        error = str(payload.get("error") or "")
        if _NO_RESULTS_MARKER in error:
            return SectionResult(section, query, payload)
        return SectionResult(section, query, payload, error or None)


def _failure_message(exc: BaseException) -> str:
    # serpapi-search-tools re-raises custom-client errors as a generic SerpApiSearchError
    # (`from None`), but Python still keeps the original exception in __context__.
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, SearchFailed):
            return str(current)
        current = current.__cause__ or current.__context__
    return str(exc)
