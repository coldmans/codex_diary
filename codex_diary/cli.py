from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .chronicle import resolve_target_date
from .diary_length import (
    DEFAULT_DIARY_LENGTH_CODE,
    normalize_diary_length,
    supported_diary_length_codes,
)
from .generator import build_diary, legacy_output_paths
from .llm import LLMError
from .i18n import (
    DEFAULT_LANGUAGE_CODE,
    get_language_option,
    normalize_language_code,
    supported_language_codes,
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-diary",
        description="Chronicle Markdown 요약으로 작업 일기 초안을 생성합니다.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("draft-update", "finalize"),
        default="finalize",
        help="draft-update는 누적 초안을, finalize는 최종 일기를 생성합니다. 기본값은 finalize입니다.",
    )
    parser.add_argument(
        "--date",
        help="특정 날짜의 일기를 생성합니다. 형식: YYYY-MM-DD",
    )
    parser.add_argument(
        "--source-dir",
        default="~/.codex/memories_extensions/chronicle/resources",
        help="Chronicle Markdown 요약 폴더 경로를 지정합니다.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(repository_root() / "output" / "diary"),
        help="결과 Markdown을 저장할 폴더입니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 저장하지 않고 결과를 stdout으로 출력합니다.",
    )
    parser.add_argument(
        "--day-boundary-hour",
        type=int,
        default=4,
        help="하루 경계 시각(로컬 타임존 기준, 기본값: 4). 0~23 사이 정수여야 합니다.",
    )
    parser.add_argument(
        "--language",
        "--output-language",
        dest="language",
        default=DEFAULT_LANGUAGE_CODE,
        help=(
            "출력 언어를 지정합니다. "
            f"지원 코드: {', '.join(supported_language_codes())}. 기본값은 en입니다."
        ),
    )
    parser.add_argument(
        "--length",
        "--diary-length",
        dest="diary_length",
        default=DEFAULT_DIARY_LENGTH_CODE,
        help=(
            "일기 길이를 지정합니다. "
            f"지원 값: {', '.join(supported_diary_length_codes())}. 기본값은 short입니다."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not 0 <= args.day_boundary_hour <= 23:
        print("--day-boundary-hour는 0 이상 23 이하의 정수여야 합니다.", file=sys.stderr)
        return 2
    language_code = normalize_language_code(args.language)
    if not language_code:
        print(
            "--language는 지원되는 언어 코드 또는 이름이어야 합니다. "
            f"지원 코드: {', '.join(supported_language_codes())}",
            file=sys.stderr,
        )
        return 2
    diary_length_code = normalize_diary_length(args.diary_length)
    if not diary_length_code:
        print(
            "--length는 지원되는 길이 코드여야 합니다. "
            f"지원 값: {', '.join(supported_diary_length_codes())}",
            file=sys.stderr,
        )
        return 2

    try:
        target_date = resolve_target_date(
            args.date,
            day_boundary_hour=args.day_boundary_hour,
        )
    except ValueError:
        print("--date는 YYYY-MM-DD 형식이어야 합니다.", file=sys.stderr)
        return 2

    source_dir = Path(args.source_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()

    try:
        result = build_diary(
            target_date=target_date,
            mode=args.mode,
            source_dir=source_dir,
            out_dir=out_dir,
            day_boundary_hour=args.day_boundary_hour,
            output_language=language_code,
            diary_length=diary_length_code,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except LLMError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"[warn] {warning}", file=sys.stderr)

    if args.dry_run:
        print(result.markdown, end="" if result.markdown.endswith("\n") else "\n")
        return 0

    for legacy_path in legacy_output_paths(out_dir, target_date.isoformat()):
        if legacy_path.exists():
            legacy_path.unlink()
    result.output_path.parent.mkdir(parents=True, exist_ok=True)
    result.output_path.write_text(result.markdown, encoding="utf-8")
    print(
        f"작업 일기를 생성했습니다: {result.output_path} "
        f"({get_language_option(language_code).label})"
    )
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
