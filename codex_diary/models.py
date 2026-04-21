from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Tuple


@dataclass(frozen=True)
class ChronicleSource:
    path: Path
    recorded_at_utc: datetime
    recorded_at_local: datetime
    granularity: str
    diary_date: date


@dataclass(frozen=True)
class Event:
    source: ChronicleSource
    order: int
    section_title: str
    text: str
    tags: Tuple[str, ...]
    entities: Tuple[str, ...]


@dataclass
class DiaryBuildResult:
    target_date: date
    mode: str
    markdown: str
    output_path: Path
    used_llm: bool
    stats: Dict[str, int] = field(default_factory=dict)
    warnings: Tuple[str, ...] = ()
