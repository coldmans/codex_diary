from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
import re
from typing import Iterable, Optional

from .models import ChronicleSource

SOURCE_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-[A-Za-z0-9]+-(?P<granularity>10min|6h)-memory-summary\.md$"
)
DATE_FORMAT = "%Y-%m-%d"
STAMP_FORMAT = "%Y-%m-%dT%H-%M-%S"


def get_local_timezone() -> tzinfo:
    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


def apply_day_boundary(local_dt: datetime, day_boundary_hour: int) -> date:
    return (local_dt - timedelta(hours=day_boundary_hour)).date()


def resolve_target_date(
    date_str: Optional[str],
    *,
    day_boundary_hour: int,
    local_tz: Optional[tzinfo] = None,
    now: Optional[datetime] = None,
) -> date:
    if date_str:
        return datetime.strptime(date_str, DATE_FORMAT).date()

    tz = local_tz or get_local_timezone()
    current = now.astimezone(tz) if now else datetime.now(tz)
    return apply_day_boundary(current, day_boundary_hour)


def parse_source_filename(
    path: Path,
    *,
    local_tz: Optional[tzinfo] = None,
    day_boundary_hour: int = 4,
) -> ChronicleSource:
    match = SOURCE_PATTERN.match(path.name)
    if not match:
        raise ValueError(f"지원하지 않는 Chronicle 파일명입니다: {path.name}")

    utc_dt = datetime.strptime(match.group("timestamp"), STAMP_FORMAT).replace(tzinfo=timezone.utc)
    tz = local_tz or get_local_timezone()
    local_dt = utc_dt.astimezone(tz)
    return ChronicleSource(
        path=path,
        recorded_at_utc=utc_dt,
        recorded_at_local=local_dt,
        granularity=match.group("granularity"),
        diary_date=apply_day_boundary(local_dt, day_boundary_hour),
    )


def discover_sources(
    source_dir: Path,
    *,
    target_date: date,
    day_boundary_hour: int,
    local_tz: Optional[tzinfo] = None,
) -> list[ChronicleSource]:
    if not source_dir.exists():
        return []

    parsed_sources = []
    for path in sorted(source_dir.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            source = parse_source_filename(
                path,
                local_tz=local_tz,
                day_boundary_hour=day_boundary_hour,
            )
        except ValueError:
            continue
        if source.diary_date == target_date:
            parsed_sources.append(source)
    return sorted(parsed_sources, key=lambda item: item.recorded_at_utc)


def split_sources_by_granularity(sources: Iterable[ChronicleSource]) -> tuple[list[ChronicleSource], list[ChronicleSource]]:
    ten_minute = [source for source in sources if source.granularity == "10min"]
    six_hour = [source for source in sources if source.granularity == "6h"]
    return ten_minute, six_hour
