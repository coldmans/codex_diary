from __future__ import annotations

import json
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from .chronicle import resolve_target_date
from .diary_structure import structure_diary
from .generator import build_diary, legacy_output_paths
from .i18n import (
    DEFAULT_LANGUAGE_CODE,
    all_section_aliases,
    all_diary_headings,
    all_report_headings,
    get_language_option,
    heading_labels,
    normalize_language_code,
    supported_language_codes,
)
from .llm import CODEX_NOT_CONNECTED_MESSAGE, codex_login_command_args, get_codex_status
from .markdown_html import render_markdown

DEFAULT_SOURCE_DIR = "~/.codex/memories_extensions/chronicle/resources"
APP_NAME = "Codex Diary"
WINDOW_TITLE = "Codex Diary"
WINDOW_SIZE = (1280, 860)
WINDOW_MIN = (1040, 720)

PREVIEW_EMPTY_MESSAGE = (
    "# Codex Diary\n\n"
    "아직 앱 안에서 열려 있는 일기가 없습니다.\n\n"
    "- `생성`을 누르면 선택 날짜의 일기를 만들 수 있습니다.\n"
    "- 기준 날짜를 바꾸면 그 날짜의 저장된 일기를 바로 다시 볼 수 있습니다.\n"
    "- `해당 주 보기`로 저장된 기록을 주간 단위로 다시 탐색할 수 있습니다.\n"
)

WEEKLY_OVERVIEW_COPY = {
    "en": {
        "overview": "Weekly Overview",
        "empty": "There are no saved diary entries for this week yet.",
        "intro": "Collected {count} saved diary entries in date order.",
        "date_list": "Date List",
        "weekly_collection": "Weekly Collection",
        "no_content": "_No content_",
    },
    "ko": {
        "overview": "주간 보기",
        "empty": "아직 이 주차에 저장된 일기가 없습니다.",
        "intro": "저장된 일기 {count}개를 날짜순으로 모아 봅니다.",
        "date_list": "날짜 목록",
        "weekly_collection": "주간 모음",
        "no_content": "_내용 없음_",
    },
    "ja": {
        "overview": "週間ビュー",
        "empty": "この週にはまだ保存された日記がありません。",
        "intro": "保存された日記 {count}件を日付順にまとめて表示します。",
        "date_list": "日付一覧",
        "weekly_collection": "週間まとめ",
        "no_content": "_内容なし_",
    },
    "zh": {
        "overview": "本周概览",
        "empty": "本周还没有已保存的日记。",
        "intro": "按日期顺序汇总已保存的日记 {count} 篇。",
        "date_list": "日期列表",
        "weekly_collection": "本周汇总",
        "no_content": "_暂无内容_",
    },
    "fr": {
        "overview": "Vue hebdomadaire",
        "empty": "Aucun journal enregistre pour cette semaine.",
        "intro": "Regroupe {count} journaux enregistres par ordre chronologique.",
        "date_list": "Liste des dates",
        "weekly_collection": "Recapitulatif hebdomadaire",
        "no_content": "_Aucun contenu_",
    },
    "de": {
        "overview": "Wochenansicht",
        "empty": "Fur diese Woche gibt es noch keinen gespeicherten Tagebucheintrag.",
        "intro": "{count} gespeicherte Tagebucheintrage in Datumsreihenfolge gesammelt.",
        "date_list": "Datumliste",
        "weekly_collection": "Wochenubersicht",
        "no_content": "_Kein Inhalt_",
    },
    "es": {
        "overview": "Vista semanal",
        "empty": "Todavia no hay diarios guardados para esta semana.",
        "intro": "Agrupa {count} diarios guardados en orden de fecha.",
        "date_list": "Lista de fechas",
        "weekly_collection": "Resumen semanal",
        "no_content": "_Sin contenido_",
    },
    "vi": {
        "overview": "Tong quan tuan",
        "empty": "Tuan nay chua co nhat ky da luu.",
        "intro": "Tong hop {count} nhat ky da luu theo thu tu ngay.",
        "date_list": "Danh sach ngay",
        "weekly_collection": "Tong hop theo tuan",
        "no_content": "_Khong co noi dung_",
    },
    "th": {
        "overview": "ภาพรวมรายสัปดาห์",
        "empty": "สัปดาห์นี้ยังไม่มีไดอารีที่บันทึกไว้",
        "intro": "รวบรวมไดอารีที่บันทึกไว้ {count} รายการตามลำดับวันที่",
        "date_list": "รายการวันที่",
        "weekly_collection": "สรุปรายสัปดาห์",
        "no_content": "_ไม่มีเนื้อหา_",
    },
    "ru": {
        "overview": "Обзор недели",
        "empty": "За эту неделю еще нет сохраненных записей.",
        "intro": "Собрано {count} сохраненных записей по порядку дат.",
        "date_list": "Список дат",
        "weekly_collection": "Недельная подборка",
        "no_content": "_Нет содержимого_",
    },
    "hi": {
        "overview": "साप्ताहिक अवलोकन",
        "empty": "इस सप्ताह के लिए अभी कोई सहेजी गई डायरी नहीं है।",
        "intro": "सहेजी गई {count} डायरी प्रविष्टियों को तारीख के क्रम में इकट्ठा किया गया है।",
        "date_list": "तारीख सूची",
        "weekly_collection": "साप्ताहिक संग्रह",
        "no_content": "_कोई सामग्री नहीं_",
    },
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def application_support_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / f".{APP_NAME.lower().replace(' ', '-')}"


def default_output_dir() -> Path:
    if is_frozen_app():
        return application_support_root() / "output" / "diary"
    return repository_root() / "output" / "diary"


def ui_assets_dir() -> Path:
    if is_frozen_app():
        bundled = Path(getattr(sys, "_MEIPASS", repository_root())) / "codex_diary" / "ui"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent / "ui"


def _heading_candidates(heading: str | tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    if isinstance(heading, str):
        return (heading,)
    return tuple(heading)


def _find_heading(markdown: str, headings: tuple[str, ...], start: int = 0) -> tuple[int, str] | None:
    match: tuple[int, str] | None = None
    for heading in headings:
        idx = markdown.find(heading, start)
        if idx == -1:
            continue
        if match is None or idx < match[0]:
            match = (idx, heading)
    return match


def extract_markdown_section(
    markdown: str,
    heading: str | tuple[str, ...] | list[str] | set[str],
    next_heading: str | tuple[str, ...] | list[str] | set[str] | None = None,
) -> str:
    heading_match = _find_heading(markdown, _heading_candidates(heading))
    if heading_match is None:
        return ""
    start, matched_heading = heading_match
    if next_heading:
        next_match = _find_heading(
            markdown,
            _heading_candidates(next_heading),
            start + len(matched_heading),
        )
        if next_match is not None:
            end, _ = next_match
            return markdown[start:end].strip() + "\n"
    return markdown[start:].strip() + "\n"


def split_markdown_views(markdown: str) -> dict[str, str]:
    report = extract_markdown_section(markdown, all_report_headings(), all_diary_headings())
    diary = extract_markdown_section(markdown, all_diary_headings())
    return {
        "full": markdown.strip() + "\n",
        "report": report,
        "diary": diary,
    }


def render_views(markdown: str) -> tuple[dict[str, str], dict[str, str]]:
    raw = split_markdown_views(markdown)
    html = {key: render_markdown(value) for key, value in raw.items()}
    return raw, html


def detect_language_code_from_markdown(markdown: str) -> str:
    for code in supported_language_codes():
        labels = heading_labels(code)
        if labels["report"] in markdown or labels["diary"] in markdown:
            return code
    return DEFAULT_LANGUAGE_CODE


def canonicalize_for_structure(markdown: str) -> str:
    korean_labels = heading_labels("ko")
    section_aliases = all_section_aliases()
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        replacement = line
        for code in supported_language_codes():
            labels = heading_labels(code)
            if stripped == labels["report"]:
                replacement = korean_labels["report"]
                break
            if stripped == labels["diary"]:
                replacement = korean_labels["diary"]
                break
            if stripped.startswith("### "):
                heading = stripped[4:].strip()
                section_key = section_aliases.get(heading)
                if section_key:
                    replacement = f"### {korean_labels[section_key]}"
                    break
        lines.append(replacement)
    normalized = "\n".join(lines)
    if markdown.endswith("\n"):
        normalized += "\n"
    return normalized


def render_payload(markdown: str, output_language_code: str | None = None) -> dict[str, Any]:
    resolved_code = normalize_language_code(output_language_code) or detect_language_code_from_markdown(markdown)
    raw, html = render_views(markdown)
    return {
        "markdown": markdown,
        "views": raw,
        "views_html": html,
        "structured": structure_diary(canonicalize_for_structure(markdown)),
        "output_language_code": resolved_code,
        "output_language": get_language_option(resolved_code).label,
    }


def parse_diary_date_from_path(path: Path) -> Optional[date]:
    if path.suffix.lower() != ".md":
        return None
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def list_daily_diary_files(out_dir: Path) -> list[tuple[date, Path]]:
    if not out_dir.exists():
        return []
    items: list[tuple[date, Path]] = []
    for path in sorted(out_dir.glob("*.md")):
        parsed = parse_diary_date_from_path(path)
        if parsed is not None:
            items.append((parsed, path))
    return sorted(items, key=lambda item: item[0], reverse=True)


def week_bounds(target_date: date) -> tuple[date, date]:
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def format_week_label(start: date, end: date) -> str:
    return f"{start.isoformat()} ~ {end.isoformat()}"


def weekly_overview_copy(output_language_code: str | None) -> dict[str, str]:
    code = normalize_language_code(output_language_code) or DEFAULT_LANGUAGE_CODE
    return WEEKLY_OVERVIEW_COPY.get(code, WEEKLY_OVERVIEW_COPY[DEFAULT_LANGUAGE_CODE])


def group_diary_files_by_week(
    diary_files: list[tuple[date, Path]],
) -> list[tuple[date, date, list[tuple[date, Path]]]]:
    grouped: dict[date, list[tuple[date, Path]]] = {}
    for entry_date, path in diary_files:
        start, _ = week_bounds(entry_date)
        grouped.setdefault(start, []).append((entry_date, path))

    items = []
    for start, entries in grouped.items():
        end = start + timedelta(days=6)
        items.append((start, end, sorted(entries, key=lambda item: item[0], reverse=True)))
    return sorted(items, key=lambda item: item[0], reverse=True)


def build_weekly_overview(
    target_date: date,
    diary_files: list[tuple[date, Path]],
    output_language_code: str | None = None,
) -> str:
    start, end = week_bounds(target_date)
    week_items = [(entry_date, path) for entry_date, path in diary_files if start <= entry_date <= end]
    copy = weekly_overview_copy(output_language_code)
    if not week_items:
        return (
            f"# {format_week_label(start, end)} {copy['overview']}\n\n"
            f"> {copy['empty']}\n"
        )

    lines = [
        f"# {format_week_label(start, end)} {copy['overview']}",
        "",
        f"> {copy['intro'].format(count=len(week_items))}",
        "",
        f"## {copy['date_list']}",
    ]
    lines.extend(f"- {entry_date.isoformat()}" for entry_date, _ in week_items)
    lines.extend(["", f"## {copy['weekly_collection']}", ""])

    for index, (entry_date, path) in enumerate(week_items):
        content = path.read_text(encoding="utf-8").strip()
        lines.append(f"### {entry_date.isoformat()}")
        lines.append("")
        lines.append(content or copy["no_content"])
        if index != len(week_items) - 1:
            lines.extend(["", "---", ""])
    lines.append("")
    return "\n".join(lines)


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(path)], check=False)
        return
    if sys.platform == "win32":
        subprocess.run(["cmd", "/c", "start", "", str(path)], check=False)
        return
    raise RuntimeError("이 플랫폼에서는 결과 파일 열기를 지원하지 않습니다.")


def list_saved_entries(out_dir: Path) -> dict[str, list[dict[str, str]]]:
    diary_files = list_daily_diary_files(out_dir)
    weekly_groups = group_diary_files_by_week(diary_files)
    return {
        "dates": [
            {"date": entry_date.isoformat(), "path": str(path)}
            for entry_date, path in diary_files
        ],
        "weeks": [
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "count": len(entries),
                "label": format_week_label(start, end),
            }
            for start, end, entries in weekly_groups
        ],
    }


@dataclass
class AppConfig:
    target_date: date
    boundary_hour: int
    source_dir: Path
    out_dir: Path
    output_language_code: str

    def to_json(self) -> dict[str, Any]:
        language = get_language_option(self.output_language_code)
        return {
            "target_date": self.target_date.isoformat(),
            "boundary_hour": self.boundary_hour,
            "source_dir": str(self.source_dir.expanduser()),
            "out_dir": str(self.out_dir.expanduser()),
            "output_language_code": language.code,
            "output_language": language.label,
        }


class DiaryBridge:
    """Methods in this class are exposed to the WebView JavaScript runtime."""

    def __init__(self) -> None:
        self.config = AppConfig(
            target_date=resolve_target_date(None, day_boundary_hour=4),
            boundary_hour=4,
            source_dir=Path(DEFAULT_SOURCE_DIR).expanduser(),
            out_dir=default_output_dir(),
            output_language_code=DEFAULT_LANGUAGE_CODE,
        )
        self._generation_lock = threading.Lock()
        self._window = None

    def attach_window(self, window) -> None:
        self._window = window

    def _codex_status_details(self) -> dict[str, Any]:
        status = get_codex_status()
        connectable = status.available and sys.platform == "darwin"
        if not status.available:
            detail = "터미널에서 `codex` 명령이 보이는지 먼저 확인해 주세요."
        elif status.connected:
            detail = status.raw_output or "로그인 상태가 정상이에요."
        else:
            detail = status.raw_output or "로그인이 필요해요."
        return {
            "available": status.available,
            "connected": status.connected,
            "connectable": connectable,
            "message": "Codex에 연결되어 있어요." if status.connected else status.message or CODEX_NOT_CONNECTED_MESSAGE,
            "detail": detail,
            "command": status.command,
            "auth_mode": status.auth_mode,
        }

    def _launch_codex_device_auth(self) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("Codex 연결은 macOS에서만 바로 시작할 수 있어요.")
        command = shlex.join(codex_login_command_args(device_auth=True))
        script = (
            'tell application "Terminal"\n'
            "  activate\n"
            f"  do script {json.dumps(command)}\n"
            "end tell"
        )
        subprocess.Popen(["osascript", "-e", script], start_new_session=True)

    # ---- Read-only helpers ---------------------------------------------
    def get_state(self) -> dict[str, Any]:
        codex = self._codex_status_details()
        return {
            "config": self.config.to_json(),
            "entries": list_saved_entries(self.config.out_dir),
            "status": codex["message"] if not codex["connected"] else "날짜를 고르고 `생성`을 누르면 앱 안에서 바로 일기를 볼 수 있습니다.",
            "codex": codex,
            "generation_available": codex["connected"],
            "supported_output_languages": [
                {"code": code, "label": get_language_option(code).label}
                for code in supported_language_codes()
            ],
        }

    def list_entries(self, out_dir: str | None = None) -> dict[str, Any]:
        directory = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        return list_saved_entries(directory)

    def today(self, boundary_hour: int) -> str:
        try:
            hour = int(boundary_hour)
        except (TypeError, ValueError):
            hour = self.config.boundary_hour
        target = resolve_target_date(None, day_boundary_hour=hour)
        self.config.target_date = target
        self.config.boundary_hour = hour
        return target.isoformat()

    def recompute_target(self, iso: str, boundary_hour: int) -> str:
        try:
            hour = int(boundary_hour)
        except (TypeError, ValueError):
            hour = self.config.boundary_hour
        target = resolve_target_date(iso, day_boundary_hour=hour)
        self.config.target_date = target
        self.config.boundary_hour = hour
        return target.isoformat()

    # ---- File picking & external open ----------------------------------
    def pick_folder(self, kind: str, current: str | None = None) -> str | None:
        if self._window is None:
            return None
        import webview  # local import so tests without pywebview still work

        start = (current or "").strip() or None
        selected = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=start,
            allow_multiple=False,
        )
        if not selected:
            return None
        chosen = Path(selected[0] if isinstance(selected, (list, tuple)) else selected).expanduser()
        if kind == "source":
            self.config.source_dir = chosen
        elif kind == "out":
            self.config.out_dir = chosen
        return str(chosen)

    def open_external(self, path_str: str) -> bool:
        if not path_str:
            return False
        path = Path(path_str).expanduser()
        if not path.exists():
            return False
        try:
            open_path(path)
            return True
        except RuntimeError:
            return False

    def copy_to_clipboard(self, text: str) -> bool:
        if sys.platform == "darwin":
            try:
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return proc.returncode == 0
            except FileNotFoundError:
                return False
        return False

    def connect_codex(self) -> dict[str, Any]:
        status = self._codex_status_details()
        if status["connected"]:
            return {
                "codex": status,
                "connected": True,
                "message": "이미 Codex에 연결되어 있어요.",
            }
        if not status["connectable"]:
            return {
                "codex": status,
                "connected": False,
                "error": "Codex 연결은 macOS에서만 바로 시작할 수 있어요.",
            }
        try:
            self._launch_codex_device_auth()
        except Exception as exc:  # noqa: BLE001 - surface launch failure to UI
            return {
                "codex": status,
                "connected": False,
                "error": str(exc),
            }
        return {
            "codex": self._codex_status_details(),
            "connected": False,
            "message": "Terminal에서 Codex 로그인 창을 열었어요. 완료한 뒤 상태를 다시 확인해 주세요.",
        }

    # ---- Generation & loading ------------------------------------------
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        codex = self._codex_status_details()
        if not codex["connected"]:
            return {"error": "먼저 codex를 연결해주세요.", "codex": codex, "generation_available": False}
        if not self._generation_lock.acquire(blocking=False):
            return {"error": "이미 생성이 진행 중입니다."}
        try:
            request = self._coerce_request(payload)
            self.config.target_date = request["target_date"]
            self.config.boundary_hour = request["boundary_hour"]
            self.config.source_dir = request["source_dir"]
            self.config.out_dir = request["out_dir"]
            self.config.output_language_code = request["output_language_code"]

            result = build_diary(
                target_date=request["target_date"],
                mode=request["mode"],
                source_dir=request["source_dir"],
                out_dir=request["out_dir"],
                day_boundary_hour=request["boundary_hour"],
                output_language=request["output_language_code"],
            )
            saved_path: Optional[Path] = None
            if request["auto_save"]:
                for legacy_path in legacy_output_paths(request["out_dir"], result.target_date.isoformat()):
                    if legacy_path.exists():
                        legacy_path.unlink()
                result.output_path.parent.mkdir(parents=True, exist_ok=True)
                result.output_path.write_text(result.markdown, encoding="utf-8")
                saved_path = result.output_path

            payload = render_payload(result.markdown, output_language_code=request["output_language_code"])
            payload.update(
                {
                    "target_date": result.target_date.isoformat(),
                    "mode": result.mode,
                    "used_llm": result.used_llm,
                    "stats": dict(result.stats),
                    "warnings": list(result.warnings),
                    "saved_path": str(saved_path) if saved_path else None,
                    "output_language_code": request["output_language_code"],
                    "output_language": get_language_option(request["output_language_code"]).label,
                }
            )
            return payload
        except Exception as exc:  # noqa: BLE001 — surface all errors to UI
            return {"error": str(exc)}
        finally:
            self._generation_lock.release()

    def load_date(self, iso: str, out_dir: str | None = None) -> dict[str, Any]:
        directory = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        path = directory / f"{iso}.md"
        if not path.exists():
            return {"error": f"{iso} 날짜의 저장된 일기를 찾지 못했습니다."}
        markdown = path.read_text(encoding="utf-8")
        payload = render_payload(markdown)
        self.config.output_language_code = payload["output_language_code"]
        payload.update({"target_date": iso, "saved_path": str(path)})
        return payload

    def load_week(
        self,
        iso: str,
        out_dir: str | None = None,
        output_language_code: str | None = None,
    ) -> dict[str, Any]:
        try:
            anchor = date.fromisoformat(iso)
        except ValueError:
            return {"error": f"잘못된 날짜 형식입니다: {iso}"}
        directory = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        language_code = (
            normalize_language_code(output_language_code)
            or normalize_language_code(self.config.output_language_code)
            or DEFAULT_LANGUAGE_CODE
        )
        self.config.output_language_code = language_code
        diary_files = list_daily_diary_files(directory)
        markdown = build_weekly_overview(anchor, diary_files, output_language_code=language_code)
        payload = render_payload(markdown, output_language_code=language_code)
        start, end = week_bounds(anchor)
        payload.update(
            {
                "label": format_week_label(start, end),
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
        )
        return payload

    # ---- Internal helpers ---------------------------------------------
    @staticmethod
    def _coerce_request(payload: dict[str, Any]) -> dict[str, Any]:
        iso = str(payload.get("target_date") or date.today().isoformat())
        boundary_raw = payload.get("boundary_hour", 4)
        try:
            boundary = int(boundary_raw)
        except (TypeError, ValueError):
            boundary = 4
        boundary = max(0, min(23, boundary))
        mode = payload.get("mode") or "finalize"
        if mode not in {"finalize", "draft-update"}:
            mode = "finalize"
        source_dir = Path(str(payload.get("source_dir") or DEFAULT_SOURCE_DIR)).expanduser()
        out_dir = Path(str(payload.get("out_dir") or default_output_dir())).expanduser()
        language_code = None
        for key in (
            "output_language_code",
            "target_language_code",
            "preferred_language_code",
            "language_code",
            "output_language",
            "target_language",
            "preferred_language",
            "language",
            "locale",
        ):
            language_code = normalize_language_code(payload.get(key))
            if language_code:
                break
        target_date = resolve_target_date(iso, day_boundary_hour=boundary)
        return {
            "target_date": target_date,
            "boundary_hour": boundary,
            "mode": mode,
            "source_dir": source_dir,
            "out_dir": out_dir,
            "auto_save": bool(payload.get("auto_save", True)),
            "output_language_code": language_code or DEFAULT_LANGUAGE_CODE,
        }


def main() -> None:
    import webview  # imported lazily so test suite doesn't require it

    bridge = DiaryBridge()
    assets = ui_assets_dir()
    entry = assets / "index.html"
    if not entry.exists():
        raise SystemExit(f"UI 에셋을 찾지 못했습니다: {entry}")

    window = webview.create_window(
        WINDOW_TITLE,
        url=str(entry),
        js_api=bridge,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN,
        background_color="#fdf1ec",
    )
    bridge.attach_window(window)
    webview.start()


if __name__ == "__main__":
    main()
