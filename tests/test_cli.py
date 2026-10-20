import json

from typer.testing import CliRunner

from conftest import TALK_TITLE
from talkfollow import cli

runner = CliRunner()


def use_fake_client(monkeypatch, fake_client):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.setattr(cli, "official_client", lambda api_key: fake_client)


def test_writes_markdown_briefing_to_file(fake_client, monkeypatch, tmp_path):
    use_fake_client(monkeypatch, fake_client)
    out_file = tmp_path / "briefing.md"

    result = runner.invoke(
        cli.app, [TALK_TITLE, "-s", "Alex", "-k", "agentic engineering", "-o", str(out_file)]
    )

    assert result.exit_code == 0, result.output
    assert out_file.read_text().startswith(f"# {TALK_TITLE}\n")


def test_json_output_and_skipping_videos(fake_client, monkeypatch):
    use_fake_client(monkeypatch, fake_client)

    result = runner.invoke(cli.app, ["agentic engineering", "--json", "--no-videos"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert [s["section"] for s in payload["searches"]] == ["web", "news"]
    assert payload["briefing_date"]


def test_exit_code_when_every_search_fails(fake_client, monkeypatch):
    use_fake_client(monkeypatch, fake_client)
    for engine in fake_client.responses:
        fake_client.responses[engine] = {"error": "Invalid API key."}

    assert runner.invoke(cli.app, ["asyncio"]).exit_code == cli.EXIT_ALL_SEARCHES_FAILED


def test_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(cli.app, ["asyncio"]).exit_code == cli.EXIT_MISSING_API_KEY


def test_blank_title_is_rejected(fake_client, monkeypatch):
    use_fake_client(monkeypatch, fake_client)

    assert runner.invoke(cli.app, ["   "]).exit_code == 2
