"""What the user asked for, and the search query each section sends."""

from __future__ import annotations

import re
from dataclasses import dataclass

from talkfollow.models import Section

# Titles this long are treated as a talk title and searched as an exact phrase.
TALK_TITLE_MIN_WORDS = 4
MIN_SIGNIFICANT_WORD_LENGTH = 3

_STOPWORDS_TEXT = """
    about after again also and are back been being but can could does doing down for from
    get gets got had has have her here him his how into its just like more most much new
    not now off one only our out over own same she should some such than that the their
    them then there these they this those through too under until use used using very
    was way were what when where which while who why will with would you your age era
    talk talks intro introduction part
"""
STOPWORDS = frozenset(_STOPWORDS_TEXT.split())


def significant_words(text: str) -> set[str]:
    """Lowercase content words, so "AI-fatigue" gives {"fatigue"} and drops filler."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= MIN_SIGNIFICANT_WORD_LENGTH and w not in STOPWORDS}


@dataclass(frozen=True)
class TalkQuery:
    title: str
    speaker: str | None = None
    keywords: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _clean(self.title))
        object.__setattr__(self, "speaker", _clean(self.speaker) or None)
        object.__setattr__(self, "keywords", _clean(self.keywords) or None)
        if not self.title:
            raise ValueError("A talk title or topic is required.")

    @property
    def is_talk(self) -> bool:
        return len(self.title.split()) >= TALK_TITLE_MIN_WORDS

    @property
    def topic(self) -> str:
        return self.keywords or self.title

    @property
    def title_words(self) -> set[str]:
        return significant_words(self.title)

    @property
    def topic_words(self) -> set[str]:
        return significant_words(self.topic)

    def for_section(self, section: Section) -> str:
        if section is Section.WEB:
            phrase = f'"{self.title}"' if self.is_talk else self.title
            return f"{phrase} {self.speaker}" if self.speaker else phrase
        return self.topic


def _clean(value: str | None) -> str:
    return " ".join(value.split()) if value else ""
