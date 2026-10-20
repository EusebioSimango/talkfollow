"""Render a ``Briefing`` as Markdown. Formatting only; no decisions about content."""

from __future__ import annotations

from datetime import date

from talkfollow.models import Briefing, SearchRecord, Section, Source


def render_markdown(briefing: Briefing) -> str:
    blocks = [
        _header(briefing),
        _answer(briefing),
        *_sections(briefing),
        _related_questions(briefing),
        _footer(briefing),
    ]
    return "\n\n".join(block for block in blocks if block).rstrip() + "\n"


def format_date(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _header(briefing: Briefing) -> str:
    facts = [
        f"**Speaker:** {briefing.speaker}" if briefing.speaker else "",
        f"**Keywords:** {briefing.keywords}" if briefing.keywords else "",
        f"**Briefing date:** {format_date(briefing.briefing_date)}",
    ]
    return "\n\n".join(
        [
            f"# {briefing.title}",
            " · ".join(fact for fact in facts if fact),
            f"> {_summary(briefing)}",
        ]
    )


def _summary(briefing: Briefing) -> str:
    counts: list[str] = []
    if briefing.search_for(Section.WEB):
        if briefing.is_talk:
            counts.append(f"{len(briefing.about_talk)} about this talk")
            counts.append(f"{len(briefing.related_reading)} related reading")
        else:
            counts.append(f"{len(briefing.related_reading)} background reading")
    if briefing.search_for(Section.NEWS):
        counts.append(f"{len(briefing.news)} news")
    if briefing.search_for(Section.VIDEOS):
        counts.append(_plural(len(briefing.videos), "video"))
    searches = _plural(len(briefing.searches), "SerpApi search", "SerpApi searches")
    sources = _plural(briefing.source_count, "source")
    return f"{sources} from {searches}: {', '.join(counts)}."


def _answer(briefing: Briefing) -> str:
    return f"## In one line\n\n{briefing.answer}" if briefing.answer else ""


def _sections(briefing: Briefing) -> list[str]:
    return [
        *_web_sections(briefing),
        _searched_section(briefing, Section.NEWS, "In the news", briefing.news),
        _searched_section(briefing, Section.VIDEOS, "Talks and videos", briefing.videos),
    ]


def _web_sections(briefing: Briefing) -> list[str]:
    record = briefing.search_for(Section.WEB)
    if not record:
        return []
    if not briefing.is_talk:
        return [
            _searched_section(briefing, Section.WEB, "Background reading", briefing.related_reading)
        ]
    about = _list_section(
        "About this talk", briefing.about_talk, _empty_reason(record, "No page about it found yet.")
    )
    if record.error:
        return [about]
    related = _list_section(
        "Related reading", briefing.related_reading, "No other on-topic reading found."
    )
    return [about, related]


def _searched_section(
    briefing: Briefing, section: Section, title: str, sources: list[Source]
) -> str:
    record = briefing.search_for(section)
    if not record:
        return ""
    empty = _empty_reason(record, f"Nothing on topic found for {_quoted(record.query)}.")
    return _list_section(title, sources, empty)


def _empty_reason(record: SearchRecord, default: str) -> str:
    return (
        f"{record.section.engine_label} search failed: {record.error}" if record.error else default
    )


def _list_section(title: str, sources: list[Source], empty: str) -> str:
    if not sources:
        return f"## {title}\n\n_{empty}_"
    items = [_source_item(index, source) for index, source in enumerate(sources, start=1)]
    return f"## {title}\n\n" + "\n".join(items)


def _source_item(index: int, source: Source) -> str:
    line = f"{index}. **[{_link_text(source.title)}]({source.link})**"
    meta = " · ".join(
        part for part in (_publisher(source), source.published, source.details) if part
    )
    if meta:
        line += f" — {meta}"
    if source.snippet:
        line += f"\n   > {source.snippet}"
    return line


def _publisher(source: Source) -> str:
    """The publisher, or the domain, unless the title already says it."""
    name = source.publisher or source.domain
    return "" if name.lower() in source.title.lower() else name


def _related_questions(briefing: Briefing) -> str:
    if not briefing.related_questions:
        return ""
    questions = "\n".join(f"- {question}" for question in briefing.related_questions)
    return f"## Questions people also ask\n\n{questions}"


def _footer(briefing: Briefing) -> str:
    rows = [
        "| Section | Engine | Query | Results |",
        "| --- | --- | --- | --- |",
        *(_search_row(record) for record in briefing.searches),
    ]
    notes = []
    if briefing.hidden_off_topic:
        notes.append(
            f"{_plural(briefing.hidden_off_topic, 'off-topic result')} hidden "
            "(no topic words in the title or snippet)."
        )
    notes.append("Results come from SerpApi. Links go to third-party sites.")
    return "\n\n".join(["---", "### Searches used", "\n".join(rows), f"_{' '.join(notes)}_"])


def _search_row(record: SearchRecord) -> str:
    query = record.query.replace("|", "\\|").replace("`", "'")
    outcome = f"Failed: {record.error}" if record.error else str(record.result_count)
    outcome = outcome.replace("|", "\\|")
    return f"| {record.section.label} | {record.section.engine_label} | `{query}` | {outcome} |"


def _link_text(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def _quoted(text: str) -> str:
    return "`" + text.replace("`", "'") + "`"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"
