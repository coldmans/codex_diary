from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .chronicle import resolve_target_date
from .generator import build_diary


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-diary",
        description="Chronicle Markdown 요약으로 한국어 작업 일기 초안을 생성합니다.",
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
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not 0 <= args.day_boundary_hour <= 23:
        print("--day-boundary-hour는 0 이상 23 이하의 정수여야 합니다.", file=sys.stderr)
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
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"[warn] {warning}", file=sys.stderr)

    if args.dry_run:
        print(result.markdown, end="" if result.markdown.endswith("\n") else "\n")
        return 0

    result.output_path.parent.mkdir(parents=True, exist_ok=True)
    result.output_path.write_text(result.markdown, encoding="utf-8")
    print(f"작업 일기를 생성했습니다: {result.output_path}")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
