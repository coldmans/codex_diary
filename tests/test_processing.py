from datetime import date, datetime, timezone
from pathlib import Path
import unittest

from codex_diary.generator import build_minor_timeline, dedupe_events, fallback_markdown
from codex_diary.models import ChronicleSource, Event
from codex_diary.redaction import mask_sensitive_text


def make_source(name: str, granularity: str) -> ChronicleSource:
    dt = datetime(2026, 4, 21, 4, 30, tzinfo=timezone.utc)
    return ChronicleSource(
        path=Path(name),
        recorded_at_utc=dt,
        recorded_at_local=dt,
        granularity=granularity,
        diary_date=date(2026, 4, 21),
    )


class ProcessingTests(unittest.TestCase):
    def test_duplicate_removal_prefers_10min(self) -> None:
        source_10 = make_source("a.md", "10min")
        source_6h = make_source("b.md", "6h")
        ten_minute_event = Event(
            source=source_10,
            order=0,
            section_title="Section",
            text="The user reviewed Chronicle docs and checked the current plan.",
            tags=("research",),
            entities=("Chronicle",),
        )
        six_hour_event = Event(
            source=source_6h,
            order=0,
            section_title="Section",
            text="The user checked the current plan and reviewed Chronicle documentation.",
            tags=("research",),
            entities=("Chronicle",),
        )
        deduped = dedupe_events([six_hour_event, ten_minute_event])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].source.granularity, "10min")

    def test_mask_sensitive_text(self) -> None:
        text = (
            "Contact me at user@example.com or +82 10-1234-5678. "
            "api_key=sk-abcdefghijklmnopqrstuvwxyz1234 "
            "jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"
        )
        masked = mask_sensitive_text(text)
        self.assertNotIn("user@example.com", masked)
        self.assertNotIn("+82 10-1234-5678", masked)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz1234", masked)
        self.assertIn("[REDACTED_EMAIL]", masked)
        self.assertIn("[REDACTED_PHONE]", masked)
        self.assertIn("[REDACTED_SECRET]", masked)

    def test_minor_timeline_keeps_low_signal_flow(self) -> None:
        source = make_source("timeline.md", "10min")
        events = [
            Event(
                source=source,
                order=0,
                section_title="Codex: recovering `chargeCat` context",
                text="A modal asked whether to update Codex, warning that local sessions would be interrupted.",
                tags=("blocker",),
                entities=("chargeCat",),
            ),
            Event(
                source=source,
                order=1,
                section_title="Chrome: short documentation and model-news browsing",
                text="an OpenAI developer documentation page about Chronicle",
                tags=("research",),
                entities=("Chronicle",),
            ),
        ]
        timeline = build_minor_timeline(events)
        self.assertEqual(len(timeline), 2)
        self.assertTrue(any("업데이트 안내 모달" in item for item in timeline))
        self.assertTrue(any("Chronicle 관련 문서" in item for item in timeline))

    def test_fallback_markdown_contains_report_and_diary(self) -> None:
        source = make_source("bundle.md", "10min")
        events = [
            Event(
                source=source,
                order=0,
                section_title="Codex: recovering `chargeCat` context",
                text="migration framing: moving `chargeCat` backend from SQLite to MySQL 8 with Docker Compose, partly for Azure deployment support",
                tags=("activity",),
                entities=("chargeCat",),
            ),
            Event(
                source=source,
                order=1,
                section_title="Planning",
                text="The visible plan proposed an MVP with backend, frontend, and deployment steps.",
                tags=("decision",),
                entities=("K-Context Guide",),
            ),
            Event(
                source=source,
                order=2,
                section_title="Testing",
                text="tests still needing follow-up: `backend/test/database.test.js` still appeared to reference `test.sqlite`",
                tags=("blocker", "next_action"),
                entities=("chargeCat", "backend/test/database.test.js", "test.sqlite"),
            ),
        ]
        markdown = fallback_markdown(
            target_date="2026-04-21",
            mode="finalize",
            stats={"used_10min": 1, "used_6h": 0},
            events=events,
        )
        self.assertIn("## 금일 작업 보고서", markdown)
        self.assertIn("## 오늘의 일기 버전", markdown)
        self.assertIn("### 오늘 한 일", markdown)
        self.assertIn("SQLite 기준 테스트", markdown)


if __name__ == "__main__":
    unittest.main()
