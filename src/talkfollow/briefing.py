"""Assemble a briefing: deduplicate sources and keep only what is on topic."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from talkfollow import parsing
from talkfollow.models import Briefing, SearchRecord, Section, SectionResult, Source
from talkfollow.queries import TalkQuery, significant_words

# A web result is "about this talk" when it contains this share of the title's words.
ABOUT_TALK_MATCH_RATIO = 0.6

_PARSERS: dict[Section, Callable[[Mapping[str, Any]], list[Source]]] = {
    Section.WEB: parsing.web_sources,
    Section.NEWS: parsing.news_sources,
    Section.VIDEOS: parsing.video_sources,
}


def build_briefing(
    query: TalkQuery,
    results: Mapping[Section, SectionResult],
    *,
    today: date | None = None,
) -> Briefing:
    web_payload = results[Section.WEB].payload if Section.WEB in results else {}

    about_talk, other_web = _split_about_talk(_sources(results, Section.WEB), query)
    related_reading, hidden_web = _on_topic(other_web, query)
    news, hidden_news = _on_topic(_sources(results, Section.NEWS), query)
    videos, hidden_videos = _on_topic(_sources(results, Section.VIDEOS), query)

    return Briefing(
        title=query.title,
        speaker=query.speaker,
        keywords=query.keywords,
        briefing_date=today or date.today(),
        is_talk=query.is_talk,
        answer=parsing.answer_text(web_payload),
        about_talk=about_talk,
        related_reading=related_reading,
        news=news,
        videos=videos,
        related_questions=parsing.related_questions(web_payload),
        searches=[_record(result) for result in results.values()],
        hidden_off_topic=hidden_web + hidden_news + hidden_videos,
    )


def _sources(results: Mapping[Section, SectionResult], section: Section) -> list[Source]:
    result = results.get(section)
    return _dedupe(_PARSERS[section](result.payload)) if result else []


def _split_about_talk(sources: list[Source], query: TalkQuery) -> tuple[list[Source], list[Source]]:
    if not query.is_talk or not query.title_words:
        return [], sources
    about: list[Source] = []
    other: list[Source] = []
    for source in sources:
        shared = query.title_words & _words(source)
        is_about = len(shared) / len(query.title_words) >= ABOUT_TALK_MATCH_RATIO
        (about if is_about else other).append(source)
    return about, other


def _on_topic(sources: list[Source], query: TalkQuery) -> tuple[list[Source], int]:
    """Keep results sharing a topic word; returns them and how many were hidden.

    This drops results that only match the speaker's name, a common miss for first names.
    """
    topic_words = query.topic_words
    if not topic_words:
        return sources, 0
    kept = [source for source in sources if topic_words & _words(source)]
    return kept, len(sources) - len(kept)


def _words(source: Source) -> set[str]:
    return significant_words(f"{source.title} {source.snippet} {source.link}")


def _dedupe(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    unique: list[Source] = []
    for source in sources:
        if source.title and source.link and source.link not in seen:
            seen.add(source.link)
            unique.append(source)
    return unique


def _record(result: SectionResult) -> SearchRecord:
    count = len(_PARSERS[result.section](result.payload))
    return SearchRecord(result.section, result.query, count, result.error)
