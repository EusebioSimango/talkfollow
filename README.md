# TalkFollow

Turn a conference talk into a short follow-up briefing, with a link for every item.

You walk out of a talk at PyCon ZA wanting to dig deeper. The usual follow-up is three browser tabs: Google for the talk page and background reading, Google News for what changed recently, and YouTube for other talks on the subject. TalkFollow runs those three searches in one command and gives you a Markdown briefing you can keep, share or paste into your notes.

```bash
talkfollow "Ramping up agentic engineering in the age of AI-fatigue" \
  --speaker "Jane Doe" --keywords "agentic engineering"
```

Built for the [SerpApi PyCon ZA 2026 Hackathon](https://serpapi.com/pyconzahackathon).

## What you get

A briefing with these sections, each built only from live search results:

| Section | Where it comes from |
| --- | --- |
| **In one line** | Google's answer box or knowledge-graph summary, when there is one. |
| **About this talk** | Pages that mention the talk itself, such as the schedule or the talk page. |
| **Related reading** | Other on-topic pages from the same Google search. |
| **In the news** | Recent Google News stories on the topic, with clear dates (`2 Sep 2026`). |
| **Talks and videos** | YouTube videos on the topic, with channel, length and views. |
| **Questions people also ask** | Google's related questions, as prompts for your own research. |
| **Searches used** | A table with every query sent, its engine and how many results came back. |

When you give a short topic instead of a talk title (for example `"Python packaging"`), the first two web sections become a single **Background reading** section.

TalkFollow never writes text that did not come back from a search. If a search fails or finds nothing on topic, the section says so in one line instead of filling the gap. See [`examples/sample-briefing.md`](examples/sample-briefing.md) for a real briefing, generated with `talkfollow "free-threaded Python"`.

### How it keeps results on topic

Search results for a talk often include people who share the speaker's name, or news that only matches one generic word. TalkFollow applies three simple rules:

1. **A title of 4 or more words is treated as a talk title** and searched as an exact phrase, together with the speaker's name.
2. **News and videos search the topic, not the title.** The topic is `--keywords` when given, otherwise the title. A short topic finds far better news than a full talk title.
3. **Every result must contain at least one topic word** in its title, snippet or link. Results that do not are hidden, and the footer says how many were hidden. A web result counts as **About this talk** when it contains at least 60% of the title's significant words.

## How it uses SerpApi

SerpApi is the whole data layer: without it there is no briefing.

TalkFollow uses the official [`serpapi-search-tools`](https://serpapi.github.io/serpapi-search-tools-python/) package, with the official [`serpapi`](https://github.com/serpapi/serpapi-python) Python SDK (`serpapi.Client`) underneath. There are no direct HTTP requests to serpapi.com.

| Section | Tool from `serpapi-search-tools` | SerpApi engine | Query |
| --- | --- | --- | --- |
| In one line, about this talk, related reading, questions | `web_search` (restricted to `google_light`) | Google Light | `"talk title" speaker` |
| In the news | `news_search` | Google News | topic |
| Talks and videos | `videos_search` | YouTube | topic |

How it fits together:

- Each tool is created with `provider="function"` and `response_format=SearchResultFormat.JSON`, so the app reads structured fields (`organic_results`, `answer_box`, `news_results`, `video_results`, ...) instead of Markdown.
- The locale is set once through `default_params` (`gl=za`, `hl=en` by default; change it with `--country` and `--language`). `result_limit` keeps each section short (5 by default, `--limit` up to 10).
- The three searches run in parallel. They share one `serpapi.Client`, passed to the tools through the package's `client=` hook and wrapped in a thread-safe `BudgetedClient` that refuses any request beyond **3 SerpApi searches per run**. One briefing costs at most 3 of the free plan's 250 searches a month. Use `--no-news` or `--no-videos` to spend fewer.
- SerpApi's "no results" answer is shown as an empty section, not as a failure. Real errors, such as an invalid key, are shown with SerpApi's own message. Request URLs are never printed, because they contain the API key.

## Run it

You need Python 3.10 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/) and a free [SerpApi API key](https://serpapi.com/users/sign_up) (250 searches a month).

```bash
git clone https://github.com/EusebioSimango/talkfollow.git
cd talkfollow
uv sync
cp .env.example .env   # then paste your key after SERPAPI_API_KEY=
```

You can also export the key instead of using `.env`:

```bash
export SERPAPI_API_KEY="your-key"
```

Try it:

```bash
# A talk: title, speaker and a short topic for news and videos
uv run talkfollow "Ramping up agentic engineering in the age of AI-fatigue" \
  -s "Jane Doe" -k "agentic engineering"

# Just a topic
uv run talkfollow "free-threaded Python"

# Spend fewer searches, save the result
uv run talkfollow "Python packaging" --no-videos --limit 3 -o briefing-packaging.md

# Structured output for other tools
uv run talkfollow "pytest fixtures" --json
```

Run `uv run talkfollow --help` for every option. The command exits with code `1` if every search failed and `2` if the API key is missing.

## Project layout

Each module has one job, so the search, the relevance rules and the output format can be read and tested on their own.

| Module | Responsibility |
| --- | --- |
| [`cli.py`](src/talkfollow/cli.py) | Command line options, API key loading, writing the output. |
| [`queries.py`](src/talkfollow/queries.py) | `TalkQuery`: decides what to search for in each section. |
| [`search.py`](src/talkfollow/search.py) | `TalkSearcher`: runs the SerpApi searches in parallel through `serpapi-search-tools`. |
| [`budget.py`](src/talkfollow/budget.py) | `BudgetedClient`: caps searches per run and turns errors into messages that are safe to show. |
| [`parsing.py`](src/talkfollow/parsing.py) | Turns SerpApi JSON into `Source` items. Pure functions. |
| [`briefing.py`](src/talkfollow/briefing.py) | Applies the relevance rules and builds the `Briefing`. |
| [`render.py`](src/talkfollow/render.py) | Writes the `Briefing` as Markdown. |
| [`models.py`](src/talkfollow/models.py) | The plain data classes shared by the modules above. |

## Tests

The tests replace `serpapi.Client` with a fake client that returns saved responses in SerpApi's real shapes, so they spend no credits and need no key:

```bash
uv run pytest
```

There is one test file per module. Together they cover the queries sent to each engine, the 3-search budget (including under parallel searches), parsing, the relevance rules, the Markdown output, error messages that never leak the key, and the CLI end to end.

## What was added for the hackathon

Everything. TalkFollow is a new project, started on 20 October 2026 for the SerpApi PyCon ZA Hackathon: the search layer, the budgeted client, the relevance rules, the briefing renderer, the CLI and the tests.

## Credits

TalkFollow is built on these open source libraries. No code was copied from them; they are used as dependencies under their own licences.

- [`serpapi-search-tools`](https://github.com/serpapi/serpapi-search-tools-python) and [`serpapi`](https://github.com/serpapi/serpapi-python) by SerpApi (MIT)
- [Typer](https://github.com/fastapi/typer) (MIT), [Rich](https://github.com/Textualize/rich) (MIT) and [python-dotenv](https://github.com/theskumar/python-dotenv) (BSD-3-Clause)
- [pytest](https://github.com/pytest-dev/pytest) (MIT), for the tests

## License

[MIT](LICENSE)
