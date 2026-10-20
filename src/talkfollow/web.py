"""Public web demo: a form and a briefing page, with limits that protect the SerpApi budget.

Run locally with ``uv run --extra web uvicorn talkfollow.web:app --reload``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from markdown_it import MarkdownIt

from talkfollow.briefing import build_briefing
from talkfollow.budget import SearchClient
from talkfollow.limits import BriefingCache, DemoLimits, LimitReached
from talkfollow.queries import TalkQuery
from talkfollow.render import render_markdown
from talkfollow.search import TalkSearcher, official_client

MAX_TITLE_LENGTH = 120
MAX_FIELD_LENGTH = 80
DEFAULT_DAILY_BRIEFINGS = 10
BRIEFINGS_PER_VISITOR_PER_HOUR = 5

REPO_URL = "https://github.com/EusebioSimango/talkfollow"
SAMPLE_BRIEFING = Path(__file__).resolve().parents[2] / "examples" / "sample-briefing.md"

# Raw HTML in search results is shown as text, never rendered.
_markdown = MarkdownIt("commonmark", {"html": False}).enable("table")


class DemoNotConfigured(RuntimeError):
    """The server has no SerpApi key."""


def create_app(
    client_factory: Callable[[], SearchClient] | None = None,
    *,
    daily_briefings: int | None = None,
) -> FastAPI:
    limits = DemoLimits(
        daily_briefings=daily_briefings or _daily_briefings_from_env(),
        briefings_per_visitor_per_hour=BRIEFINGS_PER_VISITOR_PER_HOUR,
    )
    cache = BriefingCache()
    make_client = client_factory or _client_from_env
    app = FastAPI(title="TalkFollow", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _page("TalkFollow", _intro() + _form())

    @app.get("/brief", response_class=HTMLResponse)
    def brief(
        request: Request, title: str = "", speaker: str = "", keywords: str = ""
    ) -> HTMLResponse:
        form = _form(title, speaker, keywords)
        problem = _validation_problem(title, speaker, keywords)
        if problem:
            return _message_page(400, problem, form)

        query = TalkQuery(title, speaker=speaker, keywords=keywords)
        key = _cache_key(query)
        markdown = cache.get(key)
        if markdown is None:
            try:
                client = make_client()
                limits.reserve(_visitor_ip(request))
            except DemoNotConfigured:
                return _message_page(503, "The demo is not configured yet.", form)
            except LimitReached as exc:
                return _message_page(429, str(exc), form)
            briefing = build_briefing(query, TalkSearcher(client).run(query))
            markdown = render_markdown(briefing)
            if not briefing.all_searches_failed:
                cache.put(key, markdown)
        return HTMLResponse(_page(query.title, form + _briefing_html(markdown)))

    @app.get("/example", response_class=HTMLResponse)
    def example() -> HTMLResponse:
        if not SAMPLE_BRIEFING.is_file():
            return _message_page(404, "The sample briefing is not available.", _form())
        markdown = SAMPLE_BRIEFING.read_text(encoding="utf-8")
        return HTMLResponse(_page("Sample briefing", _form() + _briefing_html(markdown)))

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz() -> str:
        return "ok"

    return app


def _client_from_env() -> SearchClient:
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        raise DemoNotConfigured
    return official_client(api_key)


def _daily_briefings_from_env() -> int:
    value = os.getenv("DEMO_DAILY_BRIEFINGS", "")
    return int(value) if value.isdigit() and int(value) > 0 else DEFAULT_DAILY_BRIEFINGS


def _validation_problem(title: str, speaker: str, keywords: str) -> str | None:
    if not title.strip():
        return "Please enter a talk title or topic."
    if len(title) > MAX_TITLE_LENGTH:
        return f"The title can be at most {MAX_TITLE_LENGTH} characters."
    if len(speaker) > MAX_FIELD_LENGTH or len(keywords) > MAX_FIELD_LENGTH:
        return f"Speaker and keywords can be at most {MAX_FIELD_LENGTH} characters each."
    return None


def _cache_key(query: TalkQuery) -> str:
    return "\n".join(part.lower() for part in (query.title, query.speaker or "", query.topic))


def _visitor_ip(request: Request) -> str:
    # Render puts the client IP first in X-Forwarded-For. A visitor can spoof it, which is
    # why the daily cap, not this per-visitor cap, is what bounds the credits spent.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _briefing_html(markdown: str) -> str:
    return f'<article class="briefing">{_markdown.render(markdown)}</article>'


def _message_page(status_code: int, message: str, form: str) -> HTMLResponse:
    notice = f'<p class="notice">{escape(message)}</p>'
    return HTMLResponse(_page("TalkFollow", form + notice), status_code=status_code)


def _intro() -> str:
    return (
        "<p>Turn a conference talk into a short follow-up briefing: pages about the talk, "
        "related reading, recent news and related videos, with a link for every item. "
        "Each new briefing makes 3 searches through SerpApi.</p>"
        '<p><a href="/example">See a sample briefing</a> (no searches needed).</p>'
    )


def _form(title: str = "", speaker: str = "", keywords: str = "") -> str:
    return f"""
<form action="/brief" method="get">
  <label>Talk title or topic
    <input name="title" value="{escape(title)}" maxlength="{MAX_TITLE_LENGTH}" required
      placeholder="Ramping up agentic engineering in the age of AI-fatigue">
  </label>
  <label>Speaker <small>(optional)</small>
    <input name="speaker" value="{escape(speaker)}" maxlength="{MAX_FIELD_LENGTH}">
  </label>
  <label>Keywords for news and videos <small>(optional)</small>
    <input name="keywords" value="{escape(keywords)}" maxlength="{MAX_FIELD_LENGTH}"
      placeholder="agentic engineering">
  </label>
  <button type="submit">Make briefing</button>
</form>"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · TalkFollow</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; color: #1f2328; }}
  header a {{ color: inherit; text-decoration: none; }}
  form {{ display: grid; gap: .75rem; margin: 1.5rem 0; }}
  label {{ display: grid; gap: .25rem; font-weight: 600; }}
  input {{ font: inherit; padding: .5rem; border: 1px solid #c9ced6; border-radius: 6px; }}
  button {{ font: inherit; padding: .6rem; border: 0; border-radius: 6px;
           background: #1f6feb; color: white; cursor: pointer; }}
  .notice {{ padding: .75rem 1rem; border-radius: 6px; background: #fff4e5; }}
  .briefing {{ border-top: 1px solid #d0d7de; margin-top: 1.5rem; }}
  .briefing blockquote {{ margin: .25rem 0 .75rem; color: #57606a; }}
  .briefing table {{ border-collapse: collapse; font-size: .9rem; }}
  .briefing th, .briefing td {{ border: 1px solid #d0d7de; padding: .3rem .5rem; }}
  footer {{ margin-top: 3rem; font-size: .85rem; color: #57606a; }}
</style>
</head>
<body>
<header><h1><a href="/">TalkFollow</a></h1></header>
{body}
<footer>
  <p>Results come from SerpApi; links go to third-party sites. This demo makes at most
  {BRIEFINGS_PER_VISITOR_PER_HOUR} new briefings per visitor per hour and has a small daily
  limit. Searches and IP addresses are not logged.</p>
  <p><a href="{REPO_URL}">Source code and CLI</a>: run it with your own free SerpApi key.</p>
</footer>
</body>
</html>"""


app = create_app()
