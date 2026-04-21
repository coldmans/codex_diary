import unittest
from pathlib import Path

from codex_diary.package_macos import app_bundle_path, default_dmg_name, sanitize_artifact_name


class MacOSPackagingTests(unittest.TestCase):
    def test_sanitize_artifact_name(self) -> None:
        self.assertEqual(sanitize_artifact_name("Codex Diary"), "Codex-Diary")
        self.assertEqual(sanitize_artifact_name("Codex_Diary!"), "Codex-Diary")

    def test_default_dmg_name(self) -> None:
        self.assertEqual(default_dmg_name("Codex Diary", "0.1.0"), "Codex-Diary-0.1.0-macOS.dmg")

    def test_app_bundle_path(self) -> None:
        self.assertEqual(app_bundle_path(Path("/tmp/dist"), "Codex Diary"), Path("/tmp/dist/Codex Diary.app"))


if __name__ == "__main__":
    unittest.main()
