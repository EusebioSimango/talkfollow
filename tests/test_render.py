from datetime import date

from talkfollow.briefing import build_briefing
from talkfollow.models import Section
from talkfollow.queries import TalkQuery
from talkfollow.render import render_markdown
from talkfollow.search import TalkSearcher


def render(client, query, sections=tuple(Section)):
    results = TalkSearcher(client).run(query, sections)
    return render_markdown(build_briefing(query, results, today=date(2026, 10, 20)))


def test_header_and_summary(fake_client, talk_query):
    text = render(fake_client, talk_query)

    assert text.startswith("# Ramping up agentic engineering in the age of AI-fatigue\n")
    assert (
        "**Speaker:** Alex · **Keywords:** agentic engineering · **Briefing date:** 20 Oct 2026"
        in text
    )
    assert (
        "> 7 sources from 3 SerpApi searches: 2 about this talk, 1 related reading, "
        "3 news, 1 video." in text
    )


def test_sections_are_in_reading_order(fake_client, talk_query):
    text = render(fake_client, talk_query)
    headings = [line for line in text.splitlines() if line.startswith("## ")]

    assert headings == [
        "## In one line",
        "## About this talk",
        "## Related reading",
        "## In the news",
        "## Talks and videos",
        "## Questions people also ask",
    ]


def test_source_lines_skip_publisher_already_in_title(fake_client, talk_query):
    text = render(fake_client, talk_query)

    assert (
        "1. **[Schedule - conf.example.org](https://conf.example.org/schedule/)** — 5 days ago"
        in text
    )
    assert (
        "**[Teams report agentic engineering gains](https://news.example.com/agentic-gains)**"
        " — Example News · 2 Sep 2026"
    ) in text


def test_empty_section_explains_itself_once(fake_client, talk_query):
    fake_client.responses["youtube"] = {
        "error": "Youtube hasn't returned any results for this query."
    }
    text = render(fake_client, talk_query)

    assert "_Nothing on topic found for `agentic engineering`._" in text
    assert text.count("hasn't returned any results") == 0


def test_failed_search_says_why(fake_client, talk_query):
    fake_client.responses["google_news"] = {"error": "Invalid API key."}
    text = render(fake_client, talk_query)

    assert "_Google News search failed: Invalid API key._" in text
    assert "| News | Google News | `agentic engineering` | Failed: Invalid API key. |" in text


def test_footer_lists_searches_and_hidden_results(fake_client, talk_query):
    text = render(fake_client, talk_query)

    assert "### Searches used" in text
    assert (
        '| Web | Google Light | `"Ramping up agentic engineering in the age of AI-fatigue" Alex`'
        " | 5 |"
    ) in text
    assert "2 off-topic results hidden" in text


def test_skipped_sections_are_not_shown(fake_client, talk_query):
    text = render(fake_client, talk_query, [Section.WEB])

    assert "In the news" not in text and "Talks and videos" not in text
    assert "from 1 SerpApi search:" in text


def test_short_topic_uses_background_reading(fake_client):
    text = render(fake_client, TalkQuery("agentic engineering"), [Section.WEB])

    assert "## Background reading" in text
    assert "About this talk" not in text
