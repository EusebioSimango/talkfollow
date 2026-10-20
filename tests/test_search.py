from talkfollow.models import Section
from talkfollow.search import TalkSearcher


def test_runs_three_engines_with_locale_and_queries(fake_client, talk_query):
    results = TalkSearcher(fake_client, country="za").run(talk_query)

    assert list(results) == [Section.WEB, Section.NEWS, Section.VIDEOS]
    assert fake_client.request_for("google_light")["q"] == talk_query.for_section(Section.WEB)
    assert fake_client.request_for("google_news")["q"] == "agentic engineering"
    assert fake_client.request_for("youtube")["search_query"] == "agentic engineering"
    assert all(r["gl"] == "za" and r["hl"] == "en" for r in fake_client.requests)


def test_only_requested_sections_spend_credits(fake_client, talk_query):
    searcher = TalkSearcher(fake_client)
    results = searcher.run(talk_query, [Section.VIDEOS, Section.WEB])

    assert list(results) == [Section.WEB, Section.VIDEOS]
    assert sorted(searcher.engines_called) == ["google_light", "youtube"]


def test_budget_exhaustion_is_reported_per_section(fake_client, talk_query):
    results = TalkSearcher(fake_client, max_searches=2).run(talk_query)

    failed = [result for result in results.values() if result.error]
    assert len(failed) == 1
    assert "budget of 2 SerpApi searches" in failed[0].error


def test_empty_result_pages_are_not_failures(fake_client, talk_query):
    fake_client.responses["youtube"] = {
        "error": "Youtube hasn't returned any results for this query."
    }

    results = TalkSearcher(fake_client).run(talk_query)

    assert results[Section.VIDEOS].error is None


def test_api_errors_keep_serpapi_message_without_secrets(fake_client, talk_query):
    class FakeHTTPError(Exception):
        status_code = 401
        error = "Invalid API key."

    fake_client.responses["google_light"] = FakeHTTPError("https://serpapi.com?api_key=SECRET")

    results = TalkSearcher(fake_client).run(talk_query, [Section.WEB])

    assert results[Section.WEB].error == "SerpApi error 401: Invalid API key."
