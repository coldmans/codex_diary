from datetime import date
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_diary.models import DiaryBuildResult
from codex_diary.llm import LLMError

from codex_diary.cli import run


class CliTests(unittest.TestCase):
    def test_language_and_length_flags_are_forwarded(self) -> None:
        result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="finalize",
            markdown="# Sample\n",
            output_path=Path("/tmp/2026-04-21.md"),
            used_llm=False,
            stats={},
            warnings=(),
        )
        stdout = StringIO()
        stderr = StringIO()
        with patch("codex_diary.cli.build_diary", return_value=result) as build_mock:
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(
                    [
                        "finalize",
                        "--date",
                        "2026-04-21",
                        "--language",
                        "ja",
                        "--dry-run",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(build_mock.call_args.kwargs["output_language"], "ja")
        self.assertEqual(build_mock.call_args.kwargs["diary_length"], "short")

    def test_length_flag_is_forwarded(self) -> None:
        result = DiaryBuildResult(
            target_date=date(2026, 4, 21),
            mode="finalize",
            markdown="# Sample\n",
            output_path=Path("/tmp/2026-04-21.md"),
            used_llm=False,
            stats={},
            warnings=(),
        )
        stdout = StringIO()
        stderr = StringIO()
        with patch("codex_diary.cli.build_diary", return_value=result) as build_mock:
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(
                    [
                        "finalize",
                        "--date",
                        "2026-04-21",
                        "--length",
                        "very-long",
                        "--dry-run",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(build_mock.call_args.kwargs["diary_length"], "very-long")

    def test_invalid_language_is_rejected(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = run(["finalize", "--language", "pirate"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--language", stderr.getvalue())

    def test_invalid_length_is_rejected(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = run(["finalize", "--length", "novella"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--length", stderr.getvalue())

    def test_graceful_failure_when_no_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(
                    [
                        "finalize",
                        "--date",
                        "2026-04-21",
                        "--source-dir",
                        tmpdir,
                        "--dry-run",
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("Chronicle 요약 파일을 찾지 못했습니다", stderr.getvalue())

    def test_codex_connection_failure_is_reported(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch(
            "codex_diary.cli.build_diary",
            side_effect=LLMError("먼저 codex를 연결해주세요. ChatGPT 로그인이 확인되지 않았습니다."),
        ):
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(["finalize", "--date", "2026-04-21", "--dry-run"])
        self.assertEqual(exit_code, 1)
        self.assertIn("먼저 codex를 연결해주세요", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
