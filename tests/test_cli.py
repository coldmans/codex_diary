from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_diary.cli import run


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
