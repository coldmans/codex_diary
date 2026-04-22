from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiaryLengthOption:
    code: str
    label: str


DEFAULT_DIARY_LENGTH_CODE = "short"

_OPTIONS = (
    DiaryLengthOption(code="short", label="Short"),
    DiaryLengthOption(code="medium", label="Medium"),
    DiaryLengthOption(code="long", label="Long"),
    DiaryLengthOption(code="very-long", label="Very long"),
)

_ALIASES = {
    "short": "short",
    "brief": "short",
    "compact": "short",
    "짧게": "short",
    "중간": "medium",
    "medium": "medium",
    "normal": "medium",
    "long": "long",
    "길게": "long",
    "very-long": "very-long",
    "very long": "very-long",
    "very_long": "very-long",
    "verylong": "very-long",
    "매우 길게": "very-long",
}


def supported_diary_length_codes() -> list[str]:
    return [option.code for option in _OPTIONS]


def get_diary_length_option(code: str | None) -> DiaryLengthOption:
    normalized = normalize_diary_length(code) or DEFAULT_DIARY_LENGTH_CODE
    for option in _OPTIONS:
        if option.code == normalized:
            return option
    return _OPTIONS[0]


def normalize_diary_length(
    value: str | None,
    *,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default
    raw = str(value).strip().lower()
    if not raw:
        return default
    normalized = _ALIASES.get(raw, raw)
    if normalized in supported_diary_length_codes():
        return normalized
    return default
