import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tkinter import Tk

from codex_diary.app import (
    DiaryDesktopApp,
    build_weekly_overview,
    default_output_dir,
    extract_markdown_section,
    list_daily_diary_files,
    parse_diary_date_from_path,
    split_markdown_views,
    week_bounds,
)
from codex_diary.models import DiaryBuildResult


SAMPLE_MARKDOWN = """# 2026-04-21 작업 일기

> 샘플

## 금일 작업 보고서

### 오늘 한 일
보고서 내용

## 오늘의 일기 버전

일기 내용
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

    def test_start_generation_updates_ui_after_background_work(self) -> None:
        root = Tk()
        root.withdraw()
        app = DiaryDesktopApp(root)
        app.target_date = date(2026, 4, 21)
        app.out_dir = Path("/tmp/codex-diary-test-output")
        app._update_controls()

        fake_result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="finalize",
            markdown=SAMPLE_MARKDOWN,
            output_path=Path("/tmp/codex-diary-test-output/2026-04-21.md"),
            used_llm=False,
            stats={"used_10min": 1, "used_6h": 0},
            warnings=(),
        )

        done = {"value": False}

        def finish() -> None:
            done["value"] = True
            self.assertEqual(app.copy_button.cget("state"), "normal")
            self.assertEqual(app.open_button.cget("state"), "normal")
            self.assertEqual(app.external_open_button.cget("state"), "normal")
            self.assertIn("보고서 내용", app.preview_content)
            root.destroy()

        with patch("codex_diary.app.build_diary", return_value=fake_result):
            with patch("pathlib.Path.write_text", return_value=None):
                app._start_generation()
                root.after(1000, finish)
                root.mainloop()

        self.assertTrue(done["value"])


if __name__ == "__main__":
    unittest.main()
