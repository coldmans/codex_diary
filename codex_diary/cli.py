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
from .llm import CODEX_MISSING_MESSAGE, CODEX_NOT_CONNECTED_MESSAGE, LLMError, normalize_codex_model
from .i18n import (
    DEFAULT_LANGUAGE_CODE,
    normalize_language_code,
    supported_language_codes,
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


CLI_COPY = {
    "en": {
        "description": "Create a work diary draft from Chronicle Markdown summaries.",
        "help": "Show this help message and exit.",
        "date_help": "Create a diary for a specific date. Format: YYYY-MM-DD",
        "source_dir_help": "Path to the Chronicle Markdown summary folder.",
        "out_dir_help": "Folder where the output Markdown will be saved.",
        "dry_run_help": "Print the result to stdout without saving a file.",
        "day_boundary_help": "Local workday boundary hour (default: 4). Must be an integer from 0 to 23.",
        "language_help": "Choose the output language. Supported codes: {codes}. Default: {default}.",
        "length_help": "Choose the diary length. Supported values: {codes}. Default: {default}.",
        "codex_model_help": "Choose the Codex model for generation, for example gpt-5.5.",
        "error_day_boundary": "--day-boundary-hour must be an integer between 0 and 23.",
        "error_invalid_language": "--language must be a supported language code or name. Supported codes: {codes}",
        "error_invalid_length": "--length must be one of the supported length codes. Supported values: {codes}",
        "error_invalid_codex_model": "--codex-model must be a valid Codex model name.",
        "error_invalid_date": "--date must be in YYYY-MM-DD format.",
        "error_missing_sources": "Could not find Chronicle summary files for {date}. Check the input folder or use --source-dir.",
        "error_connect_required": "Connect Codex first.",
        "error_codex_missing": "Connect Codex first. The Codex CLI could not be found.",
        "error_cancelled": "Generation was cancelled.",
        "success": "Created work diary: {path}",
        "warn_prefix": "[warn]",
    },
    "ko": {
        "description": "Chronicle Markdown 요약으로 작업 일기 초안을 생성합니다.",
        "help": "도움말을 표시하고 종료합니다.",
        "date_help": "특정 날짜의 일기를 생성합니다. 형식: YYYY-MM-DD",
        "source_dir_help": "Chronicle Markdown 요약 폴더 경로를 지정합니다.",
        "out_dir_help": "결과 Markdown을 저장할 폴더입니다.",
        "dry_run_help": "파일을 저장하지 않고 결과를 stdout으로 출력합니다.",
        "day_boundary_help": "하루 경계 시각(로컬 타임존 기준, 기본값: 4). 0~23 사이 정수여야 합니다.",
        "language_help": "출력 언어를 지정합니다. 지원 코드: {codes}. 기본값은 {default}입니다.",
        "length_help": "일기 길이를 지정합니다. 지원 값: {codes}. 기본값은 {default}입니다.",
        "codex_model_help": "생성에 사용할 Codex 모델을 지정합니다. 예: gpt-5.5",
        "error_day_boundary": "--day-boundary-hour는 0 이상 23 이하의 정수여야 합니다.",
        "error_invalid_language": "--language는 지원되는 언어 코드 또는 이름이어야 합니다. 지원 코드: {codes}",
        "error_invalid_length": "--length는 지원되는 길이 코드여야 합니다. 지원 값: {codes}",
        "error_invalid_codex_model": "--codex-model은 올바른 Codex 모델 이름이어야 합니다.",
        "error_invalid_date": "--date는 YYYY-MM-DD 형식이어야 합니다.",
        "error_missing_sources": "{date} 기준 Chronicle 요약 파일을 찾지 못했습니다. 입력 폴더를 확인하거나 --source-dir 옵션을 사용해 주세요.",
        "error_connect_required": "먼저 Codex를 연결해 주세요.",
        "error_codex_missing": "먼저 Codex를 연결해 주세요. Codex CLI를 찾지 못했습니다.",
        "error_cancelled": "생성이 취소되었습니다.",
        "success": "작업 일기를 생성했습니다: {path}",
        "warn_prefix": "[경고]",
    },
    "ja": {
        "description": "Chronicle の Markdown 要約から作業日記の下書きを作成します。",
        "help": "ヘルプを表示して終了します。",
        "date_help": "特定の日付の日記を生成します。形式: YYYY-MM-DD",
        "source_dir_help": "Chronicle Markdown 要約フォルダーのパスを指定します。",
        "out_dir_help": "生成した Markdown を保存するフォルダーです。",
        "dry_run_help": "ファイルを保存せず、結果を stdout に出力します。",
        "day_boundary_help": "1日の区切り時刻を指定します（ローカルタイムゾーン基準、デフォルト: 4）。0〜23 の整数である必要があります。",
        "language_help": "出力言語を指定します。対応コード: {codes}。既定値: {default}。",
        "length_help": "日記の長さを指定します。対応値: {codes}。既定値: {default}。",
        "codex_model_help": "生成に使う Codex モデルを指定します。例: gpt-5.5",
        "error_day_boundary": "--day-boundary-hour は 0 から 23 までの整数である必要があります。",
        "error_invalid_language": "--language には対応している言語コードまたは名前を指定してください。対応コード: {codes}",
        "error_invalid_length": "--length には対応している長さコードを指定してください。対応値: {codes}",
        "error_invalid_codex_model": "--codex-model には有効な Codex モデル名を指定してください。",
        "error_invalid_date": "--date は YYYY-MM-DD 形式で指定してください。",
        "error_missing_sources": "{date} の Chronicle 要約ファイルが見つかりませんでした。入力フォルダーを確認するか、--source-dir を指定してください。",
        "error_connect_required": "先に Codex を接続してください。",
        "error_codex_missing": "先に Codex を接続してください。Codex CLI が見つかりませんでした。",
        "error_cancelled": "生成をキャンセルしました。",
        "success": "作業日記を作成しました: {path}",
        "warn_prefix": "[警告]",
    },
    "zh": {
        "description": "根据 Chronicle 的 Markdown 摘要生成工作日记草稿。",
        "help": "显示此帮助信息并退出。",
        "date_help": "为指定日期生成日记。格式：YYYY-MM-DD",
        "source_dir_help": "指定 Chronicle Markdown 摘要文件夹路径。",
        "out_dir_help": "保存结果 Markdown 的文件夹。",
        "dry_run_help": "不保存文件，直接将结果输出到 stdout。",
        "day_boundary_help": "设置一天的分界小时（按本地时区，默认值：4）。必须是 0 到 23 之间的整数。",
        "language_help": "指定输出语言。支持的代码：{codes}。默认值：{default}。",
        "length_help": "指定日记长度。支持的值：{codes}。默认值：{default}。",
        "codex_model_help": "指定生成时使用的 Codex 模型。例如：gpt-5.5。",
        "error_day_boundary": "--day-boundary-hour 必须是 0 到 23 之间的整数。",
        "error_invalid_language": "--language 必须是受支持的语言代码或名称。支持的代码：{codes}",
        "error_invalid_length": "--length 必须是受支持的长度代码之一。支持的值：{codes}",
        "error_invalid_codex_model": "--codex-model 必须是有效的 Codex 模型名称。",
        "error_invalid_date": "--date 必须使用 YYYY-MM-DD 格式。",
        "error_missing_sources": "找不到 {date} 的 Chronicle 摘要文件。请检查输入文件夹，或使用 --source-dir。",
        "error_connect_required": "请先连接 Codex。",
        "error_codex_missing": "请先连接 Codex。未找到 Codex CLI。",
        "error_cancelled": "已取消生成。",
        "success": "已生成工作日记：{path}",
        "warn_prefix": "[警告]",
    },
    "fr": {
        "description": "Cree un brouillon de journal de travail a partir des resumes Markdown de Chronicle.",
        "help": "Affiche cette aide puis quitte.",
        "date_help": "Genere un journal pour une date precise. Format : YYYY-MM-DD",
        "source_dir_help": "Chemin du dossier de resumes Markdown Chronicle.",
        "out_dir_help": "Dossier ou enregistrer le Markdown genere.",
        "dry_run_help": "Affiche le resultat dans stdout sans enregistrer de fichier.",
        "day_boundary_help": "Heure locale de changement de jour de travail (par defaut : 4). Doit etre un entier entre 0 et 23.",
        "language_help": "Choisit la langue de sortie. Codes pris en charge : {codes}. Valeur par defaut : {default}.",
        "length_help": "Choisit la longueur du journal. Valeurs prises en charge : {codes}. Valeur par defaut : {default}.",
        "error_day_boundary": "--day-boundary-hour doit etre un entier entre 0 et 23.",
        "error_invalid_language": "--language doit etre un code ou un nom de langue pris en charge. Codes pris en charge : {codes}",
        "error_invalid_length": "--length doit etre l'une des longueurs prises en charge. Valeurs prises en charge : {codes}",
        "error_invalid_date": "--date doit etre au format YYYY-MM-DD.",
        "error_missing_sources": "Impossible de trouver les resumes Chronicle pour le {date}. Verifiez le dossier source ou utilisez --source-dir.",
        "error_connect_required": "Connectez d'abord Codex.",
        "error_codex_missing": "Connectez d'abord Codex. Le CLI Codex est introuvable.",
        "error_cancelled": "La generation a ete annulee.",
        "success": "Journal de travail cree : {path}",
        "warn_prefix": "[avertissement]",
    },
    "de": {
        "description": "Erstellt einen Arbeitsnotiz-Entwurf aus Chronicle-Markdown-Zusammenfassungen.",
        "help": "Diese Hilfe anzeigen und beenden.",
        "date_help": "Erstellt ein Tagebuch fuer ein bestimmtes Datum. Format: YYYY-MM-DD",
        "source_dir_help": "Pfad zum Chronicle-Markdown-Zusammenfassungsordner.",
        "out_dir_help": "Ordner, in dem das Ergebnis-Markdown gespeichert wird.",
        "dry_run_help": "Gibt das Ergebnis auf stdout aus, ohne eine Datei zu speichern.",
        "day_boundary_help": "Lokale Tagesgrenze fuer den Arbeitstag (Standard: 4). Muss eine ganze Zahl zwischen 0 und 23 sein.",
        "language_help": "Waehlt die Ausgabesprache. Unterstuetzte Codes: {codes}. Standard: {default}.",
        "length_help": "Waehlt die Tagebuchlaenge. Unterstuetzte Werte: {codes}. Standard: {default}.",
        "error_day_boundary": "--day-boundary-hour muss eine ganze Zahl zwischen 0 und 23 sein.",
        "error_invalid_language": "--language muss ein unterstuetzter Sprachcode oder Name sein. Unterstuetzte Codes: {codes}",
        "error_invalid_length": "--length muss einer der unterstuetzten Laengencodes sein. Unterstuetzte Werte: {codes}",
        "error_invalid_date": "--date muss das Format YYYY-MM-DD haben.",
        "error_missing_sources": "Fuer {date} konnten keine Chronicle-Zusammenfassungen gefunden werden. Pruefe den Eingabeordner oder nutze --source-dir.",
        "error_connect_required": "Verbinde zuerst Codex.",
        "error_codex_missing": "Verbinde zuerst Codex. Das Codex-CLI wurde nicht gefunden.",
        "error_cancelled": "Die Generierung wurde abgebrochen.",
        "success": "Arbeitsnotiz erstellt: {path}",
        "warn_prefix": "[warnung]",
    },
    "es": {
        "description": "Crea un borrador de diario de trabajo a partir de los resumenes Markdown de Chronicle.",
        "help": "Muestra esta ayuda y sale.",
        "date_help": "Genera un diario para una fecha concreta. Formato: YYYY-MM-DD",
        "source_dir_help": "Ruta de la carpeta con resumenes Markdown de Chronicle.",
        "out_dir_help": "Carpeta donde se guardara el Markdown generado.",
        "dry_run_help": "Imprime el resultado en stdout sin guardar ningun archivo.",
        "day_boundary_help": "Hora local que marca el cambio de dia laboral (predeterminado: 4). Debe ser un entero entre 0 y 23.",
        "language_help": "Elige el idioma de salida. Codigos compatibles: {codes}. Valor predeterminado: {default}.",
        "length_help": "Elige la longitud del diario. Valores compatibles: {codes}. Valor predeterminado: {default}.",
        "error_day_boundary": "--day-boundary-hour debe ser un entero entre 0 y 23.",
        "error_invalid_language": "--language debe ser un codigo o nombre de idioma compatible. Codigos compatibles: {codes}",
        "error_invalid_length": "--length debe ser uno de los codigos de longitud compatibles. Valores compatibles: {codes}",
        "error_invalid_date": "--date debe tener el formato YYYY-MM-DD.",
        "error_missing_sources": "No se encontraron resumenes de Chronicle para {date}. Revisa la carpeta de entrada o usa --source-dir.",
        "error_connect_required": "Conecta primero Codex.",
        "error_codex_missing": "Conecta primero Codex. No se encontro el CLI de Codex.",
        "error_cancelled": "La generacion se cancelo.",
        "success": "Diario de trabajo creado: {path}",
        "warn_prefix": "[aviso]",
    },
    "vi": {
        "description": "Tao ban nhap nhat ky cong viec tu cac ban tom tat Markdown cua Chronicle.",
        "help": "Hien tro giup nay va thoat.",
        "date_help": "Tao nhat ky cho mot ngay cu the. Dinh dang: YYYY-MM-DD",
        "source_dir_help": "Duong dan toi thu muc tom tat Markdown cua Chronicle.",
        "out_dir_help": "Thu muc de luu tep Markdown ket qua.",
        "dry_run_help": "In ket qua ra stdout ma khong luu tep.",
        "day_boundary_help": "Gio moc bat dau ngay lam viec theo mui gio cuc bo (mac dinh: 4). Phai la so nguyen tu 0 den 23.",
        "language_help": "Chon ngon ngu dau ra. Ma ho tro: {codes}. Mac dinh: {default}.",
        "length_help": "Chon do dai nhat ky. Gia tri ho tro: {codes}. Mac dinh: {default}.",
        "error_day_boundary": "--day-boundary-hour phai la so nguyen tu 0 den 23.",
        "error_invalid_language": "--language phai la ma hoac ten ngon ngu duoc ho tro. Ma ho tro: {codes}",
        "error_invalid_length": "--length phai la mot trong cac ma do dai duoc ho tro. Gia tri ho tro: {codes}",
        "error_invalid_date": "--date phai theo dinh dang YYYY-MM-DD.",
        "error_missing_sources": "Khong tim thay tom tat Chronicle cho ngay {date}. Hay kiem tra thu muc dau vao hoac dung --source-dir.",
        "error_connect_required": "Hay ket noi Codex truoc.",
        "error_codex_missing": "Hay ket noi Codex truoc. Khong tim thay Codex CLI.",
        "error_cancelled": "Da huy qua trinh tao.",
        "success": "Da tao nhat ky cong viec: {path}",
        "warn_prefix": "[canh bao]",
    },
    "th": {
        "description": "สร้างร่างไดอารีงานจากสรุป Markdown ของ Chronicle",
        "help": "แสดงข้อความช่วยเหลือนี้แล้วออก",
        "date_help": "สร้างไดอารีสำหรับวันที่ที่ระบุ รูปแบบ: YYYY-MM-DD",
        "source_dir_help": "ระบุพาธโฟลเดอร์สรุป Markdown ของ Chronicle",
        "out_dir_help": "โฟลเดอร์สำหรับบันทึกผลลัพธ์ Markdown",
        "dry_run_help": "พิมพ์ผลลัพธ์ไปที่ stdout โดยไม่บันทึกไฟล์",
        "day_boundary_help": "ชั่วโมงที่ใช้เป็นเส้นแบ่งวันทำงานตามเวลาท้องถิ่น (ค่าเริ่มต้น: 4) ต้องเป็นจำนวนเต็ม 0 ถึง 23",
        "language_help": "เลือกภาษาผลลัพธ์ รหัสที่รองรับ: {codes} ค่าเริ่มต้น: {default}",
        "length_help": "เลือกความยาวของไดอารี ค่าที่รองรับ: {codes} ค่าเริ่มต้น: {default}",
        "error_day_boundary": "--day-boundary-hour ต้องเป็นจำนวนเต็มระหว่าง 0 ถึง 23",
        "error_invalid_language": "--language ต้องเป็นรหัสภาษาหรือชื่อภาษาที่รองรับ รหัสที่รองรับ: {codes}",
        "error_invalid_length": "--length ต้องเป็นหนึ่งในค่าความยาวที่รองรับ ค่าที่รองรับ: {codes}",
        "error_invalid_date": "--date ต้องอยู่ในรูปแบบ YYYY-MM-DD",
        "error_missing_sources": "ไม่พบสรุป Chronicle สำหรับวันที่ {date} กรุณาตรวจสอบโฟลเดอร์อินพุตหรือใช้ --source-dir",
        "error_connect_required": "กรุณาเชื่อมต่อ Codex ก่อน",
        "error_codex_missing": "กรุณาเชื่อมต่อ Codex ก่อน ไม่พบ Codex CLI",
        "error_cancelled": "ยกเลิกการสร้างแล้ว",
        "success": "สร้างไดอารีงานแล้ว: {path}",
        "warn_prefix": "[คำเตือน]",
    },
    "ru": {
        "description": "Создает черновик рабочего дневника по Markdown-сводкам Chronicle.",
        "help": "Показать эту справку и выйти.",
        "date_help": "Создать дневник для конкретной даты. Формат: YYYY-MM-DD",
        "source_dir_help": "Путь к папке с Markdown-сводками Chronicle.",
        "out_dir_help": "Папка, куда будет сохранен итоговый Markdown.",
        "dry_run_help": "Выводит результат в stdout без сохранения файла.",
        "day_boundary_help": "Локальный час границы рабочего дня (по умолчанию: 4). Должно быть целое число от 0 до 23.",
        "language_help": "Выберите язык вывода. Поддерживаемые коды: {codes}. По умолчанию: {default}.",
        "length_help": "Выберите длину дневника. Поддерживаемые значения: {codes}. По умолчанию: {default}.",
        "error_day_boundary": "--day-boundary-hour должен быть целым числом от 0 до 23.",
        "error_invalid_language": "--language должен быть поддерживаемым кодом или названием языка. Поддерживаемые коды: {codes}",
        "error_invalid_length": "--length должен быть одним из поддерживаемых кодов длины. Поддерживаемые значения: {codes}",
        "error_invalid_date": "--date должен быть в формате YYYY-MM-DD.",
        "error_missing_sources": "Не удалось найти сводки Chronicle за {date}. Проверьте входную папку или используйте --source-dir.",
        "error_connect_required": "Сначала подключите Codex.",
        "error_codex_missing": "Сначала подключите Codex. CLI Codex не найден.",
        "error_cancelled": "Генерация отменена.",
        "success": "Рабочий дневник создан: {path}",
        "warn_prefix": "[предупреждение]",
    },
    "hi": {
        "description": "Chronicle Markdown सारांशों से कार्य डायरी का ड्राफ्ट बनाता है।",
        "help": "यह सहायता संदेश दिखाकर बाहर निकलें।",
        "date_help": "किसी खास तारीख के लिए डायरी बनाएं। प्रारूप: YYYY-MM-DD",
        "source_dir_help": "Chronicle Markdown सारांश फ़ोल्डर का पथ दें।",
        "out_dir_help": "वह फ़ोल्डर जहाँ परिणाम Markdown सहेजा जाएगा।",
        "dry_run_help": "फ़ाइल सहेजे बिना परिणाम stdout पर दिखाएं।",
        "day_boundary_help": "स्थानीय समय के अनुसार कार्यदिवस की सीमा घंटा (डिफ़ॉल्ट: 4)। यह 0 से 23 के बीच पूर्णांक होना चाहिए।",
        "language_help": "आउटपुट भाषा चुनें। समर्थित कोड: {codes}। डिफ़ॉल्ट: {default}।",
        "length_help": "डायरी की लंबाई चुनें। समर्थित मान: {codes}। डिफ़ॉल्ट: {default}।",
        "error_day_boundary": "--day-boundary-hour 0 से 23 के बीच पूर्णांक होना चाहिए।",
        "error_invalid_language": "--language समर्थित भाषा कोड या नाम होना चाहिए। समर्थित कोड: {codes}",
        "error_invalid_length": "--length समर्थित लंबाई कोड में से एक होना चाहिए। समर्थित मान: {codes}",
        "error_invalid_date": "--date का प्रारूप YYYY-MM-DD होना चाहिए।",
        "error_missing_sources": "{date} के लिए Chronicle सारांश नहीं मिले। इनपुट फ़ोल्डर जाँचें या --source-dir का उपयोग करें।",
        "error_connect_required": "पहले Codex को कनेक्ट करें।",
        "error_codex_missing": "पहले Codex को कनेक्ट करें। Codex CLI नहीं मिला।",
        "error_cancelled": "जेनरेशन रद्द कर दी गई।",
        "success": "कार्य डायरी बन गई: {path}",
        "warn_prefix": "[चेतावनी]",
    },
}


def cli_copy(language_code: str | None) -> dict[str, str]:
    return CLI_COPY[normalize_language_code(language_code) or DEFAULT_LANGUAGE_CODE]


def requested_language_code(argv: list[str] | None) -> str:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--language", "--output-language", dest="language")
    try:
        known_args, _ = pre_parser.parse_known_args(argv)
    except SystemExit:
        return DEFAULT_LANGUAGE_CODE
    return normalize_language_code(getattr(known_args, "language", None)) or DEFAULT_LANGUAGE_CODE


def build_parser(language_code: str | None = None) -> argparse.ArgumentParser:
    copy = cli_copy(language_code)
    parser = argparse.ArgumentParser(
        prog="codex-diary",
        description=copy["description"],
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help=copy["help"],
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("draft-update", "finalize"),
        default="finalize",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--date",
        help=copy["date_help"],
    )
    parser.add_argument(
        "--source-dir",
        default="~/.codex/memories_extensions/chronicle/resources",
        help=copy["source_dir_help"],
    )
    parser.add_argument(
        "--out-dir",
        default=str(repository_root() / "output" / "diary"),
        help=copy["out_dir_help"],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=copy["dry_run_help"],
    )
    parser.add_argument(
        "--day-boundary-hour",
        type=int,
        default=4,
        help=copy["day_boundary_help"],
    )
    parser.add_argument(
        "--language",
        "--output-language",
        dest="language",
        default=DEFAULT_LANGUAGE_CODE,
        help=copy["language_help"].format(
            codes=", ".join(supported_language_codes()),
            default=DEFAULT_LANGUAGE_CODE,
        ),
    )
    parser.add_argument(
        "--length",
        "--diary-length",
        dest="diary_length",
        default=DEFAULT_DIARY_LENGTH_CODE,
        help=copy["length_help"].format(
            codes=", ".join(supported_diary_length_codes()),
            default=DEFAULT_DIARY_LENGTH_CODE,
        ),
    )
    parser.add_argument(
        "--codex-model",
        default=None,
        help=copy.get("codex_model_help", CLI_COPY["en"]["codex_model_help"]),
    )
    return parser


def normalized_exception_message(
    exc: Exception,
    *,
    language_code: str,
    target_date_iso: str,
) -> str:
    copy = cli_copy(language_code)
    message = str(exc)
    if "Chronicle 요약 파일을 찾지 못했습니다" in message:
        return copy["error_missing_sources"].format(date=target_date_iso)
    if message.startswith(CODEX_MISSING_MESSAGE):
        return copy["error_codex_missing"]
    if message.startswith(CODEX_NOT_CONNECTED_MESSAGE):
        return copy["error_connect_required"]
    if "생성을 취소했어요." in message:
        return copy["error_cancelled"]
    return message


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    language_code = requested_language_code(argv)
    copy = cli_copy(language_code)
    parser = build_parser(language_code)
    args = parser.parse_args(argv)

    if not 0 <= args.day_boundary_hour <= 23:
        print(copy["error_day_boundary"], file=sys.stderr)
        return 2
    language_code = normalize_language_code(args.language)
    if not language_code:
        print(copy["error_invalid_language"].format(codes=", ".join(supported_language_codes())), file=sys.stderr)
        return 2
    copy = cli_copy(language_code)
    diary_length_code = normalize_diary_length(args.diary_length)
    if not diary_length_code:
        print(copy["error_invalid_length"].format(codes=", ".join(supported_diary_length_codes())), file=sys.stderr)
        return 2
    try:
        codex_model = normalize_codex_model(args.codex_model) if args.codex_model else None
    except LLMError:
        print(copy.get("error_invalid_codex_model", CLI_COPY["en"]["error_invalid_codex_model"]), file=sys.stderr)
        return 2

    try:
        target_date = resolve_target_date(
            args.date,
            day_boundary_hour=args.day_boundary_hour,
        )
    except ValueError:
        print(copy["error_invalid_date"], file=sys.stderr)
        return 2

    source_dir = Path(args.source_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()

    try:
        result = build_diary(
            target_date=target_date,
            mode="finalize",
            source_dir=source_dir,
            out_dir=out_dir,
            day_boundary_hour=args.day_boundary_hour,
            output_language=language_code,
            diary_length=diary_length_code,
            codex_model=codex_model,
        )
    except FileNotFoundError as exc:
        print(
            normalized_exception_message(
                exc,
                language_code=language_code,
                target_date_iso=target_date.isoformat(),
            ),
            file=sys.stderr,
        )
        return 1
    except LLMError as exc:
        print(
            normalized_exception_message(
                exc,
                language_code=language_code,
                target_date_iso=target_date.isoformat(),
            ),
            file=sys.stderr,
        )
        return 1

    for warning in result.warnings:
        print(f"{copy['warn_prefix']} {warning}", file=sys.stderr)

    if args.dry_run:
        print(result.markdown, end="" if result.markdown.endswith("\n") else "\n")
        return 0

    for legacy_path in legacy_output_paths(out_dir, target_date.isoformat()):
        if legacy_path.exists():
            legacy_path.unlink()
    result.output_path.parent.mkdir(parents=True, exist_ok=True)
    result.output_path.write_text(result.markdown, encoding="utf-8")
    print(copy["success"].format(path=result.output_path))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
