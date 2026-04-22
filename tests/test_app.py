import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from codex_diary.app import (
    DiaryBridge,
    build_weekly_overview,
    default_output_dir,
    extract_markdown_section,
    list_daily_diary_files,
    list_saved_entries,
    parse_diary_date_from_path,
    render_views,
    split_markdown_views,
    week_bounds,
)
from codex_diary.diary_structure import structure_diary
from codex_diary.markdown_html import render_markdown
from codex_diary.models import DiaryBuildResult


SAMPLE_MARKDOWN = """# 2026-04-21 작업 일기

> 샘플

## 금일 작업 보고서

### 오늘 한 일
보고서 내용

## 오늘의 일기 버전

일기 내용
"""

SAMPLE_MARKDOWN_EN = """# 2026-04-21 Work Diary

> Sample

## Work Report

### What I Did Today
Report body

## Diary Version

Diary body
"""


class AppHelperTests(unittest.TestCase):
    def test_default_output_dir_uses_repo_in_dev_mode(self) -> None:
        with patch("codex_diary.app.is_frozen_app", return_value=False):
            output_dir = default_output_dir()
        self.assertEqual(output_dir.name, "diary")
        self.assertEqual(output_dir.parent.name, "output")

    def test_default_output_dir_uses_application_support_when_frozen(self) -> None:
        fake_home = Path("/tmp/fake-home")
        with patch("codex_diary.app.is_frozen_app", return_value=True):
            with patch("pathlib.Path.home", return_value=fake_home):
                output_dir = default_output_dir()
        self.assertEqual(
            output_dir,
            fake_home / "Library" / "Application Support" / "Codex Diary" / "output" / "diary",
        )

    def test_extract_markdown_section(self) -> None:
        report = extract_markdown_section(
            SAMPLE_MARKDOWN,
            "## 금일 작업 보고서",
            "## 오늘의 일기 버전",
        )
        self.assertIn("### 오늘 한 일", report)
        self.assertNotIn("일기 내용", report)

    def test_split_markdown_views(self) -> None:
        views = split_markdown_views(SAMPLE_MARKDOWN)
        self.assertIn("# 2026-04-21 작업 일기", views["full"])
        self.assertIn("보고서 내용", views["report"])
        self.assertIn("일기 내용", views["diary"])

    def test_split_markdown_views_supports_english_headings(self) -> None:
        views = split_markdown_views(SAMPLE_MARKDOWN_EN)
        self.assertIn("## Work Report", views["report"])
        self.assertIn("Diary body", views["diary"])

    def test_parse_diary_date_from_path(self) -> None:
        self.assertEqual(parse_diary_date_from_path(Path("/tmp/2026-04-21.md")), date(2026, 4, 21))
        self.assertIsNone(parse_diary_date_from_path(Path("/tmp/not-a-date.md")))

    def test_week_bounds(self) -> None:
        start, end = week_bounds(date(2026, 4, 22))
        self.assertEqual(start, date(2026, 4, 20))
        self.assertEqual(end, date(2026, 4, 26))

    def test_build_weekly_overview(self) -> None:
        weekly_dir = Path("/tmp/codex-diary-weekly")
        weekly_dir.mkdir(parents=True, exist_ok=True)
        (weekly_dir / "2026-04-21.md").write_text("# Day 1", encoding="utf-8")
        (weekly_dir / "2026-04-23.md").write_text("# Day 2", encoding="utf-8")
        overview = build_weekly_overview(date(2026, 4, 22), list_daily_diary_files(weekly_dir))
        self.assertIn("2026-04-20 ~ 2026-04-26", overview)
        self.assertIn("2026-04-21", overview)
        self.assertIn("# Day 2", overview)

    def test_build_weekly_overview_supports_selected_language(self) -> None:
        weekly_dir = Path("/tmp/codex-diary-weekly-en")
        weekly_dir.mkdir(parents=True, exist_ok=True)
        (weekly_dir / "2026-04-21.md").write_text("# Day 1", encoding="utf-8")
        overview = build_weekly_overview(
            date(2026, 4, 22),
            list_daily_diary_files(weekly_dir),
            output_language_code="en",
        )
        self.assertIn("Weekly Overview", overview)
        self.assertIn("Date List", overview)

    def test_list_saved_entries_includes_week_label(self) -> None:
        weekly_dir = Path("/tmp/codex-diary-weekly-entries")
        weekly_dir.mkdir(parents=True, exist_ok=True)
        (weekly_dir / "2026-04-21.md").write_text("# Day 1", encoding="utf-8")
        (weekly_dir / "2026-04-23.md").write_text("# Day 2", encoding="utf-8")
        entries = list_saved_entries(weekly_dir)
        self.assertEqual(entries["weeks"][0]["label"], "2026-04-20 ~ 2026-04-26")


class MarkdownRenderTests(unittest.TestCase):
    def test_headings_and_lists(self) -> None:
        html = render_markdown("# 제목\n\n- 하나\n- 둘\n")
        self.assertIn("<h1>제목</h1>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>하나</li>", html)

    def test_blockquote_and_paragraph(self) -> None:
        html = render_markdown("> 인용\n\n본문 문장입니다.\n")
        self.assertIn("<blockquote>인용</blockquote>", html)
        self.assertIn("<p>본문 문장입니다.</p>", html)

    def test_escapes_html(self) -> None:
        html = render_markdown("<script>alert(1)</script>\n")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_render_views_produces_html(self) -> None:
        raw, html = render_views(SAMPLE_MARKDOWN)
        self.assertIn("보고서 내용", raw["report"])
        self.assertIn("<h2>", html["full"])
        self.assertIn("<p>일기 내용</p>", html["diary"])


class DiaryStructureTests(unittest.TestCase):
    def test_structure_extracts_sections(self) -> None:
        diary = """# 2026-04-21 작업 일기

> Chronicle 10분 요약 7개 바탕.

## 금일 작업 보고서

### 오늘 한 일
초반에는 chargeCat을 봤다.

### 사소한 흐름까지 포함한 시간순 메모
- [13:19] 첫 흐름
- [13:29] 두 번째 흐름

### 중요하게 확인하거나 결정한 것
- 결정 하나
- 결정 둘

### 막혔던 점 또는 미해결 이슈
- 막힘 하나

### 내일 할 일
- 정리하기

### 짧은 회고
회고 문장

## 오늘의 일기 버전

첫 문단.

둘째 문단.
"""
        structured = structure_diary(diary)
        self.assertEqual(structured["title"], "2026-04-21 작업 일기")
        self.assertIn("Chronicle", structured["intro_quote"])
        self.assertIn("chargeCat", structured["report"]["today"])
        self.assertEqual(len(structured["report"]["timeline"]), 2)
        self.assertEqual(structured["report"]["timeline"][0]["time"], "13:19")
        self.assertEqual(structured["report"]["decisions"], ["결정 하나", "결정 둘"])
        self.assertEqual(structured["report"]["blockers"], ["막힘 하나"])
        self.assertEqual(structured["report"]["tomorrow"], ["정리하기"])
        self.assertIn("회고 문장", structured["report"]["reflection"])
        self.assertEqual(len(structured["diary"]), 2)
        self.assertTrue(structured["has_report"])
        self.assertTrue(structured["has_diary"])

    def test_structure_handles_missing_sections(self) -> None:
        structured = structure_diary("# 제목\n\n## 오늘의 일기 버전\n\n짧은 글.")
        self.assertFalse(structured["has_report"])
        self.assertTrue(structured["has_diary"])
        self.assertEqual(structured["diary"], ["짧은 글."])

    def test_structure_extracts_english_sections(self) -> None:
        structured = structure_diary(SAMPLE_MARKDOWN_EN)
        self.assertTrue(structured["has_report"])
        self.assertTrue(structured["has_diary"])
        self.assertIn("Report body", structured["report"]["today"])
        self.assertEqual(structured["diary"], ["Diary body"])


class DiaryBridgeTests(unittest.TestCase):
    CONNECTED_STATUS = {
        "available": True,
        "connected": True,
        "connectable": True,
        "message": "Codex에 연결되어 있어요.",
        "detail": "로그인 상태가 정상이에요.",
    }

    def test_get_state_includes_codex_status(self) -> None:
        bridge = DiaryBridge()
        with patch.object(
            bridge,
            "_codex_status_details",
            return_value=self.CONNECTED_STATUS,
        ):
            payload = bridge.get_state()

        self.assertTrue(payload["codex"]["connected"])
        self.assertTrue(payload["generation_available"])
        self.assertIn("생성", payload["status"])

    def test_generate_returns_views_and_saves_file(self) -> None:
        bridge = DiaryBridge()
        out_dir = Path("/tmp/codex-diary-bridge-test")
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "2026-04-21.md"
        if target.exists():
            target.unlink()

        fake_result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="finalize",
            markdown=SAMPLE_MARKDOWN,
            output_path=target,
            used_llm=False,
            stats={"used_10min": 1, "used_6h": 0},
            warnings=(),
        )

        with patch.object(bridge, "_codex_status_details", return_value=self.CONNECTED_STATUS):
            with patch("codex_diary.app.build_diary", return_value=fake_result):
                payload = bridge.generate(
                    {
                        "target_date": "2026-04-21",
                        "boundary_hour": 4,
                        "mode": "finalize",
                        "source_dir": "/tmp/codex-diary-source",
                        "out_dir": str(out_dir),
                        "auto_save": True,
                    }
                )

        self.assertEqual(payload["target_date"], "2026-04-21")
        self.assertIn("보고서 내용", payload["views"]["report"])
        self.assertIn("<h1>", payload["views_html"]["full"])
        self.assertEqual(payload["saved_path"], str(target))
        self.assertTrue(target.exists())
        self.assertIn("structured", payload)
        self.assertTrue(payload["structured"]["has_diary"])

    def test_generate_blocks_when_codex_is_not_connected(self) -> None:
        bridge = DiaryBridge()
        fake_status = {
            "available": True,
            "connected": False,
            "connectable": True,
            "message": "먼저 codex를 연결해주세요.",
            "detail": "로그인이 필요해요.",
        }

        with patch.object(bridge, "_codex_status_details", return_value=fake_status):
            with patch("codex_diary.app.build_diary") as build_mock:
                payload = bridge.generate(
                    {
                        "target_date": "2026-04-21",
                        "boundary_hour": 4,
                        "mode": "finalize",
                        "source_dir": "/tmp/codex-diary-source",
                        "out_dir": "/tmp/codex-diary-out",
                        "auto_save": True,
                    }
                )

        build_mock.assert_not_called()
        self.assertEqual(payload["error"], "먼저 codex를 연결해주세요.")
        self.assertFalse(payload["generation_available"])

    def test_generate_passes_output_language_to_builder(self) -> None:
        bridge = DiaryBridge()
        out_dir = Path("/tmp/codex-diary-bridge-lang")
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "2026-04-21.md"

        fake_result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="finalize",
            markdown=SAMPLE_MARKDOWN_EN,
            output_path=target,
            used_llm=False,
            stats={"used_10min": 1, "used_6h": 0},
            warnings=(),
        )

        with patch.object(bridge, "_codex_status_details", return_value=self.CONNECTED_STATUS):
            with patch("codex_diary.app.build_diary", return_value=fake_result) as build_mock:
                payload = bridge.generate(
                    {
                        "target_date": "2026-04-21",
                        "boundary_hour": 4,
                        "mode": "finalize",
                        "source_dir": "/tmp/codex-diary-source",
                        "out_dir": str(out_dir),
                        "auto_save": False,
                        "output_language_code": "ja",
                    }
                )

        self.assertEqual(build_mock.call_args.kwargs["output_language"], "ja")
        self.assertEqual(payload["output_language_code"], "ja")
        self.assertEqual(payload["output_language"], "Japanese")

    def test_connect_codex_launches_device_auth_on_macos(self) -> None:
        bridge = DiaryBridge()
        status = {
            "available": True,
            "connected": False,
            "connectable": True,
            "message": "먼저 codex를 연결해주세요.",
            "detail": "로그인이 필요해요.",
        }

        with patch.object(bridge, "_codex_status_details", return_value=status):
            with patch.object(bridge, "_launch_codex_device_auth") as launch_mock:
                payload = bridge.connect_codex()

        launch_mock.assert_called_once()
        self.assertIn("Terminal", payload["message"])
        self.assertFalse(payload["connected"])

    def test_generate_removes_legacy_draft_file(self) -> None:
        bridge = DiaryBridge()
        out_dir = Path("/tmp/codex-diary-bridge-legacy")
        legacy_dir = out_dir / "drafts"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_file = legacy_dir / "2026-04-21.md"
        legacy_file.write_text("old draft", encoding="utf-8")
        target = out_dir / "2026-04-21.md"

        fake_result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="draft-update",
            markdown=SAMPLE_MARKDOWN,
            output_path=target,
            used_llm=False,
            stats={"used_10min": 1, "used_6h": 0},
            warnings=(),
        )

        with patch.object(bridge, "_codex_status_details", return_value=self.CONNECTED_STATUS):
            with patch("codex_diary.app.build_diary", return_value=fake_result):
                bridge.generate(
                    {
                        "target_date": "2026-04-21",
                        "boundary_hour": 4,
                        "mode": "draft-update",
                        "source_dir": "/tmp/codex-diary-source",
                        "out_dir": str(out_dir),
                        "auto_save": True,
                    }
                )

        self.assertFalse(legacy_file.exists())
        self.assertTrue(target.exists())

    def test_load_date_returns_error_when_missing(self) -> None:
        bridge = DiaryBridge()
        payload = bridge.load_date("1999-01-01", "/tmp/codex-diary-missing-dir")
        self.assertIn("error", payload)

    def test_load_week_returns_overview(self) -> None:
        bridge = DiaryBridge()
        out_dir = Path("/tmp/codex-diary-week-test")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "2026-04-21.md").write_text("# Day", encoding="utf-8")
        payload = bridge.load_week("2026-04-21", str(out_dir))
        self.assertIn("2026-04-20", payload["label"])
        self.assertIn("<h1>", payload["views_html"]["full"])

    def test_load_week_uses_current_output_language(self) -> None:
        bridge = DiaryBridge()
        bridge.config.output_language_code = "en"
        out_dir = Path("/tmp/codex-diary-week-lang-test")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "2026-04-21.md").write_text("# Day", encoding="utf-8")
        payload = bridge.load_week("2026-04-21", str(out_dir))
        self.assertEqual(payload["output_language_code"], "en")
        self.assertIn("Weekly Overview", payload["markdown"])

    def test_list_saved_entries_empty_dir(self) -> None:
        entries = list_saved_entries(Path("/tmp/codex-diary-does-not-exist"))
        self.assertEqual(entries["dates"], [])
        self.assertEqual(entries["weeks"], [])


if __name__ == "__main__":
    unittest.main()
