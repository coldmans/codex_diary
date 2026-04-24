from __future__ import annotations

from collections import OrderedDict
import re
from typing import Iterable

from .models import ChronicleSource, Event
from .redaction import mask_sensitive_text

CODE_SPAN_RE = re.compile(r"`([^`]{2,80})`")
ENDPOINT_RE = re.compile(r"\b/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+\b")

DECISION_PATTERNS = (
    re.compile(r"\bplanned\b"),
    re.compile(r"\bproposed\b"),
    re.compile(r"\bframed\b"),
    re.compile(r"\bdecided\b"),
    re.compile(r"\bdecision\b"),
    re.compile(r"\bfallback\b"),
    re.compile(r"\bmvp\b", re.IGNORECASE),
    re.compile(r"implementation direction"),
)
RESEARCH_PATTERNS = (
    re.compile(r"\breviewed\b"),
    re.compile(r"\bvisited\b"),
    re.compile(r"\bdocumentation\b"),
    re.compile(r"\bdocs\b"),
    re.compile(r"\breference(?:s)?\b"),
    re.compile(r"\bbrowsing\b"),
    re.compile(r"\bchecked\b"),
    re.compile(r"\bvalidation\b"),
    re.compile(r"\bcompare(?:d)?\b"),
    re.compile(r"\bscrolled\b"),
)
BLOCKER_PATTERNS = (
    re.compile(r"\berror\b"),
    re.compile(r"\bwarning\b"),
    re.compile(r"\bfailed\b"),
    re.compile(r"still needing"),
    re.compile(r"still appeared"),
    re.compile(r"needs? follow-up"),
    re.compile(r"temporary error"),
    re.compile(r"\bmissing\b"),
    re.compile(r"could not"),
    re.compile(r"\binterrupted\b"),
    re.compile(r"requesting confirmation"),
    re.compile(r"\bunavailable\b"),
)
NEXT_ACTION_PATTERNS = (
    re.compile(r"next step"),
    re.compile(r"next work"),
    re.compile(r"next action"),
    re.compile(r"likely next"),
    re.compile(r"\bto-?do\b"),
    re.compile(r"still needing"),
    re.compile(r"needs? follow-up"),
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_paragraph(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'])", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def parse_markdown_blocks(markdown: str) -> list[tuple[str, list[str]]]:
    lines = markdown.splitlines()
    blocks: list[tuple[str, list[str]]] = []
    current_h2 = None
    current_h3 = None
    buffer: list[str] = []

    def flush() -> None:
        if current_h2 == "Recording summary" and current_h3 and buffer:
            blocks.append((current_h3, buffer.copy()))

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("## "):
            if line[3:].strip() == "Citations":
                break
            flush()
            current_h2 = line[3:].strip()
            current_h3 = None
            buffer = []
            continue

        if current_h2 != "Recording summary":
            continue

        if line.startswith("### "):
            flush()
            current_h3 = line[4:].strip()
            buffer = []
            continue

        if current_h3:
            buffer.append(line)

    flush()

    if blocks:
        return blocks

    fallback = []
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## Citations"):
            break
        fallback.append(raw_line)
    return [("Recording summary", fallback)]


def parse_block_items(lines: Iterable[str]) -> list[str]:
    items: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        paragraph = normalize_whitespace(" ".join(paragraph_buffer))
        items.extend(split_paragraph(paragraph))
        paragraph_buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            items.append(normalize_whitespace(re.sub(r"^([-*]|\d+\.)\s+", "", line)))
            continue
        paragraph_buffer.append(line)

    flush_paragraph()
    return [item for item in items if len(item) > 10]


def extract_entities(text: str, section_title: str) -> tuple[str, ...]:
    candidates = OrderedDict()
    for match in CODE_SPAN_RE.finditer(f"{section_title} {text}"):
        token = normalize_whitespace(match.group(1))
        if token:
            candidates[token] = None
    for match in ENDPOINT_RE.finditer(text):
        token = normalize_whitespace(match.group(0))
        if token:
            candidates[token] = None
    return tuple(candidates.keys())


def categorize_event(text: str, section_title: str) -> tuple[str, ...]:
    combined = f"{section_title} {text}".lower()
    tags = []
    if any(pattern.search(combined) for pattern in DECISION_PATTERNS):
        tags.append("decision")
    if any(pattern.search(combined) for pattern in RESEARCH_PATTERNS):
        tags.append("research")
    if any(pattern.search(combined) for pattern in BLOCKER_PATTERNS):
        tags.append("blocker")
    if any(pattern.search(combined) for pattern in NEXT_ACTION_PATTERNS):
        tags.append("next_action")
    if not tags:
        tags.append("activity")
    return tuple(dict.fromkeys(tags))


def extract_events(source: ChronicleSource, markdown: str) -> list[Event]:
    blocks = parse_markdown_blocks(markdown)
    events: list[Event] = []
    order = 0

    for section_title, lines in blocks:
        masked_section_title = mask_sensitive_text(section_title)
        for item in parse_block_items(lines):
            masked_item = mask_sensitive_text(item)
            events.append(
                Event(
                    source=source,
                    order=order,
                    section_title=masked_section_title,
                    text=masked_item,
                    tags=categorize_event(masked_item, masked_section_title),
                    entities=extract_entities(masked_item, masked_section_title),
                )
            )
            order += 1
    return events
