import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_diary.package_macos import (
    app_bundle_path,
    auxiliary_dist_path,
    cleanup_packaging_artifacts,
    default_app_icon_source,
    default_dmg_name,
    sanitize_artifact_name,
)


class MacOSPackagingTests(unittest.TestCase):
    def test_sanitize_artifact_name(self) -> None:
        self.assertEqual(sanitize_artifact_name("Codex Diary"), "Codex-Diary")
        self.assertEqual(sanitize_artifact_name("Codex_Diary!"), "Codex-Diary")

    def test_default_dmg_name(self) -> None:
        self.assertEqual(default_dmg_name("Codex Diary", "0.1.0"), "Codex-Diary-0.1.0-macOS.dmg")

    def test_app_bundle_path(self) -> None:
        self.assertEqual(app_bundle_path(Path("/tmp/dist"), "Codex Diary"), Path("/tmp/dist/Codex Diary.app"))

    def test_auxiliary_dist_path(self) -> None:
        self.assertEqual(auxiliary_dist_path(Path("/tmp/dist"), "Codex Diary"), Path("/tmp/dist/Codex Diary"))

    def test_default_app_icon_source(self) -> None:
        path = default_app_icon_source()
        self.assertEqual(path.name, "app-icon.png")
        self.assertTrue(str(path).endswith("codex_diary/ui/assets/app-icon.png"))

    def test_cleanup_packaging_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist_dir = root / "dist"
            build_dir = root / "build" / "macos"
            helper_dir = dist_dir / "Codex Diary"
            helper_dir.mkdir(parents=True)
            build_dir.mkdir(parents=True)
            (dist_dir / ".DS_Store").write_text("junk", encoding="utf-8")

            cleanup_packaging_artifacts(
                dist_dir=dist_dir,
                build_dir=build_dir,
                app_name="Codex Diary",
            )

            self.assertFalse(helper_dir.exists())
            self.assertFalse(build_dir.exists())
            self.assertFalse((root / "build").exists())
            self.assertFalse((dist_dir / ".DS_Store").exists())


if __name__ == "__main__":
    unittest.main()
