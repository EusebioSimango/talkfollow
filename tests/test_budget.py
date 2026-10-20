from concurrent.futures import ThreadPoolExecutor

import pytest

from talkfollow.budget import BudgetedClient, BudgetExceeded, SearchFailed, safe_error_message


def test_budget_blocks_calls_beyond_the_limit(fake_client):
    client = BudgetedClient(fake_client, max_calls=1)
    client.search({"engine": "google_light"})

    with pytest.raises(BudgetExceeded):
        client.search({"engine": "google_news"})
    assert len(fake_client.requests) == 1
    assert client.engines_called == ["google_light"]


def test_budget_holds_under_parallel_calls(fake_client):
    client = BudgetedClient(fake_client, max_calls=3)

    def attempt(_):
        try:
            client.search({"engine": "youtube"})
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(attempt, range(10)))

    assert outcomes.count(True) == 3
    assert len(fake_client.requests) == 3


def test_client_errors_become_safe_messages(fake_client):
    class FakeHTTPError(Exception):
        status_code = 401
        error = "Invalid API key."

    fake_client.responses["google_light"] = FakeHTTPError(
        "401 for https://serpapi.com/search?api_key=SECRET"
    )
    client = BudgetedClient(fake_client, max_calls=3)

    with pytest.raises(SearchFailed) as raised:
        client.search({"engine": "google_light"})
    assert str(raised.value) == "SerpApi error 401: Invalid API key."


def test_unknown_errors_only_show_their_type():
    assert safe_error_message(TimeoutError("https://x?api_key=SECRET")) == (
        "SerpApi request failed (TimeoutError)."
    )
