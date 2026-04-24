import plistlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codex_diary.package_macos import (
    BUNDLE_IDENTIFIER,
    app_bundle_path,
    auxiliary_dist_path,
    build_homebrew_cask_text,
    build_notarytool_submit_command,
    calculate_sha256,
    cleanup_packaging_artifacts,
    default_app_icon_source,
    default_dmg_name,
    github_release_dmg_url,
    homebrew_cask_filename,
    homebrew_cask_token,
    notary_credential_args,
    opening_instructions_filename,
    opening_instructions_text,
    prepare_dmg_staging,
    sanitize_artifact_name,
    sign_app_bundle,
    staple_artifact,
    update_app_bundle_metadata,
    write_homebrew_cask,
)


class MacOSPackagingTests(unittest.TestCase):
    def test_sanitize_artifact_name(self) -> None:
        self.assertEqual(sanitize_artifact_name("Codex Diary"), "Codex-Diary")
        self.assertEqual(sanitize_artifact_name("Codex_Diary!"), "Codex-Diary")

    def test_default_dmg_name(self) -> None:
        self.assertEqual(default_dmg_name("Codex Diary", "0.1.0"), "Codex-Diary-0.1.0-macOS.dmg")

    def test_homebrew_cask_token(self) -> None:
        self.assertEqual(homebrew_cask_token("Codex Diary"), "codex-diary")
        self.assertEqual(homebrew_cask_filename("Codex Diary"), "codex-diary.rb")

    def test_github_release_dmg_url(self) -> None:
        self.assertEqual(
            github_release_dmg_url(
                github_repository="coldmans/codex_diary",
                app_name="Codex Diary",
                version="0.1.0",
            ),
            "https://github.com/coldmans/codex_diary/releases/download/v0.1.0/Codex-Diary-0.1.0-macOS.dmg",
        )

    def test_calculate_sha256(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(b"codex diary")

            self.assertEqual(
                calculate_sha256(path),
                "1e21872b107fd827857b117cad47b648a31b1e859478f8978da107afc4a9b7b8",
            )

    def test_build_homebrew_cask_text(self) -> None:
        text = build_homebrew_cask_text(
            app_name="Codex Diary",
            version="0.1.0",
            sha256="abc123",
            github_repository="coldmans/codex_diary",
        )

        self.assertIn('cask "codex-diary" do', text)
        self.assertIn('sha256 "abc123"', text)
        self.assertIn("releases/download/v#{version}/Codex-Diary-#{version}-macOS.dmg", text)
        self.assertIn('xattr",', text)
        self.assertIn("com.apple.quarantine", text)
        self.assertIn('app "Codex Diary.app"', text)

    def test_build_homebrew_cask_text_omits_quarantine_for_notarized_build(self) -> None:
        text = build_homebrew_cask_text(
            app_name="Codex Diary",
            version="0.1.0",
            sha256="abc123",
            github_repository="coldmans/codex_diary",
            notarized=True,
        )

        self.assertIn('cask "codex-diary" do', text)
        self.assertNotIn("postflight", text)
        self.assertNotIn("com.apple.quarantine", text)

    def test_write_homebrew_cask(self) -> None:
        with TemporaryDirectory() as tmp:
            path = write_homebrew_cask(
                cask_dir=Path(tmp),
                app_name="Codex Diary",
                version="0.1.0",
                sha256="abc123",
                github_repository="coldmans/codex_diary",
            )

            self.assertEqual(path.name, "codex-diary.rb")
            self.assertIn('version "0.1.0"', path.read_text(encoding="utf-8"))

    def test_notary_credential_args_prefers_keychain_profile(self) -> None:
        self.assertEqual(
            notary_credential_args(
                keychain_profile="codex-diary-notary",
                apple_id="ignored@example.com",
                team_id="IGNORED",
                password="ignored",
            ),
            ["--keychain-profile", "codex-diary-notary"],
        )

    def test_notary_credential_args_supports_apple_credentials(self) -> None:
        self.assertEqual(
            notary_credential_args(
                apple_id="me@example.com",
                team_id="TEAMID1234",
                password="app-password",
            ),
            [
                "--apple-id",
                "me@example.com",
                "--team-id",
                "TEAMID1234",
                "--password",
                "app-password",
            ],
        )

    def test_notary_credential_args_requires_complete_credentials(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                notary_credential_args(apple_id="me@example.com")

    def test_build_notarytool_submit_command(self) -> None:
        command = build_notarytool_submit_command(
            Path("/tmp/Codex-Diary.dmg"),
            keychain_profile="codex-diary-notary",
        )

        self.assertEqual(
            command,
            [
                "xcrun",
                "notarytool",
                "submit",
                "/tmp/Codex-Diary.dmg",
                "--wait",
                "--keychain-profile",
                "codex-diary-notary",
            ],
        )

    def test_sign_app_bundle_uses_developer_id_runtime_options(self) -> None:
        with patch("codex_diary.package_macos.run_command") as run:
            sign_app_bundle(
                Path("/tmp/Codex Diary.app"),
                sign_identity="Developer ID Application: Example (TEAMID1234)",
            )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[0].args[0],
            [
                "codesign",
                "--force",
                "--deep",
                "--options",
                "runtime",
                "--timestamp",
                "--sign",
                "Developer ID Application: Example (TEAMID1234)",
                "/tmp/Codex Diary.app",
            ],
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["codesign", "--verify", "--deep", "--strict", "--verbose=2", "/tmp/Codex Diary.app"],
        )

    def test_staple_artifact_staples_and_validates(self) -> None:
        with patch("codex_diary.package_macos.run_command") as run:
            staple_artifact(Path("/tmp/Codex-Diary.dmg"))

        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["xcrun", "stapler", "staple", "/tmp/Codex-Diary.dmg"],
                ["xcrun", "stapler", "validate", "/tmp/Codex-Diary.dmg"],
            ],
        )

    def test_app_bundle_path(self) -> None:
        self.assertEqual(app_bundle_path(Path("/tmp/dist"), "Codex Diary"), Path("/tmp/dist/Codex Diary.app"))

    def test_auxiliary_dist_path(self) -> None:
        self.assertEqual(auxiliary_dist_path(Path("/tmp/dist"), "Codex Diary"), Path("/tmp/dist/Codex Diary"))

    def test_default_app_icon_source(self) -> None:
        path = default_app_icon_source()
        self.assertEqual(path.name, "app-icon.png")
        self.assertTrue(str(path).endswith("codex_diary/ui/assets/app-icon.png"))

    def test_opening_instructions_explain_unsigned_app(self) -> None:
        text = opening_instructions_text("Codex Diary")

        self.assertIn("unsigned macOS build", text)
        self.assertIn("Control-click", text)
        self.assertIn("xattr -dr com.apple.quarantine", text)

    def test_prepare_dmg_staging_includes_opening_instructions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_app = root / "Codex Diary.app"
            contents = source_app / "Contents"
            contents.mkdir(parents=True)
            (contents / "Info.plist").write_text("{}", encoding="utf-8")
            staging = root / "stage"

            prepare_dmg_staging(source_app, staging)

            self.assertTrue((staging / "Codex Diary.app").exists())
            self.assertTrue((staging / "Applications").is_symlink())
            instructions = staging / opening_instructions_filename()
            self.assertTrue(instructions.exists())
            self.assertIn("Control-click", instructions.read_text(encoding="utf-8"))

    def test_update_app_bundle_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            app = Path(tmp) / "Codex Diary.app"
            contents = app / "Contents"
            contents.mkdir(parents=True)
            info_path = contents / "Info.plist"
            with info_path.open("wb") as handle:
                plistlib.dump({"CFBundleIdentifier": "Codex Diary"}, handle)

            update_app_bundle_metadata(app, app_name="Codex Diary", version="0.1.0")

            with info_path.open("rb") as handle:
                info = plistlib.load(handle)
            self.assertEqual(info["CFBundleIdentifier"], BUNDLE_IDENTIFIER)
            self.assertEqual(info["CFBundleShortVersionString"], "0.1.0")
            self.assertEqual(info["CFBundleVersion"], "0.1.0")

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
