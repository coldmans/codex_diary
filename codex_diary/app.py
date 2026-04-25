from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .chronicle import SOURCE_PATTERN, resolve_target_date
from .diary_length import (
    DEFAULT_DIARY_LENGTH_CODE,
    get_diary_length_option,
    normalize_diary_length,
    supported_diary_length_codes,
)
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
from .llm import (
    GenerationCancelledError,
    SUPPORTED_CODEX_MODELS,
    codex_login_command_args,
    default_codex_model,
    get_codex_status,
    normalize_codex_model,
)
from .markdown_html import render_markdown

DEFAULT_SOURCE_DIR = "~/.codex/memories_extensions/chronicle/resources"
APP_NAME = "Codex Diary"
WINDOW_TITLE = "Codex Diary"
WINDOW_SIZE = (1280, 860)
WINDOW_MIN = (1040, 720)
PROGRESS_PHASE_KEYS = {
    "collect": ("loading.step.collect", "loading.detail.collect"),
    "organize": ("loading.step.organize", "loading.detail.organize"),
    "write": ("loading.step.write", "loading.detail.write"),
    "finish": ("loading.step.finish", "loading.detail.finish"),
}
_NOTIFICATION_DELEGATE_CLASS = None

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

SYSTEM_NOTIFICATION_COPY = {
    "en": {
        "ready_title": "Diary Ready",
        "ready_message": "{date} entry is ready in Codex Diary.",
        "failed_title": "Generation Failed",
        "failed_message": "The {date} entry could not be finished. Open Codex Diary to check the error.",
    },
    "ko": {
        "ready_title": "일기 생성 완료",
        "ready_message": "{date} 기록이 준비됐어요. Codex Diary에서 바로 열 수 있어요.",
        "failed_title": "일기 생성 실패",
        "failed_message": "{date} 기록 생성이 끝나지 않았어요. Codex Diary를 열어 오류를 확인해 주세요.",
    },
    "ja": {
        "ready_title": "日記の作成完了",
        "ready_message": "{date} の記録ができました。Codex Diary ですぐ開けます。",
        "failed_title": "日記の作成に失敗しました",
        "failed_message": "{date} の記録を最後まで作れませんでした。Codex Diary を開いてエラーを確認してください。",
    },
    "zh": {
        "ready_title": "日记已生成",
        "ready_message": "{date} 的记录已经准备好了，可以在 Codex Diary 中直接打开。",
        "failed_title": "日记生成失败",
        "failed_message": "{date} 的记录没有顺利生成完成，请打开 Codex Diary 查看错误。",
    },
    "fr": {
        "ready_title": "Journal pret",
        "ready_message": "L'entree du {date} est prete dans Codex Diary.",
        "failed_title": "Echec de generation",
        "failed_message": "L'entree du {date} n'a pas pu etre terminee. Ouvrez Codex Diary pour verifier l'erreur.",
    },
    "de": {
        "ready_title": "Tagebuch fertig",
        "ready_message": "Der Eintrag fur {date} ist in Codex Diary bereit.",
        "failed_title": "Erstellung fehlgeschlagen",
        "failed_message": "Der Eintrag fur {date} konnte nicht abgeschlossen werden. Offne Codex Diary und prufe den Fehler.",
    },
    "es": {
        "ready_title": "Diario listo",
        "ready_message": "La entrada del {date} ya esta lista en Codex Diary.",
        "failed_title": "Fallo en la generacion",
        "failed_message": "La entrada del {date} no pudo completarse. Abre Codex Diary para revisar el error.",
    },
    "vi": {
        "ready_title": "Nhat ky da xong",
        "ready_message": "Ban ghi ngay {date} da san sang trong Codex Diary.",
        "failed_title": "Tao nhat ky that bai",
        "failed_message": "Khong the hoan tat ban ghi ngay {date}. Hay mo Codex Diary de xem loi.",
    },
    "th": {
        "ready_title": "ไดอารีพร้อมแล้ว",
        "ready_message": "บันทึกของวันที่ {date} พร้อมเปิดใน Codex Diary แล้ว",
        "failed_title": "สร้างไดอารีไม่สำเร็จ",
        "failed_message": "ไม่สามารถสร้างบันทึกของวันที่ {date} ให้เสร็จได้ โปรดเปิด Codex Diary เพื่อตรวจสอบข้อผิดพลาด",
    },
    "ru": {
        "ready_title": "Дневник готов",
        "ready_message": "Запись за {date} готова в Codex Diary.",
        "failed_title": "Не удалось создать запись",
        "failed_message": "Не удалось завершить запись за {date}. Откройте Codex Diary и проверьте ошибку.",
    },
    "hi": {
        "ready_title": "डायरी तैयार है",
        "ready_message": "{date} की एंट्री Codex Diary में तैयार है।",
        "failed_title": "डायरी बन नहीं पाई",
        "failed_message": "{date} की एंट्री पूरी नहीं हो सकी। त्रुटि देखने के लिए Codex Diary खोलें।",
    },
}

BRIDGE_COPY = {
    "en": {
        "codex_terminal": "First check whether the `codex` command is available in Terminal.",
        "codex_connected_detail": "Your login looks good.",
        "codex_login_detail": "Login is required.",
        "ready_status": "Choose a date and press `Create` to open the diary right inside the app.",
        "macos_only": "Connecting Codex can only be started directly on macOS.",
        "cancel_none": "There is no generation in progress.",
        "cancelling": "Cancelling the current generation.",
        "already_connected": "Codex is already connected.",
        "terminal_opened": "Opened a Codex login window in Terminal. After you finish, check the status again.",
        "connect_required": "Connect Codex first.",
        "generation_in_progress": "A generation is already in progress.",
        "missing_saved_diary": "Could not find a saved diary for {date}.",
    },
    "ko": {
        "codex_terminal": "터미널에서 `codex` 명령이 보이는지 먼저 확인해 주세요.",
        "codex_connected_detail": "로그인 상태가 정상이에요.",
        "codex_login_detail": "로그인이 필요해요.",
        "ready_status": "날짜를 고르고 `생성`을 누르면 앱 안에서 바로 일기를 볼 수 있습니다.",
        "macos_only": "Codex 연결은 macOS에서만 바로 시작할 수 있어요.",
        "cancel_none": "진행 중인 생성 작업이 없어요.",
        "cancelling": "생성을 취소하는 중이에요.",
        "already_connected": "이미 Codex에 연결되어 있어요.",
        "terminal_opened": "Terminal에서 Codex 로그인 창을 열었어요. 완료한 뒤 상태를 다시 확인해 주세요.",
        "connect_required": "먼저 codex를 연결해주세요.",
        "generation_in_progress": "이미 생성이 진행 중입니다.",
        "missing_saved_diary": "{date} 날짜의 저장된 일기를 찾지 못했습니다.",
    },
    "ja": {
        "codex_terminal": "まず Terminal で `codex` コマンドが使えるか確認してください。",
        "codex_connected_detail": "ログイン状態は正常です。",
        "codex_login_detail": "ログインが必要です。",
        "ready_status": "日付を選んで `Create` を押すと、アプリ内ですぐに日記を開けます。",
        "macos_only": "Codex への接続は macOS でのみ直接開始できます。",
        "cancel_none": "進行中の生成はありません。",
        "cancelling": "生成をキャンセルしています。",
        "already_connected": "Codex はすでに接続されています。",
        "terminal_opened": "Terminal で Codex ログイン画面を開きました。完了したら状態をもう一度確認してください。",
        "connect_required": "先に Codex を接続してください。",
        "generation_in_progress": "すでに生成が進行中です。",
        "missing_saved_diary": "{date} の保存済み日記が見つかりませんでした。",
    },
    "zh": {
        "codex_terminal": "请先确认 Terminal 里可以使用 `codex` 命令。",
        "codex_connected_detail": "登录状态正常。",
        "codex_login_detail": "需要先登录。",
        "ready_status": "选择日期并按下 `Create` 后，就能在应用里直接打开日记。",
        "macos_only": "只有在 macOS 上才能直接发起 Codex 连接。",
        "cancel_none": "当前没有正在进行的生成任务。",
        "cancelling": "正在取消当前生成。",
        "already_connected": "Codex 已经连接好了。",
        "terminal_opened": "已经在 Terminal 中打开 Codex 登录窗口。完成后请再次检查状态。",
        "connect_required": "请先连接 Codex。",
        "generation_in_progress": "已经有一个生成任务在进行中。",
        "missing_saved_diary": "找不到 {date} 的已保存日记。",
    },
    "fr": {
        "codex_terminal": "Verifiez d'abord dans Terminal que la commande `codex` est disponible.",
        "codex_connected_detail": "Votre connexion est en ordre.",
        "codex_login_detail": "Une connexion est necessaire.",
        "ready_status": "Choisissez une date puis appuyez sur `Create` pour ouvrir le journal directement dans l'app.",
        "macos_only": "La connexion a Codex ne peut etre lancee directement que sur macOS.",
        "cancel_none": "Aucune generation n'est en cours.",
        "cancelling": "Annulation de la generation en cours.",
        "already_connected": "Codex est deja connecte.",
        "terminal_opened": "Une fenetre de connexion Codex a ete ouverte dans Terminal. Une fois termine, reverifiez l'etat.",
        "connect_required": "Connectez d'abord Codex.",
        "generation_in_progress": "Une generation est deja en cours.",
        "missing_saved_diary": "Impossible de trouver un journal enregistre pour le {date}.",
    },
    "de": {
        "codex_terminal": "Pruefe zuerst im Terminal, ob der Befehl `codex` verfuegbar ist.",
        "codex_connected_detail": "Dein Login sieht gut aus.",
        "codex_login_detail": "Eine Anmeldung ist erforderlich.",
        "ready_status": "Waehle ein Datum und druecke `Create`, um das Tagebuch direkt in der App zu oeffnen.",
        "macos_only": "Die Codex-Verbindung kann nur unter macOS direkt gestartet werden.",
        "cancel_none": "Es laeuft gerade keine Generierung.",
        "cancelling": "Die aktuelle Generierung wird abgebrochen.",
        "already_connected": "Codex ist bereits verbunden.",
        "terminal_opened": "Ein Codex-Loginfenster wurde im Terminal geoeffnet. Pruefe den Status erneut, sobald du fertig bist.",
        "connect_required": "Verbinde zuerst Codex.",
        "generation_in_progress": "Es laeuft bereits eine Generierung.",
        "missing_saved_diary": "Fuer {date} wurde kein gespeichertes Tagebuch gefunden.",
    },
    "es": {
        "codex_terminal": "Primero revisa en Terminal si el comando `codex` esta disponible.",
        "codex_connected_detail": "Tu sesion esta correcta.",
        "codex_login_detail": "Hace falta iniciar sesion.",
        "ready_status": "Elige una fecha y pulsa `Create` para abrir el diario directamente dentro de la app.",
        "macos_only": "La conexion a Codex solo puede iniciarse directamente en macOS.",
        "cancel_none": "No hay ninguna generacion en curso.",
        "cancelling": "Cancelando la generacion actual.",
        "already_connected": "Codex ya esta conectado.",
        "terminal_opened": "Se abrio una ventana de acceso de Codex en Terminal. Cuando termines, vuelve a comprobar el estado.",
        "connect_required": "Conecta primero Codex.",
        "generation_in_progress": "Ya hay una generacion en curso.",
        "missing_saved_diary": "No se encontro un diario guardado para {date}.",
    },
    "vi": {
        "codex_terminal": "Truoc tien hay kiem tra trong Terminal xem co lenh `codex` hay khong.",
        "codex_connected_detail": "Trang thai dang nhap dang tot.",
        "codex_login_detail": "Can dang nhap truoc.",
        "ready_status": "Chon ngay roi bam `Create` de mo nhat ky ngay trong ung dung.",
        "macos_only": "Chi tren macOS moi co the bat dau ket noi Codex truc tiep.",
        "cancel_none": "Khong co lan tao nao dang chay.",
        "cancelling": "Dang huy lan tao hien tai.",
        "already_connected": "Codex da duoc ket noi roi.",
        "terminal_opened": "Da mo cua so dang nhap Codex trong Terminal. Hoan tat xong thi hay kiem tra lai trang thai.",
        "connect_required": "Hay ket noi Codex truoc.",
        "generation_in_progress": "Da co mot lan tao dang dien ra.",
        "missing_saved_diary": "Khong tim thay nhat ky da luu cho ngay {date}.",
    },
    "th": {
        "codex_terminal": "กรุณาตรวจดูก่อนว่าใน Terminal ใช้คำสั่ง `codex` ได้หรือไม่",
        "codex_connected_detail": "สถานะการล็อกอินปกติดี",
        "codex_login_detail": "จำเป็นต้องล็อกอินก่อน",
        "ready_status": "เลือกวันที่แล้วกด `Create` เพื่อเปิดไดอารีได้ตรงในแอปทันที",
        "macos_only": "การเชื่อมต่อ Codex แบบเริ่มตรงๆ ทำได้เฉพาะบน macOS",
        "cancel_none": "ตอนนี้ไม่มีงานสร้างที่กำลังทำอยู่",
        "cancelling": "กำลังยกเลิกการสร้างปัจจุบัน",
        "already_connected": "Codex เชื่อมต่ออยู่แล้ว",
        "terminal_opened": "ได้เปิดหน้าต่างล็อกอิน Codex ใน Terminal แล้ว หลังทำเสร็จกรุณาตรวจสอบสถานะอีกครั้ง",
        "connect_required": "กรุณาเชื่อมต่อ Codex ก่อน",
        "generation_in_progress": "มีงานสร้างกำลังทำอยู่แล้ว",
        "missing_saved_diary": "ไม่พบไดอารีที่บันทึกไว้สำหรับ {date}",
    },
    "ru": {
        "codex_terminal": "Сначала проверьте в Terminal, доступна ли команда `codex`.",
        "codex_connected_detail": "С входом все в порядке.",
        "codex_login_detail": "Нужно войти в систему.",
        "ready_status": "Выберите дату и нажмите `Create`, чтобы открыть дневник прямо в приложении.",
        "macos_only": "Подключение Codex можно запустить напрямую только на macOS.",
        "cancel_none": "Сейчас нет активной генерации.",
        "cancelling": "Отменяю текущую генерацию.",
        "already_connected": "Codex уже подключен.",
        "terminal_opened": "Окно входа Codex открыто в Terminal. После завершения снова проверьте статус.",
        "connect_required": "Сначала подключите Codex.",
        "generation_in_progress": "Генерация уже выполняется.",
        "missing_saved_diary": "Не удалось найти сохраненный дневник за {date}.",
    },
    "hi": {
        "codex_terminal": "पहले Terminal में देख लें कि `codex` कमांड उपलब्ध है या नहीं।",
        "codex_connected_detail": "आपका लॉगिन ठीक है।",
        "codex_login_detail": "पहले लॉग इन करना जरूरी है।",
        "ready_status": "तारीख चुनकर `Create` दबाएं, फिर डायरी सीधे ऐप के अंदर खुल जाएगी।",
        "macos_only": "Codex कनेक्शन सीधे सिर्फ macOS पर शुरू किया जा सकता है।",
        "cancel_none": "अभी कोई जनरेशन चल नहीं रही है।",
        "cancelling": "मौजूदा जनरेशन रद्द की जा रही है।",
        "already_connected": "Codex पहले से कनेक्ट है।",
        "terminal_opened": "Terminal में Codex लॉगिन विंडो खोल दी गई है। पूरा करने के बाद स्टेटस फिर से जांचिए।",
        "connect_required": "पहले Codex कनेक्ट करें।",
        "generation_in_progress": "एक जनरेशन पहले से चल रही है।",
        "missing_saved_diary": "{date} के लिए सेव की गई डायरी नहीं मिली।",
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


def bridge_copy(output_language_code: str | None) -> dict[str, str]:
    code = normalize_language_code(output_language_code) or DEFAULT_LANGUAGE_CODE
    return BRIDGE_COPY.get(code, BRIDGE_COPY[DEFAULT_LANGUAGE_CODE])


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


def system_notification_copy(output_language_code: str | None) -> dict[str, str]:
    code = normalize_language_code(output_language_code) or DEFAULT_LANGUAGE_CODE
    return SYSTEM_NOTIFICATION_COPY.get(code, SYSTEM_NOTIFICATION_COPY[DEFAULT_LANGUAGE_CODE])


def native_notification_delegate_class(NSObject, NSApplication):
    global _NOTIFICATION_DELEGATE_CLASS
    if _NOTIFICATION_DELEGATE_CLASS is not None:
        return _NOTIFICATION_DELEGATE_CLASS

    class CodexDiaryNotificationDelegate(NSObject):  # type: ignore[misc, valid-type]
        def userNotificationCenter_shouldPresentNotification_(self, center, notification):  # noqa: N802
            return True

        def userNotificationCenter_didActivateNotification_(self, center, notification):  # noqa: N802
            try:
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            finally:
                try:
                    center.removeDeliveredNotification_(notification)
                except Exception:
                    pass

    _NOTIFICATION_DELEGATE_CLASS = CodexDiaryNotificationDelegate
    return _NOTIFICATION_DELEGATE_CLASS


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
        summary, tags = weekly_entry_snapshot(content, copy["no_content"])
        lines.append(f"### {entry_date.isoformat()}")
        lines.append("")
        lines.append(summary)
        if tags:
            lines.extend(["", " ".join(f"#{tag}" for tag in tags[:4])])
        if index != len(week_items) - 1:
            lines.extend(["", "---", ""])
    lines.append("")
    return "\n".join(lines)


FIRST_SENTENCE_RE = re.compile(r"[^。.!?\n]+[。.!?]?")


def first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    match = FIRST_SENTENCE_RE.match(cleaned)
    return (match.group(0) if match else cleaned).strip()


def fallback_weekly_summary(markdown: str, no_content: str) -> str:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines:
        return no_content
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip() or no_content
    for line in lines:
        if line.startswith(("## ", "### ", "#### ", "<!--")):
            continue
        if line.startswith("> "):
            return first_sentence(line[2:].strip()) or no_content
        return first_sentence(line) or no_content
    return no_content


def weekly_entry_snapshot(markdown: str, no_content: str) -> tuple[str, list[str]]:
    structured = structure_diary(markdown)
    candidates = [
        structured["report"]["today"],
        structured["report"]["reflection"],
        *(structured["diary"][:1] if structured["diary"] else []),
        structured["intro_quote"],
    ]
    for candidate in candidates:
        summary = first_sentence(candidate)
        if summary:
            return summary, structured.get("tags") or []
    return fallback_weekly_summary(markdown, no_content), structured.get("tags") or []


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


def build_readiness(source_dir: Path, out_dir: Path) -> dict[str, Any]:
    source = source_dir.expanduser()
    output = out_dir.expanduser()
    source_count = 0
    source_exists = source.exists() and source.is_dir()
    if source_exists:
        try:
            source_count = sum(
                1
                for path in source.glob("*.md")
                if path.is_file() and not path.is_symlink() and SOURCE_PATTERN.match(path.name)
            )
        except OSError:
            source_count = 0
    return {
        "source_dir": str(source),
        "source_exists": source_exists,
        "source_markdown_count": source_count,
        "out_dir": str(output),
        "out_exists": output.exists() and output.is_dir(),
    }


@dataclass
class AppConfig:
    target_date: date
    boundary_hour: int
    source_dir: Path
    out_dir: Path
    output_language_code: str
    diary_length_code: str
    codex_model: str

    def to_json(self) -> dict[str, Any]:
        language = get_language_option(self.output_language_code)
        diary_length = get_diary_length_option(self.diary_length_code)
        return {
            "target_date": self.target_date.isoformat(),
            "boundary_hour": self.boundary_hour,
            "source_dir": str(self.source_dir.expanduser()),
            "out_dir": str(self.out_dir.expanduser()),
            "output_language_code": language.code,
            "output_language": language.label,
            "diary_length_code": diary_length.code,
            "diary_length": diary_length.label,
            "codex_model": self.codex_model,
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
            diary_length_code=DEFAULT_DIARY_LENGTH_CODE,
            codex_model=default_codex_model(),
        )
        self._generation_lock = threading.Lock()
        self._progress_lock = threading.Lock()
        self._cancel_requested = threading.Event()
        self._window = None
        self._notification_delegate = None
        self._progress = self._build_progress_snapshot(
            status="idle",
            phase=None,
            percent=0,
            target_date=self.config.target_date.isoformat(),
            output_language_code=self.config.output_language_code,
            mode="finalize",
            stats={"diary_length": self.config.diary_length_code},
        )

    def attach_window(self, window) -> None:
        self._window = window

    @staticmethod
    def _build_progress_snapshot(
        *,
        status: str,
        phase: str | None,
        percent: int | None = None,
        current: int | None = None,
        total: int | None = None,
        step_key: str | None = None,
        detail_key: str | None = None,
        target_date: str | None = None,
        output_language_code: str | None = None,
        mode: str | None = None,
        stats: dict[str, Any] | None = None,
        indeterminate: bool = False,
        error: str | None = None,
    ) -> dict[str, Any]:
        default_step_key, default_detail_key = PROGRESS_PHASE_KEYS.get(phase or "", (None, None))
        normalized_percent = None if percent is None else max(0, min(100, int(percent)))
        return {
            "status": status,
            "phase": phase,
            "percent": normalized_percent,
            "current": current,
            "total": total,
            "step_key": step_key or default_step_key,
            "detail_key": detail_key or default_detail_key,
            "target_date": target_date,
            "output_language_code": output_language_code,
            "mode": mode,
            "stats": dict(stats or {}),
            "indeterminate": bool(indeterminate),
            "error": error,
        }

    def _current_progress(self) -> dict[str, Any]:
        with self._progress_lock:
            return {
                **self._progress,
                "stats": dict(self._progress.get("stats") or {}),
            }

    def _dispatch_progress(self, snapshot: dict[str, Any]) -> None:
        if self._window is None:
            return
        payload_json = json.dumps(snapshot, ensure_ascii=False)
        script = (
            "(function(){"
            f"const payload={payload_json};"
            "if(window.__codexDiaryOnProgress){window.__codexDiaryOnProgress(payload);}"
            "window.dispatchEvent(new CustomEvent('codex-diary:progress',{detail:payload}));"
            "})();"
        )
        try:
            self._window.evaluate_js(script)
        except Exception:
            return

    def _update_progress(
        self,
        *,
        status: str,
        phase: str | None,
        percent: int | None = None,
        current: int | None = None,
        total: int | None = None,
        step_key: str | None = None,
        detail_key: str | None = None,
        target_date: str | None = None,
        output_language_code: str | None = None,
        mode: str | None = None,
        stats: dict[str, Any] | None = None,
        indeterminate: bool = False,
        error: str | None = None,
    ) -> dict[str, Any]:
        snapshot = self._build_progress_snapshot(
            status=status,
            phase=phase,
            percent=percent,
            current=current,
            total=total,
            step_key=step_key,
            detail_key=detail_key,
            target_date=target_date,
            output_language_code=output_language_code,
            mode=mode,
            stats=stats,
            indeterminate=indeterminate,
            error=error,
        )
        with self._progress_lock:
            self._progress = snapshot
        self._dispatch_progress(snapshot)
        return snapshot

    def _codex_status_details(self) -> dict[str, Any]:
        status = get_codex_status()
        copy = bridge_copy(self.config.output_language_code)
        connectable = status.available and sys.platform == "darwin"
        if not status.available:
            detail = copy["codex_terminal"]
        elif status.connected:
            detail = copy["codex_connected_detail"]
        else:
            detail = copy["codex_login_detail"]
        return {
            "available": status.available,
            "connected": status.connected,
            "connectable": connectable,
            "message": copy["already_connected"] if status.connected else copy["connect_required"],
            "detail": detail,
            "command": status.command,
            "auth_mode": status.auth_mode,
            "configured_model": status.configured_model,
            "selected_model": self.config.codex_model,
        }

    def _launch_codex_device_auth(self) -> None:
        if sys.platform != "darwin":
            raise RuntimeError(bridge_copy(self.config.output_language_code)["macos_only"])
        command = shlex.join(codex_login_command_args(device_auth=True))
        script = (
            'tell application "Terminal"\n'
            "  activate\n"
            f"  do script {json.dumps(command)}\n"
            "end tell"
        )
        subprocess.Popen(["osascript", "-e", script], start_new_session=True)

    def _show_native_system_notification(self, *, title: str, message: str) -> bool:
        if sys.platform != "darwin":
            return False
        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSApplication,
                NSUserNotification,
                NSUserNotificationCenter,
                NSUserNotificationDefaultSoundName,
            )
            from Foundation import NSObject  # type: ignore[import-not-found]
        except Exception:
            return False

        if self._notification_delegate is None:
            delegate_class = native_notification_delegate_class(NSObject, NSApplication)
            self._notification_delegate = delegate_class.alloc().init()

        try:
            center = NSUserNotificationCenter.defaultUserNotificationCenter()
            center.setDelegate_(self._notification_delegate)
            notification = NSUserNotification.alloc().init()
            notification.setTitle_(title)
            notification.setInformativeText_(message)
            notification.setSoundName_(NSUserNotificationDefaultSoundName)
            if hasattr(notification, "setHasActionButton_"):
                notification.setHasActionButton_(False)
            center.deliverNotification_(notification)
            return True
        except Exception:
            return False

    def _show_system_notification(self, *, title: str, message: str) -> None:
        # Avoid AppleScript notifications: clicking those can focus Script Editor
        # or osascript instead of the packaged Codex Diary app.
        self._show_native_system_notification(title=title, message=message)

    def _notify_generation_result(
        self,
        *,
        success: bool,
        target_date: str,
        output_language_code: str | None,
    ) -> None:
        copy = system_notification_copy(output_language_code)
        if success:
            self._show_system_notification(
                title=copy["ready_title"],
                message=copy["ready_message"].format(date=target_date),
            )
            return
        self._show_system_notification(
            title=copy["failed_title"],
            message=copy["failed_message"].format(date=target_date),
        )

    # ---- Read-only helpers ---------------------------------------------
    def get_state(self) -> dict[str, Any]:
        codex = self._codex_status_details()
        copy = bridge_copy(self.config.output_language_code)
        return {
            "config": self.config.to_json(),
            "entries": list_saved_entries(self.config.out_dir),
            "status": codex["message"] if not codex["connected"] else copy["ready_status"],
            "codex": codex,
            "progress": self._current_progress(),
            "readiness": build_readiness(self.config.source_dir, self.config.out_dir),
            "generation_available": codex["connected"],
            "supported_output_languages": [
                {"code": code, "label": get_language_option(code).label}
                for code in supported_language_codes()
            ],
            "supported_diary_lengths": [
                {"code": code, "label": get_diary_length_option(code).label}
                for code in supported_diary_length_codes()
            ],
            "supported_codex_models": [
                {"code": code, "label": code}
                for code in SUPPORTED_CODEX_MODELS
            ],
        }

    def list_entries(self, out_dir: str | None = None) -> dict[str, Any]:
        directory = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        return list_saved_entries(directory)

    def readiness(self, source_dir: str | None = None, out_dir: str | None = None) -> dict[str, Any]:
        source = Path(source_dir).expanduser() if source_dir else self.config.source_dir
        output = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        return build_readiness(source, output)

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
        current_effective_today = resolve_target_date(None, day_boundary_hour=self.config.boundary_hour)
        if iso == current_effective_today.isoformat():
            target = resolve_target_date(None, day_boundary_hour=hour)
        else:
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

    def cancel_generation(self) -> dict[str, Any]:
        copy = bridge_copy(self.config.output_language_code)
        if not self._generation_lock.locked():
            return {
                "cancelled": False,
                "progress": self._current_progress(),
                "message": copy["cancel_none"],
            }
        self._cancel_requested.set()
        current = self._current_progress()
        progress = self._update_progress(
            status="cancelling",
            phase=current.get("phase") or "collect",
            percent=current.get("percent"),
            current=current.get("current"),
            total=current.get("total"),
            step_key=current.get("step_key"),
            detail_key="loading.detail.cancel",
            target_date=self.config.target_date.isoformat(),
            output_language_code=self.config.output_language_code,
            mode=current.get("mode") or "finalize",
            stats=dict(current.get("stats") or {}),
            indeterminate=True,
            error=None,
        )
        return {
            "cancelled": False,
            "progress": progress,
            "message": copy["cancelling"],
        }

    def connect_codex(self) -> dict[str, Any]:
        copy = bridge_copy(self.config.output_language_code)
        status = self._codex_status_details()
        if status["connected"]:
            return {
                "codex": status,
                "connected": True,
                "message": copy["already_connected"],
            }
        if not status["available"]:
            return {
                "codex": status,
                "connected": False,
                "error": status["detail"],
            }
        if not status["connectable"]:
            return {
                "codex": status,
                "connected": False,
                "error": copy["macos_only"],
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
            "message": copy["terminal_opened"],
        }

    # ---- Generation & loading ------------------------------------------
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._coerce_request(payload)
        copy = bridge_copy(request["output_language_code"])
        codex = self._codex_status_details()
        if not codex["connected"]:
            progress = self._update_progress(
                status="failed",
                phase="write",
                percent=0,
                target_date=request["target_date"].isoformat(),
                output_language_code=request["output_language_code"],
                mode=request["mode"],
                error=copy["connect_required"],
            )
            return {
                "error": copy["connect_required"],
                "codex": codex,
                "generation_available": False,
                "progress": progress,
            }
        if not self._generation_lock.acquire(blocking=False):
            return {
                "error": copy["generation_in_progress"],
                "progress": self._current_progress(),
            }
        try:
            self._cancel_requested.clear()
            self.config.target_date = request["target_date"]
            self.config.boundary_hour = request["boundary_hour"]
            self.config.source_dir = request["source_dir"]
            self.config.out_dir = request["out_dir"]
            self.config.output_language_code = request["output_language_code"]
            self.config.diary_length_code = request["diary_length_code"]
            self.config.codex_model = request["codex_model"]
            target_date_iso = request["target_date"].isoformat()

            def report_progress(update: dict[str, Any]) -> dict[str, Any]:
                previous_stats = dict(self._current_progress().get("stats") or {})
                next_stats = {
                    **previous_stats,
                    **dict(update.get("stats") or {}),
                }
                return self._update_progress(
                    status=str(update.get("status") or "running"),
                    phase=update.get("phase"),
                    percent=update.get("percent"),
                    current=update.get("current"),
                    total=update.get("total"),
                    step_key=update.get("step_key"),
                    detail_key=update.get("detail_key"),
                    target_date=target_date_iso,
                    output_language_code=request["output_language_code"],
                    mode=request["mode"],
                    stats=next_stats,
                    indeterminate=bool(update.get("indeterminate", False)),
                    error=update.get("error"),
                )

            report_progress(
                {
                    "status": "running",
                    "phase": "collect",
                    "percent": 4,
                    "stats": {"diary_length": request["diary_length_code"]},
                }
            )

            result = build_diary(
                target_date=request["target_date"],
                mode=request["mode"],
                source_dir=request["source_dir"],
                out_dir=request["out_dir"],
                day_boundary_hour=request["boundary_hour"],
                output_language=request["output_language_code"],
                diary_length=request["diary_length_code"],
                codex_model=request["codex_model"],
                progress=report_progress,
                should_cancel=self._cancel_requested.is_set,
            )
            if self._cancel_requested.is_set():
                raise GenerationCancelledError("생성을 취소했어요.")
            saved_path: Optional[Path] = None
            if request["auto_save"]:
                report_progress(
                    {
                        "status": "running",
                        "phase": "finish",
                        "percent": 96,
                        "stats": {**dict(result.stats), "events_selected": dict(result.stats).get("events_selected")},
                    }
                )
                for legacy_path in legacy_output_paths(request["out_dir"], result.target_date.isoformat()):
                    if legacy_path.exists():
                        legacy_path.unlink()
                result.output_path.parent.mkdir(parents=True, exist_ok=True)
                result.output_path.write_text(result.markdown, encoding="utf-8")
                saved_path = result.output_path

            payload = render_payload(result.markdown, output_language_code=request["output_language_code"])
            saved_mtime = (
                datetime.fromtimestamp(saved_path.stat().st_mtime).isoformat(timespec="seconds")
                if saved_path and saved_path.exists()
                else None
            )
            completed_progress = report_progress(
                {
                    "status": "completed",
                    "phase": "finish",
                    "percent": 100,
                    "stats": dict(result.stats),
                }
            )
            payload.update(
                {
                    "target_date": result.target_date.isoformat(),
                    "mode": result.mode,
                    "used_llm": result.used_llm,
                    "stats": dict(result.stats),
                    "warnings": list(result.warnings),
                    "saved_path": str(saved_path) if saved_path else None,
                    "saved_mtime": saved_mtime,
                    "output_language_code": request["output_language_code"],
                    "output_language": get_language_option(request["output_language_code"]).label,
                    "diary_length_code": request["diary_length_code"],
                    "diary_length": get_diary_length_option(request["diary_length_code"]).label,
                    "codex_model": request["codex_model"],
                    "progress": completed_progress,
                }
            )
            self._notify_generation_result(
                success=True,
                target_date=result.target_date.isoformat(),
                output_language_code=request["output_language_code"],
            )
            return payload
        except GenerationCancelledError as exc:
            current = self._current_progress()
            cancelled_progress = self._update_progress(
                status="cancelled",
                phase=current.get("phase") or "collect",
                percent=current.get("percent"),
                current=current.get("current"),
                total=current.get("total"),
                step_key=current.get("step_key"),
                detail_key="loading.detail.cancelled",
                target_date=request["target_date"].isoformat(),
                output_language_code=request["output_language_code"],
                mode=request["mode"],
                stats=dict(current.get("stats") or {}),
                indeterminate=False,
                error=None,
            )
            return {
                "cancelled": True,
                "message": str(exc),
                "progress": cancelled_progress,
            }
        except Exception as exc:  # noqa: BLE001 — surface all errors to UI
            current = self._current_progress()
            failed_progress = self._update_progress(
                status="failed",
                phase=current.get("phase") or "finish",
                percent=current.get("percent"),
                current=current.get("current"),
                total=current.get("total"),
                step_key=current.get("step_key"),
                detail_key=current.get("detail_key"),
                target_date=request["target_date"].isoformat(),
                output_language_code=request["output_language_code"],
                mode=request["mode"],
                stats=dict(current.get("stats") or {}),
                indeterminate=False,
                error=str(exc),
            )
            if current.get("phase") in {"write", "finish"}:
                self._notify_generation_result(
                    success=False,
                    target_date=request["target_date"].isoformat(),
                    output_language_code=request["output_language_code"],
                )
            return {"error": str(exc), "progress": failed_progress}
        finally:
            self._cancel_requested.clear()
            self._generation_lock.release()

    def load_date(self, iso: str, out_dir: str | None = None) -> dict[str, Any]:
        directory = Path(out_dir).expanduser() if out_dir else self.config.out_dir
        path = directory / f"{iso}.md"
        if not path.exists():
            return {"error": bridge_copy(self.config.output_language_code)["missing_saved_diary"].format(date=iso)}
        markdown = path.read_text(encoding="utf-8")
        payload = render_payload(markdown)
        payload.update(
            {
                "target_date": iso,
                "saved_path": str(path),
                "saved_mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
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
        diary_length_code = None
        for key in (
            "diary_length_code",
            "diary_length",
            "length",
            "entry_length",
        ):
            diary_length_code = normalize_diary_length(payload.get(key))
            if diary_length_code:
                break
        codex_model = None
        for key in (
            "codex_model",
            "model",
            "llm_model",
        ):
            try:
                codex_model = normalize_codex_model(payload.get(key))
            except Exception:
                codex_model = None
            if codex_model:
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
            "diary_length_code": diary_length_code or DEFAULT_DIARY_LENGTH_CODE,
            "codex_model": codex_model or default_codex_model(),
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
