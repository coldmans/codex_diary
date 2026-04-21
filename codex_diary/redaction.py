from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){2,4}\d{3,4}(?!\w)")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
TOKEN_ASSIGN_RE = re.compile(
    r"(?i)\b(access[_-]?token|refresh[_-]?token|api[_-]?key|secret|password|authorization)\b\s*[:=]\s*([^\s,;]+)"
)
LONG_SECRET_RE = re.compile(r"\b(?=[A-Za-z0-9_-]{24,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_-]+\b")


def mask_sensitive_text(text: str) -> str:
    masked = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    masked = PHONE_RE.sub("[REDACTED_PHONE]", masked)
    masked = JWT_RE.sub("[REDACTED_SECRET]", masked)
    masked = OPENAI_KEY_RE.sub("[REDACTED_SECRET]", masked)
    masked = GOOGLE_KEY_RE.sub("[REDACTED_SECRET]", masked)
    masked = TOKEN_ASSIGN_RE.sub(lambda match: f"{match.group(1)}=[REDACTED_SECRET]", masked)
    masked = LONG_SECRET_RE.sub("[REDACTED_SECRET]", masked)
    return masked
