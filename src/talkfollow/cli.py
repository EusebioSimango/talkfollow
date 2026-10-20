"""Command line entry point: ``talkfollow "Talk title" --speaker Name --keywords "topic"``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from talkfollow.briefing import build_briefing
from talkfollow.models import Briefing, Section
from talkfollow.queries import TalkQuery
from talkfollow.render import render_markdown
from talkfollow.search import DEFAULT_RESULT_LIMIT, TalkSearcher, official_client

EXIT_ALL_SEARCHES_FAILED = 1
EXIT_MISSING_API_KEY = 2

app = typer.Typer(
    add_completion=False,
    help="Turn a conference talk, speaker or topic into a cited follow-up briefing.",
)
console = Console()
status_console = Console(stderr=True)


@app.command()
def main(
    title: Annotated[
        str, typer.Argument(help='Talk title or topic, e.g. "async Python at scale".')
    ],
    speaker: Annotated[
        str | None, typer.Option("--speaker", "-s", help="Speaker name, to find the talk.")
    ] = None,
    keywords: Annotated[
        str | None,
        typer.Option(
            "--keywords", "-k", help='Short topic for news and videos, e.g. "agentic AI".'
        ),
    ] = None,
    country: Annotated[str, typer.Option(help="Two-letter country code for results.")] = "za",
    language: Annotated[str, typer.Option(help="Language code for results.")] = "en",
    limit: Annotated[
        int, typer.Option(min=1, max=10, help="Results requested per search.")
    ] = DEFAULT_RESULT_LIMIT,
    news: Annotated[bool, typer.Option(help="Include the Google News search.")] = True,
    videos: Annotated[bool, typer.Option(help="Include the YouTube search.")] = True,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Save the briefing to this file.")
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Output JSON instead of Markdown.")
    ] = False,
) -> None:
    try:
        query = TalkQuery(title, speaker=speaker, keywords=keywords)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="TITLE") from None

    api_key = load_api_key()
    searcher = TalkSearcher(
        official_client(api_key), country=country, language=language, result_limit=limit
    )
    with status_console.status("Searching Google, Google News and YouTube via SerpApi..."):
        results = searcher.run(query, selected_sections(news=news, videos=videos))
    briefing = build_briefing(query, results)

    write_output(briefing, output=output, as_json=as_json)
    status_console.print(f"[dim]SerpApi searches made: {len(searcher.engines_called)}[/dim]")
    if briefing.all_searches_failed:
        raise typer.Exit(code=EXIT_ALL_SEARCHES_FAILED)


def load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        status_console.print(
            "[red]Missing SERPAPI_API_KEY.[/red] Copy .env.example to .env and add your key "
            "from https://serpapi.com/manage-api-key"
        )
        raise typer.Exit(code=EXIT_MISSING_API_KEY)
    return api_key


def selected_sections(*, news: bool, videos: bool) -> list[Section]:
    sections = [Section.WEB]
    if news:
        sections.append(Section.NEWS)
    if videos:
        sections.append(Section.VIDEOS)
    return sections


def write_output(briefing: Briefing, *, output: Path | None, as_json: bool) -> None:
    text = (
        json.dumps(briefing.to_dict(), indent=2, ensure_ascii=False, default=str) + "\n"
        if as_json
        else render_markdown(briefing)
    )
    if output:
        output.write_text(text, encoding="utf-8")
        status_console.print(f"Saved briefing to [bold]{output}[/bold]")
    elif as_json or not console.is_terminal:
        print(text, end="")
    else:
        console.print(Markdown(text))


if __name__ == "__main__":
    app()
