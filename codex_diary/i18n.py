from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageOption:
    code: str
    label: str
    locale: str


LANGUAGE_OPTIONS = {
    "en": LanguageOption("en", "English", "en-US"),
    "ko": LanguageOption("ko", "Korean", "ko-KR"),
    "ja": LanguageOption("ja", "Japanese", "ja-JP"),
    "zh": LanguageOption("zh", "Chinese", "zh-CN"),
    "fr": LanguageOption("fr", "French", "fr-FR"),
    "de": LanguageOption("de", "German", "de-DE"),
    "es": LanguageOption("es", "Spanish", "es-ES"),
    "vi": LanguageOption("vi", "Vietnamese", "vi-VN"),
    "th": LanguageOption("th", "Thai", "th-TH"),
    "ru": LanguageOption("ru", "Russian", "ru-RU"),
    "hi": LanguageOption("hi", "Hindi", "hi-IN"),
}

DEFAULT_LANGUAGE_CODE = "en"

LANGUAGE_ALIASES = {
    "english": "en",
    "korean": "ko",
    "korean (한국어)": "ko",
    "한국어": "ko",
    "japanese": "ja",
    "japanese (日本語)": "ja",
    "日本語": "ja",
    "chinese": "zh",
    "chinese (中文)": "zh",
    "中文": "zh",
    "french": "fr",
    "french (français)": "fr",
    "français": "fr",
    "german": "de",
    "german (deutsch)": "de",
    "deutsch": "de",
    "spanish": "es",
    "spanish (español)": "es",
    "español": "es",
    "vietnamese": "vi",
    "vietnamese (tiếng việt)": "vi",
    "tiếng việt": "vi",
    "thai": "th",
    "thai (ไทย)": "th",
    "ไทย": "th",
    "russian": "ru",
    "russian (русский)": "ru",
    "русский": "ru",
    "hindi": "hi",
    "hindi (हिन्दी)": "hi",
    "हिन्दी": "hi",
    "en-us": "en",
    "ko-kr": "ko",
    "ja-jp": "ja",
    "zh-cn": "zh",
    "fr-fr": "fr",
    "de-de": "de",
    "es-es": "es",
    "vi-vn": "vi",
    "th-th": "th",
    "ru-ru": "ru",
    "hi-in": "hi",
}


SECTION_HEADINGS = {
    "en": {
        "report": "## Work Report",
        "diary": "## Diary Version",
        "today": "What I Did Today",
        "timeline": "Timeline Notes, Including Small Steps",
        "decisions": "Key Decisions and Confirmations",
        "blockers": "Blockers or Open Issues",
        "tomorrow": "Tasks for Tomorrow",
        "reflection": "Short Reflection",
    },
    "ko": {
        "report": "## 금일 작업 보고서",
        "diary": "## 오늘의 일기 버전",
        "today": "오늘 한 일",
        "timeline": "사소한 흐름까지 포함한 시간순 메모",
        "decisions": "중요하게 확인하거나 결정한 것",
        "blockers": "막혔던 점 또는 미해결 이슈",
        "tomorrow": "내일 할 일",
        "reflection": "짧은 회고",
    },
    "ja": {
        "report": "## 今日の作業レポート",
        "diary": "## 今日の日記バージョン",
        "today": "今日やったこと",
        "timeline": "細かな流れも含めた時系列メモ",
        "decisions": "重要な確認事項・決定事項",
        "blockers": "詰まった点・未解決の課題",
        "tomorrow": "明日やること",
        "reflection": "短い振り返り",
    },
    "zh": {
        "report": "## 今日工作报告",
        "diary": "## 今日日记版",
        "today": "今天做了什么",
        "timeline": "包含细节流程的时间顺序备忘",
        "decisions": "重点确认或决定的事项",
        "blockers": "卡住的点或未解决的问题",
        "tomorrow": "明天要做的事",
        "reflection": "简短回顾",
    },
    "fr": {
        "report": "## Rapport de travail du jour",
        "diary": "## Version journal du jour",
        "today": "Ce que j'ai fait aujourd'hui",
        "timeline": "Notes chronologiques, y compris les petits mouvements",
        "decisions": "Points importants verifies ou decides",
        "blockers": "Blocages ou points encore ouverts",
        "tomorrow": "Ce qu'il faut faire demain",
        "reflection": "Courte retrospective",
    },
    "de": {
        "report": "## Arbeitsbericht des Tages",
        "diary": "## Tagebuchversion von heute",
        "today": "Was ich heute gemacht habe",
        "timeline": "Zeitliche Notizen, auch zu kleinen Schritten",
        "decisions": "Wichtige Bestatigungen oder Entscheidungen",
        "blockers": "Blocker oder offene Punkte",
        "tomorrow": "Aufgaben fur morgen",
        "reflection": "Kurze Reflexion",
    },
    "es": {
        "report": "## Informe de trabajo del dia",
        "diary": "## Version de diario de hoy",
        "today": "Lo que hice hoy",
        "timeline": "Notas cronologicas, incluidos los pasos pequenos",
        "decisions": "Confirmaciones o decisiones importantes",
        "blockers": "Bloqueos o temas abiertos",
        "tomorrow": "Tareas para manana",
        "reflection": "Reflexion breve",
    },
    "vi": {
        "report": "## Bao cao cong viec hom nay",
        "diary": "## Phien ban nhat ky hom nay",
        "today": "Hom nay da lam gi",
        "timeline": "Ghi chu theo trinh tu thoi gian, ke ca cac buoc nho",
        "decisions": "Nhung dieu quan trong da xac nhan hoac quyet dinh",
        "blockers": "Diem bi nghen hoac van de chua xong",
        "tomorrow": "Viec can lam ngay mai",
        "reflection": "Nhin lai ngan",
    },
    "th": {
        "report": "## รายงานงานของวันนี้",
        "diary": "## เวอร์ชันไดอารีของวันนี้",
        "today": "วันนี้ทำอะไรบ้าง",
        "timeline": "บันทึกตามลำดับเวลา รวมถึงจังหวะเล็กๆ",
        "decisions": "สิ่งสำคัญที่ยืนยันหรือได้ตัดสินใจ",
        "blockers": "จุดที่ติดหรือประเด็นที่ยังค้าง",
        "tomorrow": "สิ่งที่จะทำพรุ่งนี้",
        "reflection": "ทบทวนสั้นๆ",
    },
    "ru": {
        "report": "## Рабочий отчет за сегодня",
        "diary": "## Дневниковая версия за сегодня",
        "today": "Что я сделал сегодня",
        "timeline": "Хронологические заметки, включая мелкие шаги",
        "decisions": "Важные подтверждения и решения",
        "blockers": "Блокеры или открытые вопросы",
        "tomorrow": "Что сделать завтра",
        "reflection": "Короткая рефлексия",
    },
    "hi": {
        "report": "## आज की कार्य रिपोर्ट",
        "diary": "## आज की डायरी संस्करण",
        "today": "आज क्या किया",
        "timeline": "छोटे कदमों सहित समयानुक्रम नोट्स",
        "decisions": "महत्वपूर्ण पुष्टि या फैसले",
        "blockers": "अटके हुए बिंदु या खुले मुद्दे",
        "tomorrow": "कल के काम",
        "reflection": "छोटी समीक्षा",
    },
}


def supported_language_codes() -> tuple[str, ...]:
    return tuple(LANGUAGE_OPTIONS.keys())


def normalize_language_code(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in LANGUAGE_OPTIONS:
        return raw
    return LANGUAGE_ALIASES.get(raw)


def get_language_option(value: str | None) -> LanguageOption:
    code = normalize_language_code(value) or DEFAULT_LANGUAGE_CODE
    return LANGUAGE_OPTIONS.get(code, LANGUAGE_OPTIONS[DEFAULT_LANGUAGE_CODE])


def heading_labels(value: str | None) -> dict[str, str]:
    option = get_language_option(value)
    return SECTION_HEADINGS[option.code]


def all_report_headings() -> tuple[str, ...]:
    return tuple(labels["report"] for labels in SECTION_HEADINGS.values())


def all_diary_headings() -> tuple[str, ...]:
    return tuple(labels["diary"] for labels in SECTION_HEADINGS.values())


def all_section_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for labels in SECTION_HEADINGS.values():
        aliases[labels["today"]] = "today"
        aliases[labels["timeline"]] = "timeline"
        aliases[labels["decisions"]] = "decisions"
        aliases[labels["blockers"]] = "blockers"
        aliases[labels["tomorrow"]] = "tomorrow"
        aliases[labels["reflection"]] = "reflection"
    return aliases
