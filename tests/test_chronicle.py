from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import tempfile
import unittest

from codex_diary.chronicle import (
    apply_day_boundary,
    discover_sources,
    parse_source_filename,
    resolve_target_date,
)


class ChronicleParsingTests(unittest.TestCase):
    def test_parse_source_filename_uses_utc_and_local_boundary(self) -> None:
        source = parse_source_filename(
            Path("2026-04-21T18-30-00-abcd-10min-memory-summary.md"),
            local_tz=ZoneInfo("Asia/Seoul"),
            day_boundary_hour=4,
        )
        self.assertEqual(source.recorded_at_utc.tzinfo, timezone.utc)
        self.assertEqual(source.recorded_at_local.hour, 3)
        self.assertEqual(source.diary_date.isoformat(), "2026-04-21")

    def test_resolve_target_date_respects_boundary(self) -> None:
        now = datetime(2026, 4, 22, 3, 30, tzinfo=ZoneInfo("Asia/Seoul"))
        target_date = resolve_target_date(
            None,
            day_boundary_hour=4,
            local_tz=ZoneInfo("Asia/Seoul"),
            now=now,
        )
        self.assertEqual(target_date.isoformat(), "2026-04-21")

    def test_discover_sources_groups_by_effective_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2026-04-21T18-30-00-abcd-10min-memory-summary.md").write_text("x", encoding="utf-8")
            (root / "2026-04-21T19-10-00-zzzz-10min-memory-summary.md").write_text("x", encoding="utf-8")
            matched = discover_sources(
                root,
                target_date=datetime(2026, 4, 21).date(),
                day_boundary_hour=4,
                local_tz=ZoneInfo("Asia/Seoul"),
            )
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0].path.name, "2026-04-21T18-30-00-abcd-10min-memory-summary.md")


if __name__ == "__main__":
    unittest.main()
