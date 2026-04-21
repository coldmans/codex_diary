from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__

APP_NAME = "Codex Diary"


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


def default_dmg_name(app_name: str, version: str) -> str:
    return f"{sanitize_artifact_name(app_name)}-{version}-macOS.dmg"


def app_bundle_path(dist_dir: Path, app_name: str) -> Path:
    return dist_dir / f"{app_name}.app"


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
        str(launcher),
    ]
    run_command(command, cwd=root)
    bundle = app_bundle_path(dist_dir, app_name)
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller 빌드가 끝났지만 앱 번들을 찾지 못했습니다: {bundle}")
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
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
