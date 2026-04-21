from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import Optional

from tkinter import (
    BooleanVar,
    Button,
    Canvas,
    Checkbutton,
    DISABLED,
    Frame,
    NORMAL,
    Radiobutton,
    Scrollbar,
    StringVar,
    Tk,
    filedialog,
    messagebox,
)

from .chronicle import resolve_target_date
from .generator import build_diary
from .models import DiaryBuildResult

DEFAULT_SOURCE_DIR = "~/.codex/memories_extensions/chronicle/resources"
APP_BACKGROUND = "#f3f2ee"
PANEL_BACKGROUND = "#ffffff"
TEXT_BACKGROUND = "#fbfbf8"
BORDER_COLOR = "#d7d4cc"
ACCENT_COLOR = "#2850a7"
WARNING_COLOR = "#9a5a00"
TEXT_COLOR = "#202020"
SUBTEXT_COLOR = "#5a5f73"
APP_NAME = "Codex Diary"
PREVIEW_EMPTY_MESSAGE = (
    "# Codex Diary\n\n"
    "아직 앱 안에서 열려 있는 일기가 없습니다.\n\n"
    "- `생성`을 누르면 선택 날짜의 일기를 만들 수 있습니다.\n"
    "- `결과 보기`는 가장 최근 결과를 앱 안에서 엽니다.\n"
    "- `선택 날짜 보기`와 `해당 주 보기`로 저장된 일기를 다시 탐색할 수 있습니다.\n"
)


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


def default_text_font(size: int = 13) -> tuple[str, int]:
    if sys.platform == "darwin":
        return ("Apple SD Gothic Neo", size)
    return ("TkDefaultFont", size)


def compact_path(path: Path, *, max_length: int = 42) -> str:
    text = str(path.expanduser())
    if len(text) <= max_length:
        return text
    return "..." + text[-(max_length - 3) :]


def extract_markdown_section(markdown: str, heading: str, next_heading: str | None = None) -> str:
    start = markdown.find(heading)
    if start == -1:
        return ""
    if next_heading:
        end = markdown.find(next_heading, start + len(heading))
        if end != -1:
            return markdown[start:end].strip() + "\n"
    return markdown[start:].strip() + "\n"


def split_markdown_views(markdown: str) -> dict[str, str]:
    report = extract_markdown_section(markdown, "## 금일 작업 보고서", "## 오늘의 일기 버전")
    diary = extract_markdown_section(markdown, "## 오늘의 일기 버전")
    return {
        "full": markdown.strip() + "\n",
        "report": report,
        "diary": diary,
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


def group_diary_files_by_week(diary_files: list[tuple[date, Path]]) -> list[tuple[date, date, list[tuple[date, Path]]]]:
    grouped: dict[date, list[tuple[date, Path]]] = {}
    for entry_date, path in diary_files:
        start, _ = week_bounds(entry_date)
        grouped.setdefault(start, []).append((entry_date, path))

    items = []
    for start, entries in grouped.items():
        end = start + timedelta(days=6)
        items.append((start, end, sorted(entries, key=lambda item: item[0], reverse=True)))
    return sorted(items, key=lambda item: item[0], reverse=True)


def build_weekly_overview(target_date: date, diary_files: list[tuple[date, Path]]) -> str:
    start, end = week_bounds(target_date)
    week_items = [(entry_date, path) for entry_date, path in diary_files if start <= entry_date <= end]
    if not week_items:
        return (
            f"# {format_week_label(start, end)} 주간 보기\n\n"
            "> 아직 이 주차에 저장된 일기가 없습니다.\n"
        )

    lines = [
        f"# {format_week_label(start, end)} 주간 보기",
        "",
        f"> 저장된 일기 {len(week_items)}개를 날짜순으로 모아 봅니다.",
        "",
        "## 날짜 목록",
    ]
    lines.extend(f"- {entry_date.isoformat()}" for entry_date, _ in week_items)
    lines.extend(["", "## 주간 모음", ""])

    for index, (entry_date, path) in enumerate(week_items):
        content = path.read_text(encoding="utf-8").strip()
        lines.append(f"### {entry_date.isoformat()}")
        lines.append("")
        lines.append(content or "_내용 없음_")
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


@dataclass
class GenerationSuccess:
    result: DiaryBuildResult
    saved: bool


@dataclass
class GenerationFailure:
    message: str


@dataclass
class GenerationRequest:
    target_date: date
    boundary_hour: int
    mode: str
    source_dir: Path
    out_dir: Path
    auto_save: bool


class DiaryDesktopApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Codex Diary")
        self.root.geometry("1280x860")
        self.root.minsize(1040, 760)
        self.root.configure(bg=APP_BACKGROUND)

        self.queue: queue.Queue[GenerationSuccess | GenerationFailure] = queue.Queue()
        self.current_result: Optional[DiaryBuildResult] = None
        self.current_view_path: Optional[Path] = None
        self.target_date = resolve_target_date(None, day_boundary_hour=4)
        self.boundary_hour = 4
        self.source_dir = Path(DEFAULT_SOURCE_DIR).expanduser()
        self.out_dir = default_output_dir()

        self.mode_var = StringVar(value="finalize")
        self.view_var = StringVar(value="full")
        self.auto_save_var = BooleanVar(value=True)

        self.status_message = "날짜를 고르고 `생성`을 누르면 앱 안에서 바로 일기를 볼 수 있습니다."
        self.meta_message = f"출력 폴더: {self.out_dir}"
        self.warning_message = ""
        self.preview_content = PREVIEW_EMPTY_MESSAGE
        self.view_contents = split_markdown_views(PREVIEW_EMPTY_MESSAGE)

        self.generate_button: Optional[Button] = None
        self.open_button: Optional[Button] = None
        self.external_open_button: Optional[Button] = None
        self.copy_button: Optional[Button] = None
        self.date_button: Optional[Button] = None
        self.boundary_button: Optional[Button] = None
        self.source_button: Optional[Button] = None
        self.out_button: Optional[Button] = None
        self.preview_canvas: Optional[Canvas] = None
        self.preview_inner: Optional[Frame] = None
        self.status_frame: Optional[Frame] = None
        self.sidebar_canvas: Optional[Canvas] = None
        self.sidebar_inner: Optional[Frame] = None

        self._build_ui()
        self._update_controls()
        self._render_status()
        self._render_preview()
        self._refresh_saved_lists()
        self.root.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        controls = Frame(self.root, bg=PANEL_BACKGROUND, bd=1, relief="solid")
        controls.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        controls.columnconfigure(0, weight=1)

        date_frame = Frame(controls, bg=PANEL_BACKGROUND)
        date_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        Button(date_frame, text="전날", command=lambda: self._shift_date(-1)).pack(side="left")
        self.date_button = Button(date_frame, text="", command=self._open_selected_date_in_app)
        self.date_button.pack(side="left", padx=(8, 8))
        Button(date_frame, text="다음날", command=lambda: self._shift_date(1)).pack(side="left")
        Button(date_frame, text="오늘 기준", command=self._reset_date_to_today).pack(side="left", padx=(8, 0))
        Button(date_frame, text="-1h", command=lambda: self._shift_boundary(-1)).pack(side="left", padx=(18, 0))
        self.boundary_button = Button(date_frame, text="", command=lambda: None)
        self.boundary_button.pack(side="left", padx=(8, 8))
        Button(date_frame, text="+1h", command=lambda: self._shift_boundary(1)).pack(side="left")

        path_frame = Frame(controls, bg=PANEL_BACKGROUND)
        path_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.source_button = Button(path_frame, text="", command=self._choose_source_dir)
        self.source_button.pack(side="left")
        self.out_button = Button(path_frame, text="", command=self._choose_out_dir)
        self.out_button.pack(side="left", padx=(8, 0))
        Button(path_frame, text="목록 새로고침", command=self._refresh_saved_lists).pack(side="right")

        action_frame = Frame(controls, bg=PANEL_BACKGROUND)
        action_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        Radiobutton(
            action_frame,
            text="최종 일기",
            value="finalize",
            variable=self.mode_var,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left")
        Radiobutton(
            action_frame,
            text="초안 갱신",
            value="draft-update",
            variable=self.mode_var,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left", padx=(10, 0))
        Checkbutton(
            action_frame,
            text="생성 후 바로 저장",
            variable=self.auto_save_var,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left", padx=(14, 0))

        self.generate_button = Button(action_frame, text="생성", command=self._start_generation)
        self.generate_button.pack(side="right")
        self.external_open_button = Button(
            action_frame,
            text="외부 앱 열기",
            command=self._open_output_file_external,
            state=DISABLED,
        )
        self.external_open_button.pack(side="right", padx=(0, 8))
        self.open_button = Button(
            action_frame,
            text="결과 보기",
            command=self._open_output_file,
            state=DISABLED,
        )
        self.open_button.pack(side="right", padx=(0, 8))
        self.copy_button = Button(
            action_frame,
            text="현재 보기 복사",
            command=self._copy_current_view,
            state=DISABLED,
        )
        self.copy_button.pack(side="right", padx=(0, 8))

        view_frame = Frame(controls, bg=PANEL_BACKGROUND)
        view_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        Radiobutton(
            view_frame,
            text="전체 Markdown",
            value="full",
            variable=self.view_var,
            command=self._refresh_view,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left")
        Radiobutton(
            view_frame,
            text="금일 작업 보고서",
            value="report",
            variable=self.view_var,
            command=self._refresh_view,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left", padx=(10, 0))
        Radiobutton(
            view_frame,
            text="오늘의 일기",
            value="diary",
            variable=self.view_var,
            command=self._refresh_view,
            bg=PANEL_BACKGROUND,
            activebackground=PANEL_BACKGROUND,
        ).pack(side="left", padx=(10, 0))
        Button(view_frame, text="선택 날짜 보기", command=self._open_selected_date_in_app).pack(
            side="right"
        )
        Button(view_frame, text="해당 주 보기", command=self._open_selected_week_in_app).pack(
            side="right", padx=(0, 8)
        )

        self.status_frame = Frame(self.root, bg=PANEL_BACKGROUND, bd=1, relief="solid")
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        main = Frame(self.root, bg=APP_BACKGROUND)
        main.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)

        preview_frame = Frame(main, bg=PANEL_BACKGROUND, bd=1, relief="solid")
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview_canvas = Canvas(
            preview_frame,
            bg=TEXT_BACKGROUND,
            bd=0,
            highlightthickness=0,
            yscrollincrement=24,
        )
        preview_scrollbar = Scrollbar(preview_frame, command=self.preview_canvas.yview)
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_inner = Frame(self.preview_canvas, bg=TEXT_BACKGROUND)
        self.preview_canvas.create_window((0, 0), window=self.preview_inner, anchor="nw")
        self.preview_inner.bind(
            "<Configure>",
            lambda _: self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all")),
        )
        self.preview_canvas.bind("<Configure>", lambda _: self._render_preview())

        sidebar_frame = Frame(main, bg=PANEL_BACKGROUND, bd=1, relief="solid", width=280)
        sidebar_frame.grid(row=0, column=1, sticky="ns")
        sidebar_frame.grid_propagate(False)
        sidebar_frame.columnconfigure(0, weight=1)
        sidebar_frame.rowconfigure(0, weight=1)
        self.sidebar_canvas = Canvas(sidebar_frame, bg=PANEL_BACKGROUND, bd=0, highlightthickness=0)
        sidebar_scrollbar = Scrollbar(sidebar_frame, command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sidebar_inner = Frame(self.sidebar_canvas, bg=PANEL_BACKGROUND)
        self.sidebar_canvas.create_window((0, 0), window=self.sidebar_inner, anchor="nw")
        self.sidebar_inner.bind(
            "<Configure>",
            lambda _: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all")),
        )

    def _update_controls(self) -> None:
        if self.date_button is not None:
            self.date_button.configure(text=f"날짜 {self.target_date.isoformat()}")
        if self.boundary_button is not None:
            self.boundary_button.configure(text=f"하루 경계 {self.boundary_hour:02d}시")
        if self.source_button is not None:
            self.source_button.configure(text=f"입력 폴더 변경: {compact_path(self.source_dir)}")
        if self.out_button is not None:
            self.out_button.configure(text=f"출력 폴더 변경: {compact_path(self.out_dir)}")

    def _set_status(self, status: str, *, meta: str = "", warning: str = "") -> None:
        self.status_message = status
        self.meta_message = meta
        self.warning_message = warning
        self._render_status()

    def _render_status(self) -> None:
        if self.status_frame is None:
            return
        for child in self.status_frame.winfo_children():
            child.destroy()
        wrap = max(self.root.winfo_width() - 80, 760)
        lines = [
            (self.status_message, TEXT_COLOR, default_text_font(12)),
            (self.meta_message, SUBTEXT_COLOR, default_text_font(11)),
            (self.warning_message, WARNING_COLOR, default_text_font(11)),
        ]
        for text, color, font in lines:
            if not text:
                continue
            Button(
                self.status_frame,
                text=text,
                command=lambda: None,
                relief="flat",
                borderwidth=0,
                bg=PANEL_BACKGROUND,
                activebackground=PANEL_BACKGROUND,
                fg=color,
                activeforeground=color,
                anchor="w",
                justify="left",
                wraplength=wrap,
                font=font,
            ).pack(fill="x", padx=10, pady=4)

    def _set_preview_content(self, content: str) -> None:
        self.preview_content = content if content.strip() else PREVIEW_EMPTY_MESSAGE
        self._render_preview()

    def _render_preview(self) -> None:
        if self.preview_canvas is None or self.preview_inner is None:
            return
        for child in self.preview_inner.winfo_children():
            child.destroy()

        wrap = max(self.preview_canvas.winfo_width() - 48, 560)
        lines = self.preview_content.splitlines()
        if not lines:
            lines = [PREVIEW_EMPTY_MESSAGE]

        for line in lines:
            if not line.strip():
                spacer = Frame(self.preview_inner, bg=TEXT_BACKGROUND, height=8)
                spacer.pack(fill="x")
                continue
            font = default_text_font(13)
            color = TEXT_COLOR
            if line.startswith("# "):
                font = default_text_font(18)
                color = ACCENT_COLOR
            elif line.startswith("## "):
                font = default_text_font(16)
                color = ACCENT_COLOR
            elif line.startswith("### "):
                font = default_text_font(14)
                color = ACCENT_COLOR
            elif line.startswith("> "):
                font = default_text_font(12)
                color = SUBTEXT_COLOR
            Button(
                self.preview_inner,
                text=line,
                command=lambda: None,
                relief="flat",
                borderwidth=0,
                bg=TEXT_BACKGROUND,
                activebackground=TEXT_BACKGROUND,
                fg=color,
                activeforeground=color,
                anchor="w",
                justify="left",
                wraplength=wrap,
                font=font,
                padx=12,
                pady=6,
            ).pack(fill="x", padx=8, pady=1)

        self.preview_canvas.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _on_preview_mousewheel(self, event) -> str:
        if self.preview_canvas is not None:
            self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _refresh_view(self) -> None:
        key = self.view_var.get() or "full"
        self._set_preview_content(self.view_contents.get(key, PREVIEW_EMPTY_MESSAGE))

    def _refresh_saved_lists(self) -> None:
        if self.sidebar_inner is None:
            return
        for child in self.sidebar_inner.winfo_children():
            child.destroy()

        diary_files = list_daily_diary_files(self.out_dir)
        weekly_groups = group_diary_files_by_week(diary_files)

        Button(
            self.sidebar_inner,
            text="저장된 주간",
            command=lambda: None,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_COLOR,
            relief="flat",
            activebackground=PANEL_BACKGROUND,
        ).pack(fill="x", padx=8, pady=(8, 6))

        if not weekly_groups:
            Button(
                self.sidebar_inner,
                text="아직 저장된 주간이 없습니다",
                command=lambda: None,
            ).pack(fill="x", padx=8, pady=(0, 8))
        else:
            for start, end, _entries in weekly_groups[:10]:
                Button(
                    self.sidebar_inner,
                    text=format_week_label(start, end),
                    command=lambda s=start: self._open_week_start_in_app(s),
                ).pack(fill="x", padx=8, pady=(0, 6))

        Button(
            self.sidebar_inner,
            text="저장된 날짜",
            command=lambda: None,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_COLOR,
            relief="flat",
            activebackground=PANEL_BACKGROUND,
        ).pack(fill="x", padx=8, pady=(10, 6))

        if not diary_files:
            Button(
                self.sidebar_inner,
                text="아직 저장된 날짜가 없습니다",
                command=lambda: None,
            ).pack(fill="x", padx=8, pady=(0, 8))
        else:
            for entry_date, _path in diary_files[:28]:
                Button(
                    self.sidebar_inner,
                    text=entry_date.isoformat(),
                    command=lambda d=entry_date: self._open_date_in_app(d),
                ).pack(fill="x", padx=8, pady=(0, 6))

        if self.sidebar_canvas is not None:
            self.sidebar_canvas.update_idletasks()
            self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def _shift_date(self, delta_days: int) -> None:
        self.target_date = self.target_date + timedelta(days=delta_days)
        self._update_controls()

    def _reset_date_to_today(self) -> None:
        self.target_date = resolve_target_date(None, day_boundary_hour=self.boundary_hour)
        self._update_controls()

    def _shift_boundary(self, delta_hours: int) -> None:
        self.boundary_hour = max(0, min(23, self.boundary_hour + delta_hours))
        self.target_date = resolve_target_date(self.target_date.isoformat(), day_boundary_hour=self.boundary_hour)
        self._update_controls()

    def _choose_source_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.source_dir))
        if selected:
            self.source_dir = Path(selected).expanduser()
            self._update_controls()
            self._set_status(
                "입력 폴더를 변경했습니다.",
                meta=f"입력 폴더: {self.source_dir}",
            )

    def _choose_out_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.out_dir))
        if selected:
            self.out_dir = Path(selected).expanduser()
            self._update_controls()
            self._refresh_saved_lists()
            self._set_status(
                "출력 폴더를 변경했습니다.",
                meta=f"출력 폴더: {self.out_dir}",
            )

    def _start_generation(self) -> None:
        if self.generate_button is not None:
            self.generate_button.configure(state=DISABLED)

        request = GenerationRequest(
            target_date=self.target_date,
            boundary_hour=self.boundary_hour,
            mode=self.mode_var.get(),
            source_dir=self.source_dir,
            out_dir=self.out_dir,
            auto_save=self.auto_save_var.get(),
        )

        self._set_status(
            "Chronicle 요약을 읽고 일기를 생성하는 중입니다...",
            meta=f"날짜: {request.target_date.isoformat()} / 모드: {request.mode}",
        )

        worker = threading.Thread(target=self._run_generation, args=(request,), daemon=True)
        worker.start()

    def _run_generation(self, request: GenerationRequest) -> None:
        try:
            result = build_diary(
                target_date=request.target_date,
                mode=request.mode,
                source_dir=request.source_dir,
                out_dir=request.out_dir,
                day_boundary_hour=request.boundary_hour,
            )
            if request.auto_save:
                result.output_path.parent.mkdir(parents=True, exist_ok=True)
                result.output_path.write_text(result.markdown, encoding="utf-8")
            self.queue.put(GenerationSuccess(result=result, saved=request.auto_save))
        except Exception as exc:
            self.queue.put(GenerationFailure(message=str(exc)))

    def _poll_queue(self) -> None:
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll_queue)
            return

        if self.generate_button is not None:
            self.generate_button.configure(state=NORMAL)

        if isinstance(item, GenerationFailure):
            self._set_status(
                "생성에 실패했습니다.",
                warning=item.message,
            )
            messagebox.showerror("생성 실패", item.message)
        else:
            self._handle_success(item)

        self.root.after(120, self._poll_queue)

    def _handle_success(self, payload: GenerationSuccess) -> None:
        self.current_result = payload.result
        self.current_view_path = payload.result.output_path if payload.saved else None
        self.view_contents = split_markdown_views(payload.result.markdown)
        self.view_var.set("full")
        self._refresh_view()

        used_llm = "LLM 사용" if payload.result.used_llm else "규칙 기반 fallback"
        save_note = f"저장 위치: {payload.result.output_path}" if payload.saved else "미리보기만 생성"
        self._set_status(
            f"{payload.result.target_date.isoformat()} 결과를 앱 안에서 열었습니다.",
            meta=(
                f"모드: {payload.result.mode} / "
                f"10분 요약 {payload.result.stats.get('used_10min', 0)}개 / "
                f"6시간 요약 {payload.result.stats.get('used_6h', 0)}개 / "
                f"{used_llm} / {save_note}"
            ),
            warning=" | ".join(payload.result.warnings),
        )

        if self.copy_button is not None:
            self.copy_button.configure(state=NORMAL)
        if self.open_button is not None:
            self.open_button.configure(state=NORMAL)
        if self.external_open_button is not None:
            self.external_open_button.configure(state=NORMAL if payload.saved else DISABLED)

        if payload.saved:
            self._refresh_saved_lists()

    def _current_view_key(self) -> str:
        return self.view_var.get() or "full"

    def _copy_current_view(self) -> None:
        key = self._current_view_key()
        content = self.view_contents.get(key, "")
        if not content:
            messagebox.showinfo("복사할 내용 없음", "먼저 일기를 생성하거나 열어 주세요.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._set_status("현재 보기를 클립보드에 복사했습니다.", meta=f"보기: {key}")

    def _open_output_file(self) -> None:
        if self.current_result and self.current_result.output_path.exists():
            self._open_path_in_app(self.current_result.output_path)
            return
        self._open_selected_date_in_app()

    def _open_output_file_external(self) -> None:
        if not self.current_view_path or not self.current_view_path.exists():
            messagebox.showinfo("열 수 없음", "외부 앱으로 열 수 있는 저장 파일이 없습니다.")
            return
        try:
            open_path(self.current_view_path)
        except RuntimeError as exc:
            messagebox.showerror("파일 열기 실패", str(exc))

    def _open_path_in_app(self, path: Path) -> None:
        if not path.exists():
            messagebox.showinfo("결과 없음", f"파일을 찾지 못했습니다: {path}")
            return
        markdown = path.read_text(encoding="utf-8")
        self.current_view_path = path
        self.view_contents = split_markdown_views(markdown)
        self.view_var.set("full")
        self._refresh_view()
        self._set_status(
            f"{path.name} 내용을 앱 안에서 열었습니다.",
            meta=f"파일: {path}",
        )
        if self.open_button is not None:
            self.open_button.configure(state=NORMAL)
        if self.external_open_button is not None:
            self.external_open_button.configure(state=NORMAL)
        if self.copy_button is not None:
            self.copy_button.configure(state=NORMAL)

    def _open_date_in_app(self, target: date) -> None:
        self.target_date = target
        self._update_controls()
        self._open_selected_date_in_app()

    def _open_selected_date_in_app(self) -> None:
        path = self.out_dir / f"{self.target_date.isoformat()}.md"
        if not path.exists():
            messagebox.showinfo("결과 없음", f"{self.target_date.isoformat()} 날짜의 저장된 일기를 찾지 못했습니다.")
            return
        self._open_path_in_app(path)

    def _open_week_start_in_app(self, week_start: date) -> None:
        self.target_date = week_start
        self._update_controls()
        self._open_selected_week_in_app()

    def _open_selected_week_in_app(self) -> None:
        diary_files = list_daily_diary_files(self.out_dir)
        weekly_markdown = build_weekly_overview(self.target_date, diary_files)
        start, end = week_bounds(self.target_date)
        self.current_view_path = None
        self.view_contents = split_markdown_views(weekly_markdown)
        self.view_var.set("full")
        self._refresh_view()
        self._set_status(
            f"{format_week_label(start, end)} 주간 보기를 앱 안에서 열었습니다.",
            meta=f"출력 폴더: {self.out_dir}",
        )
        if self.external_open_button is not None:
            self.external_open_button.configure(state=DISABLED)
        if self.copy_button is not None:
            self.copy_button.configure(state=NORMAL)


def main() -> None:
    root = Tk()
    DiaryDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
