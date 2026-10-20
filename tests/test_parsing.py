from conftest import load_fixture
from talkfollow import parsing


def test_web_sources_read_organic_results():
    sources = parsing.web_sources(load_fixture("google_light"))

    assert sources[0].title == "Schedule - conf.example.org"
    assert sources[0].published == "5 days ago"
    assert sources[0].domain == "conf.example.org"


def test_news_sources_expand_clusters_and_format_dates():
    sources = parsing.news_sources(load_fixture("google_news"))

    assert [s.title for s in sources] == [
        "Teams report agentic engineering gains",
        "Engineering leaders on agentic tooling",
        "Agentic AI budgets grow",
        "Local football results",
    ]
    assert sources[0].published == "2 Sep 2026"
    assert sources[1].published == "18 Oct 2026"
    assert sources[0].publisher == "Example News"


def test_video_sources_include_channel_length_and_views():
    (video,) = parsing.video_sources(load_fixture("youtube"))

    assert video.publisher == "Example Conf"
    assert video.details == "28:41 · 1,234 views"


def test_answer_and_related_questions():
    payload = load_fixture("google_light")

    assert parsing.answer_text(payload).startswith("Agentic engineering is")
    assert parsing.related_questions(payload) == ["What is agentic engineering?"]


def test_unexpected_shapes_are_ignored():
    assert parsing.web_sources({"organic_results": "oops"}) == []
    assert parsing.news_sources({"news_results": [None, 3]}) == []
    assert parsing.format_news_date({"date": "yesterday"}) == "yesterday"
