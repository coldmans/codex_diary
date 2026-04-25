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
    def test_help_is_localized_for_requested_language(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as exc_info:
                run(["--language", "ja", "--help"])
        self.assertEqual(exc_info.exception.code, 0)
        self.assertIn("Chronicle の Markdown 要約から作業日記の下書きを作成します。", stdout.getvalue())
        self.assertIn("出力言語を指定します。", stdout.getvalue())

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
                        "--date",
                        "2026-04-21",
                        "--length",
                        "very-long",
                        "--dry-run",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(build_mock.call_args.kwargs["diary_length"], "very-long")

    def test_codex_model_flag_is_forwarded(self) -> None:
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
                        "--date",
                        "2026-04-21",
                        "--codex-model",
                        "gpt-5.5",
                        "--dry-run",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(build_mock.call_args.kwargs["codex_model"], "gpt-5.5")

    def test_invalid_language_is_rejected(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = run(["--language", "pirate"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--language", stderr.getvalue())

    def test_invalid_length_is_rejected(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = run(["--length", "novella"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--length", stderr.getvalue())

    def test_invalid_date_is_localized(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            exit_code = run(["--language", "ja", "--date", "2026/04/21"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--date は YYYY-MM-DD 形式で指定してください。", stderr.getvalue())

    def test_graceful_failure_when_no_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(
                    [
                        "--date",
                        "2026-04-21",
                        "--language",
                        "ja",
                        "--source-dir",
                        tmpdir,
                        "--dry-run",
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("Chronicle 要約ファイルが見つかりませんでした", stderr.getvalue())

    def test_codex_connection_failure_is_reported(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch(
            "codex_diary.cli.build_diary",
            side_effect=LLMError("먼저 codex를 연결해주세요. ChatGPT 로그인이 확인되지 않았습니다."),
        ):
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = run(["--date", "2026-04-21", "--language", "ja", "--dry-run"])
        self.assertEqual(exit_code, 1)
        self.assertIn("先に Codex を接続してください。", stderr.getvalue())

    def test_success_message_is_localized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "2026-04-21.md"
            result = DiaryBuildResult(
                target_date=date(2026, 4, 21),
                mode="finalize",
                markdown="# Sample\n",
                output_path=output_path,
                used_llm=False,
                stats={},
                warnings=(),
            )
            stdout = StringIO()
            stderr = StringIO()
            with patch("codex_diary.cli.build_diary", return_value=result):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    exit_code = run(["--date", "2026-04-21", "--language", "ja"])
            self.assertEqual(exit_code, 0)
            self.assertIn("作業日記を作成しました", stdout.getvalue())
            self.assertTrue(output_path.exists())

    def test_legacy_draft_mode_is_accepted_but_treated_as_finalize(self) -> None:
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
                exit_code = run(["draft-update", "--date", "2026-04-21", "--dry-run"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(build_mock.call_args.kwargs["mode"], "finalize")


if __name__ == "__main__":
    unittest.main()
