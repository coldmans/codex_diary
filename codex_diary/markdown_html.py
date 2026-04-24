"""Minimal Markdown → HTML renderer for the desktop UI.

Only the subset produced by generator.py is handled: headings (h1-h4),
ordered/unordered lists, blockquotes, fenced code blocks, horizontal rules,
paragraphs, and inline bold/italic/code.  Keeping this dependency-free
avoids adding another Python module to the PyInstaller bundle.
"""
from __future__ import annotations

import html
import re
from typing import List
from urllib.parse import urlsplit


INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _escape_attr(text: str) -> str:
    return html.escape(text, quote=True)


def _safe_link_href(raw_href: str) -> str:
    href = html.unescape(raw_href).strip()
    if not href:
        return "#"
    parsed = urlsplit(href)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return "#"
    return _escape_attr(href)


def _apply_inline(text: str) -> str:
    escaped = _escape(text)
    escaped = INLINE_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", escaped)
    escaped = ITALIC_RE.sub(lambda m: f"<em>{m.group(1)}</em>", escaped)
    escaped = LINK_RE.sub(
        lambda m: f'<a href="{_safe_link_href(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def _close_open_list(lines: List[str], stack: List[str]) -> None:
    while stack:
        lines.append(f"</{stack.pop()}>")


def render_markdown(markdown: str) -> str:
    if not markdown.strip():
        return ""

    out: List[str] = []
    list_stack: List[str] = []
    in_code = False
    code_lang = ""
    code_buffer: List[str] = []
    paragraph: List[str] = []
    in_quote = False
    quote_buffer: List[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = " ".join(line.strip() for line in paragraph if line.strip())
        if joined:
            out.append(f"<p>{_apply_inline(joined)}</p>")
        paragraph.clear()

    def flush_quote() -> None:
        nonlocal in_quote
        if not quote_buffer:
            in_quote = False
            return
        joined = " ".join(quote_buffer)
        out.append(f"<blockquote>{_apply_inline(joined)}</blockquote>")
        quote_buffer.clear()
        in_quote = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if in_code:
            if line.strip().startswith("```"):
                joined = "\n".join(code_buffer)
                lang_attr = f' class="lang-{_escape_attr(code_lang)}"' if code_lang else ""
                out.append(f"<pre><code{lang_attr}>{_escape(joined)}</code></pre>")
                code_buffer.clear()
                code_lang = ""
                in_code = False
            else:
                code_buffer.append(raw_line)
            continue

        if line.strip().startswith("```"):
            flush_paragraph()
            flush_quote()
            _close_open_list(out, list_stack)
            in_code = True
            code_lang = line.strip()[3:].strip()
            continue

        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_quote()
            _close_open_list(out, list_stack)
            continue

        if stripped.startswith("> "):
            flush_paragraph()
            _close_open_list(out, list_stack)
            quote_buffer.append(stripped[2:])
            in_quote = True
            continue
        if in_quote:
            flush_quote()

        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            _close_open_list(out, list_stack)
            out.append("<hr />")
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            flush_paragraph()
            _close_open_list(out, list_stack)
            level = len(heading_match.group(1))
            out.append(f"<h{level}>{_apply_inline(heading_match.group(2))}</h{level}>")
            continue

        bullet_match = re.match(r"^[-*+]\s+(.*)", stripped)
        if bullet_match:
            flush_paragraph()
            if not list_stack or list_stack[-1] != "ul":
                _close_open_list(out, list_stack)
                out.append("<ul>")
                list_stack.append("ul")
            out.append(f"<li>{_apply_inline(bullet_match.group(1))}</li>")
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)", stripped)
        if ordered_match:
            flush_paragraph()
            if not list_stack or list_stack[-1] != "ol":
                _close_open_list(out, list_stack)
                out.append("<ol>")
                list_stack.append("ol")
            out.append(f"<li>{_apply_inline(ordered_match.group(1))}</li>")
            continue

        _close_open_list(out, list_stack)
        paragraph.append(stripped)

    flush_paragraph()
    flush_quote()
    _close_open_list(out, list_stack)
    if in_code and code_buffer:
        out.append(f"<pre><code>{_escape(chr(10).join(code_buffer))}</code></pre>")

    return "\n".join(out)
