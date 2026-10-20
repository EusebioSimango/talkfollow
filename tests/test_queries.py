import pytest

from talkfollow.models import Section
from talkfollow.queries import TalkQuery, significant_words


def test_talk_title_is_searched_as_exact_phrase_with_speaker(talk_query):
    assert talk_query.is_talk
    assert talk_query.for_section(Section.WEB) == (
        '"Ramping up agentic engineering in the age of AI-fatigue" Alex'
    )


def test_keywords_drive_news_and_video_searches(talk_query):
    assert talk_query.for_section(Section.NEWS) == "agentic engineering"
    assert talk_query.for_section(Section.VIDEOS) == "agentic engineering"


def test_short_topic_is_not_quoted_and_is_used_everywhere():
    query = TalkQuery("  asyncio  ")

    assert not query.is_talk
    assert {query.for_section(section) for section in Section} == {"asyncio"}


def test_blank_values_are_treated_as_missing():
    query = TalkQuery("asyncio", speaker="  ", keywords="")

    assert query.speaker is None and query.keywords is None


def test_title_is_required():
    with pytest.raises(ValueError):
        TalkQuery("   ")


def test_significant_words_drop_filler_and_split_hyphens():
    assert significant_words("Ramping up agentic engineering in the age of AI-fatigue") == {
        "ramping",
        "agentic",
        "engineering",
        "fatigue",
    }
