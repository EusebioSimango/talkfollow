"""Plain data shared by the search, briefing and rendering steps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class Section(str, Enum):
    """One SerpApi search per section, always shown in this order."""

    WEB = "web"
    NEWS = "news"
    VIDEOS = "videos"

    @property
    def engine_label(self) -> str:
        return {
            Section.WEB: "Google Light",
            Section.NEWS: "Google News",
            Section.VIDEOS: "YouTube",
        }[self]

    @property
    def label(self) -> str:
        return {Section.WEB: "Web", Section.NEWS: "News", Section.VIDEOS: "Videos"}[self]


@dataclass(frozen=True)
class SectionResult:
    """What one SerpApi search returned, or why it failed."""

    section: Section
    query: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Source:
    """One cited result in the briefing."""

    title: str
    link: str
    snippet: str = ""
    publisher: str = ""
    published: str = ""
    details: str = ""

    @property
    def domain(self) -> str:
        return urlparse(self.link).netloc.removeprefix("www.")


@dataclass(frozen=True)
class SearchRecord:
    """The query sent for a section and how it went, for the briefing footer."""

    section: Section
    query: str
    result_count: int
    error: str | None = None


@dataclass
class Briefing:
    title: str
    speaker: str | None
    keywords: str | None
    briefing_date: date
    is_talk: bool
    answer: str = ""
    about_talk: list[Source] = field(default_factory=list)
    related_reading: list[Source] = field(default_factory=list)
    news: list[Source] = field(default_factory=list)
    videos: list[Source] = field(default_factory=list)
    related_questions: list[str] = field(default_factory=list)
    searches: list[SearchRecord] = field(default_factory=list)
    hidden_off_topic: int = 0

    @property
    def source_count(self) -> int:
        return len(self.about_talk) + len(self.related_reading) + len(self.news) + len(self.videos)

    @property
    def all_searches_failed(self) -> bool:
        return bool(self.searches) and all(record.error for record in self.searches)

    def search_for(self, section: Section) -> SearchRecord | None:
        return next((r for r in self.searches if r.section is section), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
