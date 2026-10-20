from datetime import date

from talkfollow.briefing import build_briefing
from talkfollow.queries import TalkQuery
from talkfollow.search import TalkSearcher


def make_briefing(client, query):
    return build_briefing(query, TalkSearcher(client).run(query), today=date(2026, 10, 20))


def test_splits_talk_pages_from_related_reading(fake_client, talk_query):
    briefing = make_briefing(fake_client, talk_query)

    assert [s.link for s in briefing.about_talk] == [
        "https://conf.example.org/schedule/",
        "https://conf.example.org/talks/42/",
    ]
    assert [s.link for s in briefing.related_reading] == [
        "https://blog.example.com/agentic-workflows"
    ]


def test_hides_results_that_only_match_the_speaker_name(fake_client, talk_query):
    briefing = make_briefing(fake_client, talk_query)

    links = {s.link for s in briefing.related_reading + briefing.news}
    assert "https://social.example.com/alex-smith" not in links
    assert "https://news.example.com/football" not in links
    assert briefing.hidden_off_topic == 2


def test_counts_and_search_records(fake_client, talk_query):
    briefing = make_briefing(fake_client, talk_query)

    assert briefing.source_count == 2 + 1 + 3 + 1
    assert [r.result_count for r in briefing.searches] == [5, 4, 1]
    assert not briefing.all_searches_failed


def test_short_topic_has_no_about_talk_section(fake_client):
    briefing = make_briefing(fake_client, TalkQuery("agentic engineering"))

    assert not briefing.is_talk
    assert briefing.about_talk == []
    assert len(briefing.related_reading) >= 2


def test_all_failed_when_every_search_errors(fake_client, talk_query):
    for engine in fake_client.responses:
        fake_client.responses[engine] = {"error": "Invalid API key."}

    assert make_briefing(fake_client, talk_query).all_searches_failed
