from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from codex_diary.llm import GenerationCancelledError, LLMError, load_provider_from_codex
from codex_diary.generator import (
    build_diary,
    build_llm_prompt,
    build_minor_timeline,
    choose_events,
    dedupe_events,
    fallback_markdown,
    legacy_output_paths,
    resolve_output_path,
    sample_events_for_prompt,
)
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


def make_source_at(name: str, granularity: str, hour: int, minute: int) -> ChronicleSource:
    dt = datetime(2026, 4, 21, hour, minute, tzinfo=timezone.utc)
    return ChronicleSource(
        path=Path(name),
        recorded_at_utc=dt,
        recorded_at_local=dt,
        granularity=granularity,
        diary_date=date(2026, 4, 21),
    )


def make_event(
    name: str,
    granularity: str,
    hour: int,
    minute: int,
    text: str,
    *,
    order: int = 0,
    tags: tuple[str, ...] = ("activity",),
    section_title: str = "Section",
) -> Event:
    return Event(
        source=make_source_at(name, granularity, hour, minute),
        order=order,
        section_title=section_title,
        text=text,
        tags=tags,
        entities=(),
    )


class ProcessingTests(unittest.TestCase):
    def test_sample_events_for_prompt_keeps_beginning_and_end(self) -> None:
        events = []
        for idx in range(20):
            dt = datetime(2026, 4, 21, 4, idx, tzinfo=timezone.utc)
            source = ChronicleSource(
                path=Path(f"event-{idx}.md"),
                recorded_at_utc=dt,
                recorded_at_local=dt,
                granularity="10min",
                diary_date=date(2026, 4, 21),
            )
            events.append(
                Event(
                    source=source,
                    order=0,
                    section_title="Section",
                    text=f"event {idx}",
                    tags=("activity",),
                    entities=(),
                )
            )

        sampled = sample_events_for_prompt(events, max_events=6)
        self.assertEqual(len(sampled), 6)
        self.assertEqual(sampled[0].text, "event 0")
        self.assertEqual(sampled[-1].text, "event 19")
        self.assertTrue(any(item.text not in {"event 0", "event 19"} for item in sampled))

    def test_sample_events_for_prompt_balances_across_source_windows(self) -> None:
        events = []
        for idx in range(40):
            events.append(make_event("early.md", "10min", 4, idx % 60, f"early event {idx}", order=idx))
        for idx in range(4):
            events.append(make_event("mid.md", "10min", 12, idx, f"mid event {idx}", order=idx))
        for idx in range(4):
            events.append(make_event("late.md", "10min", 21, idx, f"late event {idx}", order=idx))

        sampled = sample_events_for_prompt(events, max_events=9)
        sampled_sources = {event.source.path.name for event in sampled}

        self.assertIn("early.md", sampled_sources)
        self.assertIn("mid.md", sampled_sources)
        self.assertIn("late.md", sampled_sources)

    def test_sample_events_for_prompt_pins_priority_tags(self) -> None:
        events = [make_event("early.md", "10min", 4, idx % 60, f"early event {idx}", order=idx) for idx in range(50)]
        events.append(
            make_event(
                "late.md",
                "10min",
                22,
                10,
                "a late blocker still needing follow-up remained before packaging",
                tags=("blocker", "next_action"),
                section_title="Late blocker",
            )
        )

        sampled = sample_events_for_prompt(events, max_events=8)

        self.assertTrue(any("late blocker" in event.section_title.lower() for event in sampled))

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

    def test_duplicate_removal_keeps_similar_events_far_apart(self) -> None:
        early = make_event(
            "early.md",
            "10min",
            4,
            5,
            "The user checked the same settings panel again and reviewed the current configuration.",
        )
        late = make_event(
            "late.md",
            "10min",
            22,
            5,
            "The user reviewed the current configuration and checked the same settings panel again.",
        )

        deduped = dedupe_events([early, late])

        self.assertEqual(len(deduped), 2)

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

    def test_fallback_markdown_supports_english_output(self) -> None:
        source = make_source("bundle-en.md", "10min")
        events = [
            Event(
                source=source,
                order=0,
                section_title="Planning",
                text="The visible plan proposed an MVP with backend, frontend, and deployment steps.",
                tags=("decision",),
                entities=("K-Context Guide",),
            ),
            Event(
                source=source,
                order=1,
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
            output_language="en",
        )
        self.assertIn("## Work Report", markdown)
        self.assertIn("## Diary Version", markdown)
        self.assertIn("### What I Did Today", markdown)
        self.assertIn("SQLite-oriented tests", markdown)

    def test_build_llm_prompt_samples_across_full_day(self) -> None:
        events = []
        for idx in range(160):
            hour = 4 + (idx // 60)
            minute = idx % 60
            dt = datetime(2026, 4, 21, hour, minute, tzinfo=timezone.utc)
            source = ChronicleSource(
                path=Path(f"prompt-{idx}.md"),
                recorded_at_utc=dt,
                recorded_at_local=dt,
                granularity="10min",
                diary_date=date(2026, 4, 21),
            )
            events.append(
                Event(
                    source=source,
                    order=0,
                    section_title="Prompt Coverage",
                    text=f"event {idx}",
                    tags=("activity",),
                    entities=(),
                )
            )

        prompt = build_llm_prompt(
            mode="finalize",
            target_date="2026-04-21",
            day_boundary_hour=4,
            stats={"used_10min": 16, "used_6h": 0},
            events=events,
            output_language="ko",
        )
        self.assertIn("Total extracted events: 160", prompt)
        self.assertIn("Prompt events included: 120", prompt)
        self.assertIn("event 0", prompt)
        self.assertIn("event 159", prompt)

    def test_build_llm_prompt_trims_long_event_lines(self) -> None:
        long_tail = "z" * 800
        events = [
            make_event(
                "long.md",
                "10min",
                4,
                10,
                f"This sentence is intentionally long and should be trimmed before it enters the prompt {long_tail}",
                section_title="Very long prompt section title " + ("x" * 80),
            )
        ]

        prompt = build_llm_prompt(
            mode="finalize",
            target_date="2026-04-21",
            day_boundary_hour=4,
            stats={"used_10min": 1, "used_6h": 0},
            events=events,
            output_language="ko",
        )

        self.assertNotIn(long_tail, prompt)
        self.assertIn("Prompt events included: 1", prompt)

    def test_build_llm_prompt_includes_diary_length_guidance(self) -> None:
        events = [make_event("length.md", "10min", 4, 10, "Checked a long record and compared several views.")]
        prompt = build_llm_prompt(
            mode="finalize",
            target_date="2026-04-21",
            day_boundary_hour=4,
            stats={"used_10min": 1, "used_6h": 0},
            events=events,
            output_language="ko",
            diary_length="very-long",
        )

        self.assertIn("Diary length: very-long", prompt)
        self.assertIn("Length target: very-long.", prompt)
        self.assertIn("(6-8 full paragraphs)", prompt)

    def test_choose_events_adds_6h_when_10min_coverage_is_narrow(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            morning_a = root / "morning-a.md"
            morning_b = root / "morning-b.md"
            fallback = root / "fallback-6h.md"

            morning_a.write_text(
                "## Recording summary\n### Morning\n"
                "- Reviewed the calendar layout and checked the current report view.\n"
                "- Compared the current tabs and confirmed the early window behavior.\n"
                "- Read the current output and checked the file path handling again.\n",
                encoding="utf-8",
            )
            morning_b.write_text(
                "## Recording summary\n### Morning Follow-up\n"
                "- Reviewed the button placement and checked the toolbar state again.\n"
                "- Compared the current window layout and checked the scroll handling.\n"
                "- Read the current state and checked the same flow one more time.\n",
                encoding="utf-8",
            )
            fallback.write_text(
                "## Recording summary\n### Later Summary\n"
                "- A late blocker still needing follow-up remained around packaging and localized output.\n",
                encoding="utf-8",
            )

            sources = [
                ChronicleSource(
                    path=morning_a,
                    recorded_at_utc=datetime(2026, 4, 21, 4, 10, tzinfo=timezone.utc),
                    recorded_at_local=datetime(2026, 4, 21, 4, 10, tzinfo=timezone.utc),
                    granularity="10min",
                    diary_date=date(2026, 4, 21),
                ),
                ChronicleSource(
                    path=morning_b,
                    recorded_at_utc=datetime(2026, 4, 21, 4, 40, tzinfo=timezone.utc),
                    recorded_at_local=datetime(2026, 4, 21, 4, 40, tzinfo=timezone.utc),
                    granularity="10min",
                    diary_date=date(2026, 4, 21),
                ),
                ChronicleSource(
                    path=fallback,
                    recorded_at_utc=datetime(2026, 4, 21, 18, 0, tzinfo=timezone.utc),
                    recorded_at_local=datetime(2026, 4, 21, 18, 0, tzinfo=timezone.utc),
                    granularity="6h",
                    diary_date=date(2026, 4, 21),
                ),
            ]

            events, stats = choose_events(sources)

        self.assertEqual(stats["used_6h"], 1)
        self.assertTrue(any(event.source.granularity == "6h" for event in events))

    def test_build_diary_reports_progress_in_pipeline_order(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "chronicle.md"
            source_path.write_text(
                "## Recording summary\n"
                "### Morning\n"
                "- Reviewed the calendar layout and confirmed the current diary flow.\n",
                encoding="utf-8",
            )
            source = ChronicleSource(
                path=source_path,
                recorded_at_utc=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                recorded_at_local=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                granularity="10min",
                diary_date=date(2026, 4, 21),
            )
            progress_updates = []
            provider = SimpleNamespace(
                generate_markdown=lambda prompt, output_language: "# 2026-04-21 작업 일기\n\n> 샘플\n"
            )

            with patch("codex_diary.generator.discover_sources", return_value=[source]):
                result = build_diary(
                    target_date=date(2026, 4, 21),
                    mode="finalize",
                    source_dir=root,
                    out_dir=root,
                    day_boundary_hour=4,
                    output_language="ko",
                    provider=provider,
                    progress=progress_updates.append,
                )

        self.assertEqual(result.target_date.isoformat(), "2026-04-21")
        phases = [item["phase"] for item in progress_updates]
        self.assertEqual(phases[0], "collect")
        self.assertIn("organize", phases)
        self.assertIn("write", phases)
        self.assertEqual(progress_updates[-1]["phase"], "finish")
        self.assertEqual(progress_updates[-1]["status"], "completed")

    def test_build_diary_forwards_progress_capable_provider_updates(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "chronicle.md"
            source_path.write_text(
                "## Recording summary\n"
                "### Morning\n"
                "- Reviewed the calendar layout and confirmed the current diary flow.\n",
                encoding="utf-8",
            )
            source = ChronicleSource(
                path=source_path,
                recorded_at_utc=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                recorded_at_local=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                granularity="10min",
                diary_date=date(2026, 4, 21),
            )
            progress_updates = []

            def generate_markdown_with_progress(prompt, output_language, progress=None):  # type: ignore[no-untyped-def]
                if progress is not None:
                    progress(
                        {
                            "status": "running",
                            "phase": "write",
                            "detail_key": "loading.detail.writeStart",
                            "percent": 74,
                        }
                    )
                    progress(
                        {
                            "status": "running",
                            "phase": "write",
                            "detail_key": "loading.detail.writeWait",
                            "percent": 78,
                            "indeterminate": True,
                        }
                    )
                return "# 2026-04-21 작업 일기\n\n> 샘플\n"

            provider = SimpleNamespace(generate_markdown=generate_markdown_with_progress)

            with patch("codex_diary.generator.discover_sources", return_value=[source]):
                build_diary(
                    target_date=date(2026, 4, 21),
                    mode="finalize",
                    source_dir=root,
                    out_dir=root,
                    day_boundary_hour=4,
                    output_language="ko",
                    provider=provider,
                    progress=progress_updates.append,
                )

        write_details = [item.get("detail_key") for item in progress_updates if item.get("phase") == "write"]
        self.assertIn("loading.detail.writeStart", write_details)
        self.assertIn("loading.detail.writeWait", write_details)

    def test_build_diary_reports_failed_collect_phase_when_sources_missing(self) -> None:
        progress_updates = []
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch("codex_diary.generator.discover_sources", return_value=[]):
                with self.assertRaises(FileNotFoundError):
                    build_diary(
                        target_date=date(2026, 4, 21),
                        mode="finalize",
                        source_dir=root,
                        out_dir=root,
                        day_boundary_hour=4,
                        output_language="ko",
                        provider=SimpleNamespace(generate_markdown=lambda prompt, output_language: ""),
                        progress=progress_updates.append,
                    )

        self.assertTrue(progress_updates)
        self.assertEqual(progress_updates[-1]["status"], "failed")
        self.assertEqual(progress_updates[-1]["phase"], "collect")

    def test_build_diary_raises_when_cancelled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "chronicle.md"
            source_path.write_text(
                "## Recording summary\n"
                "### Morning\n"
                "- Reviewed the calendar layout and confirmed the current diary flow.\n",
                encoding="utf-8",
            )
            source = ChronicleSource(
                path=source_path,
                recorded_at_utc=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                recorded_at_local=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
                granularity="10min",
                diary_date=date(2026, 4, 21),
            )

            def cancelled_provider(prompt, output_language, progress=None, should_cancel=None):  # type: ignore[no-untyped-def]
                raise GenerationCancelledError("생성을 취소했어요.")

            provider = SimpleNamespace(generate_markdown=cancelled_provider)

            with patch("codex_diary.generator.discover_sources", return_value=[source]):
                with self.assertRaises(GenerationCancelledError):
                    build_diary(
                        target_date=date(2026, 4, 21),
                        mode="finalize",
                        source_dir=root,
                        out_dir=root,
                        day_boundary_hour=4,
                        output_language="ko",
                        diary_length="medium",
                        provider=provider,
                        should_cancel=lambda: False,
                    )

    def test_output_path_is_single_file_per_day(self) -> None:
        out_dir = Path("/tmp/codex-diary-output")
        self.assertEqual(
            resolve_output_path(out_dir, "finalize", "2026-04-21"),
            out_dir / "2026-04-21.md",
        )
        self.assertEqual(
            resolve_output_path(out_dir, "draft-update", "2026-04-21"),
            out_dir / "2026-04-21.md",
        )
        self.assertEqual(
            legacy_output_paths(out_dir, "2026-04-21"),
            [out_dir / "drafts" / "2026-04-21.md"],
        )

    def test_codex_provider_rejects_unconnected_login_status(self) -> None:
        def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
            if args[:3] == ["/opt/homebrew/bin/codex", "login", "status"]:
                return SimpleNamespace(returncode=0, stdout="Not logged in", stderr="")
            raise AssertionError("codex exec should not run before login is confirmed")

        with patch("codex_diary.llm.subprocess.run", side_effect=fake_run):
            with self.assertRaises(LLMError) as ctx:
                load_provider_from_codex()
        self.assertIn("먼저 codex를 연결해주세요", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
