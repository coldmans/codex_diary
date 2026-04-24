from __future__ import annotations

import argparse
import hashlib
import importlib.util
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__

APP_NAME = "Codex Diary"
BUNDLE_IDENTIFIER = "io.github.coldmans.codex-diary"
DEFAULT_GITHUB_REPOSITORY = "coldmans/codex_diary"
ICONSET_SPECS = (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sanitize_artifact_name(app_name: str) -> str:
    cleaned = "".join(char if char.isalnum() else "-" for char in app_name)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "codex-diary"


def default_dist_dir() -> Path:
    return repository_root() / "dist"


def default_build_dir() -> Path:
    return repository_root() / "build" / "macos"


def default_homebrew_cask_dir() -> Path:
    return repository_root() / "Casks"


def default_app_icon_source() -> Path:
    return repository_root() / "codex_diary" / "ui" / "assets" / "app-icon.png"


def default_dmg_name(app_name: str, version: str) -> str:
    return f"{sanitize_artifact_name(app_name)}-{version}-macOS.dmg"


def homebrew_cask_token(app_name: str) -> str:
    return sanitize_artifact_name(app_name).lower()


def homebrew_cask_filename(app_name: str) -> str:
    return f"{homebrew_cask_token(app_name)}.rb"


def github_release_dmg_url(*, github_repository: str, app_name: str, version: str) -> str:
    repository = github_repository.strip().strip("/")
    return f"https://github.com/{repository}/releases/download/v{version}/{default_dmg_name(app_name, version)}"


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_homebrew_cask_text(
    *,
    app_name: str,
    version: str,
    sha256: str,
    github_repository: str = DEFAULT_GITHUB_REPOSITORY,
    bundle_identifier: str = BUNDLE_IDENTIFIER,
) -> str:
    repository = github_repository.strip().strip("/")
    token = homebrew_cask_token(app_name)
    url = github_release_dmg_url(
        github_repository=repository,
        app_name=app_name,
        version="#{version}",
    )
    return (
        f'cask "{token}" do\n'
        f'  version "{version}"\n'
        f'  sha256 "{sha256}"\n'
        "\n"
        f'  url "{url}",\n'
        f'      verified: "github.com/{repository}/"\n'
        f'  name "{app_name}"\n'
        '  desc "Generate diary drafts from Chronicle Markdown summaries"\n'
        f'  homepage "https://github.com/{repository}"\n'
        "\n"
        f'  app "{app_name}.app"\n'
        "\n"
        "  caveats <<~EOS\n"
        f"    {app_name} is currently distributed as an unsigned macOS build.\n"
        "    If macOS blocks first launch, Control-click the app in Finder and choose Open.\n"
        "  EOS\n"
        "\n"
        "  zap trash: [\n"
        f'    "~/Library/Application Support/{app_name}",\n'
        f'    "~/Library/Caches/{bundle_identifier}",\n'
        f'    "~/Library/Preferences/{bundle_identifier}.plist",\n'
        "  ]\n"
        "end\n"
    )


def write_homebrew_cask(
    *,
    cask_dir: Path,
    app_name: str,
    version: str,
    sha256: str,
    github_repository: str = DEFAULT_GITHUB_REPOSITORY,
) -> Path:
    cask_dir.mkdir(parents=True, exist_ok=True)
    cask_path = cask_dir / homebrew_cask_filename(app_name)
    cask_path.write_text(
        build_homebrew_cask_text(
            app_name=app_name,
            version=version,
            sha256=sha256,
            github_repository=github_repository,
        ),
        encoding="utf-8",
    )
    return cask_path


def app_bundle_path(dist_dir: Path, app_name: str) -> Path:
    return dist_dir / f"{app_name}.app"


def auxiliary_dist_path(dist_dir: Path, app_name: str) -> Path:
    return dist_dir / app_name


def opening_instructions_filename() -> str:
    return "If macOS blocks opening.txt"


def opening_instructions_text(app_name: str) -> str:
    return (
        f"{app_name} is currently distributed as an unsigned macOS build.\n\n"
        "If macOS says Apple cannot check the app for malicious software:\n\n"
        "1. Drag the app to Applications.\n"
        "2. In Finder, Control-click the app and choose Open.\n"
        "3. Click Open in the confirmation dialog.\n\n"
        "Alternative for advanced users:\n\n"
        f"xattr -dr com.apple.quarantine \"/Applications/{app_name}.app\"\n\n"
        "A future notarized release can remove this warning, but that requires an Apple Developer ID certificate.\n"
    )


def update_app_bundle_metadata(
    app_bundle: Path,
    *,
    app_name: str,
    version: str,
    bundle_identifier: str = BUNDLE_IDENTIFIER,
) -> None:
    info_path = app_bundle / "Contents" / "Info.plist"
    if not info_path.exists():
        raise RuntimeError(f"앱 번들 Info.plist를 찾지 못했습니다: {info_path}")
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleIdentifier"] = bundle_identifier
    info["CFBundleName"] = app_name
    info["CFBundleDisplayName"] = app_name
    info["CFBundleShortVersionString"] = version
    info["CFBundleVersion"] = version
    with info_path.open("wb") as handle:
        plistlib.dump(info, handle)


def ad_hoc_sign_app_bundle(app_bundle: Path) -> None:
    run_command(["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)])


def ensure_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("macOS DMG 빌드는 macOS에서만 실행할 수 있습니다.")


def ensure_pyinstaller_installed() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        raise RuntimeError(
            'PyInstaller가 설치되어 있지 않습니다. 먼저 `pip install -e ".[macos-build]"`를 실행해 주세요.'
        )


def run_command(args: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd) if cwd else None, check=True)


def build_app_icon(*, source_png: Path, build_dir: Path, app_name: str) -> Path:
    if not source_png.exists():
        raise RuntimeError(f"앱 아이콘 소스 PNG를 찾지 못했습니다: {source_png}")

    icon_root = build_dir / "icon"
    iconset_dir = icon_root / f"{sanitize_artifact_name(app_name)}.iconset"
    icns_path = icon_root / f"{sanitize_artifact_name(app_name)}.icns"

    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    icon_root.mkdir(parents=True, exist_ok=True)
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for filename, size in ICONSET_SPECS:
        run_command(
            [
                "sips",
                "-z",
                str(size),
                str(size),
                str(source_png),
                "--out",
                str(iconset_dir / filename),
            ]
        )

    if icns_path.exists():
        icns_path.unlink()
    run_command(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)])

    if not icns_path.exists():
        raise RuntimeError(f"macOS 앱 아이콘 생성이 끝났지만 .icns 파일을 찾지 못했습니다: {icns_path}")
    return icns_path


def build_pyinstaller_app(
    *,
    app_name: str,
    dist_dir: Path,
    build_dir: Path,
) -> Path:
    root = repository_root()
    launcher = root / "codex_diary" / "app_launcher.py"
    if not launcher.exists():
        raise RuntimeError(f"앱 런처 파일을 찾지 못했습니다: {launcher}")

    pyinstaller_work = build_dir / "pyinstaller"
    spec_path = build_dir / "spec"
    spec_path.mkdir(parents=True, exist_ok=True)
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    ui_dir = root / "codex_diary" / "ui"
    app_icon = build_app_icon(
        source_png=default_app_icon_source(),
        build_dir=build_dir,
        app_name=app_name,
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        app_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(pyinstaller_work),
        "--specpath",
        str(spec_path),
        "--paths",
        str(root),
        "--icon",
        str(app_icon),
        "--collect-submodules",
        "webview",
        "--collect-data",
        "webview",
        "--add-data",
        f"{ui_dir}:codex_diary/ui",
        str(launcher),
    ]
    run_command(command, cwd=root)
    bundle = app_bundle_path(dist_dir, app_name)
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller 빌드가 끝났지만 앱 번들을 찾지 못했습니다: {bundle}")
    update_app_bundle_metadata(bundle, app_name=app_name, version=__version__)
    ad_hoc_sign_app_bundle(bundle)
    return bundle


def prepare_dmg_staging(app_bundle: Path, staging_dir: Path) -> Path:
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    copied_bundle = staging_dir / app_bundle.name
    shutil.copytree(app_bundle, copied_bundle, symlinks=True)

    applications_link = staging_dir / "Applications"
    if applications_link.exists() or applications_link.is_symlink():
        applications_link.unlink()
    applications_link.symlink_to("/Applications")

    instructions = staging_dir / opening_instructions_filename()
    instructions.write_text(opening_instructions_text(app_bundle.stem), encoding="utf-8")
    return copied_bundle


def create_dmg(
    *,
    source_dir: Path,
    output_path: Path,
    volume_name: str,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    command = [
        "hdiutil",
        "create",
        "-volname",
        volume_name,
        "-srcfolder",
        str(source_dir),
        "-ov",
        "-format",
        "UDZO",
        str(output_path),
    ]
    run_command(command)
    if not output_path.exists():
        raise RuntimeError(f"DMG 생성이 끝났지만 결과 파일을 찾지 못했습니다: {output_path}")
    return output_path


def cleanup_packaging_artifacts(*, dist_dir: Path, build_dir: Path, app_name: str) -> None:
    helper_dist = auxiliary_dist_path(dist_dir, app_name)
    if helper_dist.exists() and helper_dist.is_dir():
        shutil.rmtree(helper_dist)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_root = build_dir.parent
    if build_root.exists() and build_root.is_dir() and not any(build_root.iterdir()):
        build_root.rmdir()
    ds_store = dist_dir / ".DS_Store"
    if ds_store.exists():
        ds_store.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-diary-package-macos",
        description="Codex Diary macOS 앱 번들과 DMG를 생성합니다.",
    )
    parser.add_argument(
        "--app-name",
        default=APP_NAME,
        help="앱 번들 이름입니다. 기본값은 'Codex Diary'입니다.",
    )
    parser.add_argument(
        "--dist-dir",
        default=str(default_dist_dir()),
        help="최종 앱 번들과 DMG를 저장할 폴더입니다.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(default_build_dir()),
        help="PyInstaller 작업 파일과 DMG staging 파일을 둘 폴더입니다.",
    )
    parser.add_argument(
        "--skip-dmg",
        action="store_true",
        help="DMG 생성은 건너뛰고 .app 번들까지만 만듭니다.",
    )
    parser.add_argument(
        "--write-homebrew-cask",
        action="store_true",
        help="생성된 DMG SHA256을 사용해 Homebrew Cask 파일도 갱신합니다.",
    )
    parser.add_argument(
        "--homebrew-cask-dir",
        default=str(default_homebrew_cask_dir()),
        help="Homebrew Cask 파일을 저장할 폴더입니다.",
    )
    parser.add_argument(
        "--github-repository",
        default=DEFAULT_GITHUB_REPOSITORY,
        help="릴리즈 DMG URL에 사용할 GitHub 저장소입니다. 예: owner/repo",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ensure_macos()
    ensure_pyinstaller_installed()

    app_name = args.app_name.strip() or APP_NAME
    dist_dir = Path(args.dist_dir).expanduser().resolve()
    build_dir = Path(args.build_dir).expanduser().resolve()

    bundle = build_pyinstaller_app(
        app_name=app_name,
        dist_dir=dist_dir,
        build_dir=build_dir,
    )
    print(f"앱 번들을 생성했습니다: {bundle}")

    if args.skip_dmg:
        cleanup_packaging_artifacts(dist_dir=dist_dir, build_dir=build_dir, app_name=app_name)
        return 0

    dmg_root = build_dir / "dmg-root"
    prepare_dmg_staging(bundle, dmg_root)
    dmg_path = dist_dir / default_dmg_name(app_name, __version__)
    create_dmg(
        source_dir=dmg_root,
        output_path=dmg_path,
        volume_name=app_name,
    )
    print(f"DMG를 생성했습니다: {dmg_path}")
    dmg_sha256 = calculate_sha256(dmg_path)
    print(f"DMG SHA256: {dmg_sha256}")
    if args.write_homebrew_cask:
        cask_path = write_homebrew_cask(
            cask_dir=Path(args.homebrew_cask_dir).expanduser().resolve(),
            app_name=app_name,
            version=__version__,
            sha256=dmg_sha256,
            github_repository=args.github_repository,
        )
        print(f"Homebrew Cask를 갱신했습니다: {cask_path}")
    cleanup_packaging_artifacts(dist_dir=dist_dir, build_dir=build_dir, app_name=app_name)
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
