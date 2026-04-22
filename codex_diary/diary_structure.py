"""Parse a finalized diary Markdown into a structured payload for the UI.

The UI uses this structure to render semantically meaningful components
(timeline items, highlight cards, checklist, diary prose) instead of a raw
Markdown block.  Anything the parser does not recognize is preserved in
``extras`` so the caller can still show it as fallback Markdown.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .i18n import all_diary_headings, all_report_headings, all_section_aliases

TIMELINE_RE = re.compile(r"^\[(\d{2}:\d{2})\]\s*(.*)")
BULLET_RE = re.compile(r"^[-*+]\s+(.*)")

REPORT_HEADINGS = set(all_report_headings())
DIARY_HEADINGS = set(all_diary_headings())
SECTION_SLUGS = all_section_aliases()


def _collect_lines(source: str) -> List[str]:
    return [line.rstrip() for line in source.splitlines()]


def _split_top_sections(markdown: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"preamble": [], "report": [], "diary": []}
    current = "preamble"
    for line in _collect_lines(markdown):
        if line.strip() in REPORT_HEADINGS:
            current = "report"
            continue
        if line.strip() in DIARY_HEADINGS:
            current = "diary"
            continue
        sections[current].append(line)
    return sections


def _extract_title_and_quote(lines: List[str]) -> tuple[Optional[str], Optional[str], List[str]]:
    title: Optional[str] = None
    quote: Optional[str] = None
    leftover: List[str] = []
    for line in lines:
        stripped = line.strip()
        if title is None and stripped.startswith("# "):
            title = stripped[2:].strip()
            continue
        if quote is None and stripped.startswith("> "):
            quote = stripped[2:].strip()
            continue
        if stripped:
            leftover.append(stripped)
    return title, quote, leftover


def _split_report_subsections(lines: List[str]) -> Dict[str, List[str]]:
    subs: Dict[str, List[str]] = {}
    current_key: Optional[str] = None
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer, current_key
        if current_key is not None:
            subs[current_key] = buffer
        buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            flush()
            heading = stripped[4:].strip()
            current_key = SECTION_SLUGS.get(heading, heading)
            continue
        if current_key is None:
            continue
        buffer.append(line)
    flush()
    return subs


def _clean_paragraph(lines: List[str]) -> str:
    return " ".join(part.strip() for part in lines if part.strip()).strip()


def _parse_bullets(lines: List[str]) -> List[str]:
    items: List[str] = []
    buffer: List[str] = []
    for line in lines:
        stripped = line.strip()
        match = BULLET_RE.match(stripped)
        if match:
            if buffer:
                items.append(_clean_paragraph(buffer))
                buffer = []
            items.append(match.group(1).strip())
        elif stripped:
            buffer.append(stripped)
    if buffer:
        items.append(_clean_paragraph(buffer))
    return [item for item in items if item]


def _parse_timeline(lines: List[str]) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        match = BULLET_RE.match(stripped)
        if not match:
            continue
        text = match.group(1).strip()
        ts = TIMELINE_RE.match(text)
        if ts:
            entries.append({"time": ts.group(1), "text": ts.group(2).strip()})
        else:
            entries.append({"time": "", "text": text})
    return entries


def _parse_paragraphs(lines: List[str]) -> List[str]:
    paragraphs: List[str] = []
    buffer: List[str] = []
    for line in lines:
        if not line.strip():
            if buffer:
                paragraphs.append(_clean_paragraph(buffer))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        paragraphs.append(_clean_paragraph(buffer))
    return [p for p in paragraphs if p]


def structure_diary(markdown: str) -> Dict[str, Any]:
    sections = _split_top_sections(markdown)
    title, intro_quote, _ = _extract_title_and_quote(sections["preamble"])
    report_subs = _split_report_subsections(sections["report"])

    structured: Dict[str, Any] = {
        "title": title or "",
        "intro_quote": intro_quote or "",
        "report": {
            "today": _clean_paragraph(report_subs.get("today", [])),
            "timeline": _parse_timeline(report_subs.get("timeline", [])),
            "decisions": _parse_bullets(report_subs.get("decisions", [])),
            "blockers": _parse_bullets(report_subs.get("blockers", [])),
            "tomorrow": _parse_bullets(report_subs.get("tomorrow", [])),
            "reflection": _clean_paragraph(report_subs.get("reflection", [])),
        },
        "diary": _parse_paragraphs(sections["diary"]),
    }

    structured["has_report"] = any(
        [
            structured["report"]["today"],
            structured["report"]["timeline"],
            structured["report"]["decisions"],
            structured["report"]["blockers"],
            structured["report"]["tomorrow"],
            structured["report"]["reflection"],
        ]
    )
    structured["has_diary"] = bool(structured["diary"])
    return structured
