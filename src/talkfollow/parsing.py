"""Turn each engine's SerpApi JSON into ``Source`` objects. Pure functions, no I/O."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any

from talkfollow.models import Source

# Google News groups coverage of one story into a cluster; keep only its lead articles.
MAX_STORIES_PER_CLUSTER = 2

# Absolute dates as Google shows them next to web results, e.g. "18 Sept 2024", "Sep 18, 2024".
WEB_DATE_FORMATS = ("%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y")


def web_sources(payload: Mapping[str, Any]) -> list[Source]:
    return [
        Source(
            title=clean_text(item.get("title")),
            link=_link(item),
            snippet=clean_text(item.get("snippet")),
            publisher=clean_text(item.get("source")),
            published=format_web_date(item.get("date")),
        )
        for item in _items(payload, "organic_results")
    ]


def news_sources(payload: Mapping[str, Any]) -> list[Source]:
    sources: list[Source] = []
    for item in _items(payload, "news_results"):
        stories = list(_items(item, "stories"))[:MAX_STORIES_PER_CLUSTER] or [item]
        sources.extend(
            Source(
                title=clean_text(story.get("title")),
                link=_link(story),
                snippet=clean_text(story.get("snippet")),
                publisher=_name(story.get("source")),
                published=format_news_date(story),
            )
            for story in stories
        )
    return sources


def video_sources(payload: Mapping[str, Any]) -> list[Source]:
    return [
        Source(
            title=clean_text(item.get("title")),
            link=_link(item),
            snippet=clean_text(item.get("description")),
            publisher=_name(item.get("channel")),
            published=clean_text(item.get("published_date")),
            details=_video_details(item),
        )
        for item in _items(payload, "video_results")
    ]


def answer_text(payload: Mapping[str, Any]) -> str:
    box = payload.get("answer_box")
    if isinstance(box, Mapping):
        return clean_text(box.get("answer") or box.get("snippet") or box.get("result"))
    graph = payload.get("knowledge_graph")
    if isinstance(graph, Mapping):
        return clean_text(graph.get("description"))
    return ""


def related_questions(payload: Mapping[str, Any]) -> list[str]:
    questions = (clean_text(item.get("question")) for item in _items(payload, "related_questions"))
    return [question for question in questions if question]


def format_news_date(item: Mapping[str, Any]) -> str:
    """Prefer ``iso_date`` and show it as "2 Sep 2026"; the plain ``date`` is US-ordered."""
    for key, parse in (("iso_date", _parse_iso), ("date", _parse_us_date)):
        value = item.get(key)
        if isinstance(value, str) and value:
            parsed = parse(value)
            if parsed:
                return _display_date(parsed)
    return clean_text(item.get("date"))


def format_web_date(value: Any) -> str:
    """Show absolute dates as "18 Sep 2024"; keep relative ones like "5 days ago" as they are."""
    text = clean_text(value)
    normalised = text.replace("Sept ", "Sep ")
    for date_format in WEB_DATE_FORMATS:
        try:
            return _display_date(datetime.strptime(normalised, date_format))
        except ValueError:
            continue
    return text


def clean_text(value: Any) -> str:
    return " ".join(str(value).split()) if value else ""


def _display_date(value: datetime) -> str:
    return f"{value.day} {value:%b %Y}"


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_us_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.split(",")[0].strip(), "%m/%d/%Y")
    except ValueError:
        return None


def _video_details(item: Mapping[str, Any]) -> str:
    views = item.get("views")
    parts = [
        clean_text(item.get("length")),
        f"{views:,} views" if isinstance(views, int) else "",
    ]
    return " · ".join(part for part in parts if part)


def _items(payload: Mapping[str, Any], key: str) -> Iterator[Mapping[str, Any]]:
    value = payload.get(key)
    if isinstance(value, list):
        yield from (item for item in value if isinstance(item, Mapping))


def _link(item: Mapping[str, Any]) -> str:
    link = item.get("link")
    return link.strip() if isinstance(link, str) else ""


def _name(value: Any) -> str:
    if isinstance(value, Mapping):
        return clean_text(value.get("name") or value.get("title"))
    return clean_text(value)
