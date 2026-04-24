from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Optional

from .diary_length import DEFAULT_DIARY_LENGTH_CODE, normalize_diary_length


CODEX_NOT_CONNECTED_MESSAGE = "먼저 codex를 연결해주세요."
CODEX_MISSING_MESSAGE = "먼저 codex를 연결해주세요. Codex CLI를 찾지 못했습니다."
CODEX_LOGIN_LAUNCHED_MESSAGE = "Codex 로그인 창을 열었어요. 연결이 끝나면 다시 생성해 주세요."
CODEX_EXEC_TIMEOUT_SECONDS = 240
CODEX_EXEC_TIMEOUTS_BY_LENGTH = {
    "short": 240,
    "medium": 240,
    "long": 300,
    "very-long": 360,
}
CODEX_PROGRESS_HEARTBEAT_SECONDS = 0.8
DEFAULT_CODEX_MODEL = "gpt-5.4"
SUPPORTED_CODEX_MODELS = (
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.3-codex",
    "gpt-5.3-codex-spark",
    "gpt-5.2",
)
CODEX_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$")
COMMON_CODEX_PATHS = (
    "/opt/homebrew/bin/codex",
    "/usr/local/bin/codex",
    "/usr/bin/codex",
    "~/.local/bin/codex",
)

ProviderProgressCallback = Callable[[dict[str, Any]], None]
CancellationCheck = Callable[[], bool]

CODEX_LOGIN_ERROR_MARKERS = (
    "not logged in",
    "login required",
    "please run codex login",
)
CODEX_MODEL_ERROR_MARKERS = (
    "does not exist or you do not have access",
    "model_not_found",
    "unsupported model",
    "invalid model",
)
CODEX_TOKEN_REFRESH_MARKERS = (
    "invalid refresh token",
    "invalid_grant",
)


class LLMError(RuntimeError):
    """Raised when an LLM request fails."""


class CodexConnectionError(LLMError):
    """Raised when Codex CLI is not available or not logged in."""


class GenerationCancelledError(LLMError):
    """Raised when an in-flight generation is cancelled by the user."""


@dataclass(frozen=True)
class CodexStatus:
    available: bool
    connected: bool
    auth_mode: Optional[str]
    message: str
    command: Optional[str]
    raw_output: str = ""
    configured_model: Optional[str] = None

    def to_json(self) -> dict[str, Optional[str] | bool]:
        return {
            "available": self.available,
            "connected": self.connected,
            "auth_mode": self.auth_mode,
            "message": self.message,
            "command": self.command,
            "raw_output": self.raw_output,
            "configured_model": self.configured_model,
        }


class LLMProvider:
    def generate_markdown(
        self,
        prompt: str,
        *,
        output_language: str | None = None,
        progress: Optional[ProviderProgressCallback] = None,
        should_cancel: Optional[CancellationCheck] = None,
    ) -> str:
        raise NotImplementedError


def find_codex_command() -> Optional[str]:
    discovered = shutil.which("codex")
    if discovered:
        return discovered
    for candidate in COMMON_CODEX_PATHS:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return str(path)
    return None


def normalize_codex_model(value: str | None) -> Optional[str]:
    if value is None:
        return None
    model = str(value).strip()
    if not model:
        return None
    if not CODEX_MODEL_PATTERN.match(model):
        raise LLMError(f"Codex 모델 이름이 올바르지 않아요: {model}")
    return model


def read_codex_config_model(config_path: Path | None = None) -> Optional[str]:
    path = config_path or Path("~/.codex/config.toml").expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("model"):
            continue
        match = re.match(r'^model\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$', line)
        if not match:
            continue
        try:
            return normalize_codex_model(match.group(1))
        except LLMError:
            return None
    return None


def default_codex_model() -> str:
    return read_codex_config_model() or DEFAULT_CODEX_MODEL


def get_codex_status() -> CodexStatus:
    command = find_codex_command()
    configured_model = read_codex_config_model()
    if not command:
        return CodexStatus(
            available=False,
            connected=False,
            auth_mode=None,
            message=CODEX_MISSING_MESSAGE,
            command=None,
            configured_model=configured_model,
        )

    try:
        proc = subprocess.run(
            [command, "login", "status"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except OSError as exc:
        return CodexStatus(
            available=False,
            connected=False,
            auth_mode=None,
            message=f"{CODEX_MISSING_MESSAGE} ({exc})",
            command=command,
            configured_model=configured_model,
        )
    except subprocess.TimeoutExpired:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message="Codex 연결 상태를 확인하는 중 시간이 너무 오래 걸렸어요. 잠시 후 다시 시도해 주세요.",
            command=command,
            configured_model=configured_model,
        )

    raw_output = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part).strip()
    normalized = raw_output.lower()
    if "logged in using" in normalized:
        auth_mode = "chatgpt" if "chatgpt" in normalized else "api-key" if "api key" in normalized else "unknown"
        return CodexStatus(
            available=True,
            connected=True,
            auth_mode=auth_mode,
            message="Codex가 연결되어 있어요.",
            command=command,
            raw_output=raw_output,
            configured_model=configured_model,
        )
    if "not logged in" in normalized or "login required" in normalized:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message=CODEX_NOT_CONNECTED_MESSAGE,
            command=command,
            raw_output=raw_output,
            configured_model=configured_model,
        )
    if proc.returncode != 0:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message=CODEX_NOT_CONNECTED_MESSAGE,
            command=command,
            raw_output=raw_output,
            configured_model=configured_model,
        )
    return CodexStatus(
        available=True,
        connected=False,
        auth_mode=None,
        message=CODEX_NOT_CONNECTED_MESSAGE,
        command=command,
        raw_output=raw_output,
        configured_model=configured_model,
    )


def ensure_codex_connected() -> CodexStatus:
    status = get_codex_status()
    if not status.connected:
        raise CodexConnectionError(status.message or CODEX_NOT_CONNECTED_MESSAGE)
    return status


def codex_login_command_args(*, device_auth: bool = True) -> list[str]:
    command = find_codex_command()
    if not command:
        raise CodexConnectionError(CODEX_MISSING_MESSAGE)
    args = [command, "login"]
    if device_auth:
        args.append("--device-auth")
    return args


def codex_timeout_seconds_for_length(diary_length: str | None) -> int:
    normalized = normalize_diary_length(
        diary_length,
        default=DEFAULT_DIARY_LENGTH_CODE,
    ) or DEFAULT_DIARY_LENGTH_CODE
    return CODEX_EXEC_TIMEOUTS_BY_LENGTH.get(normalized, CODEX_EXEC_TIMEOUT_SECONDS)


def _codex_error_detail(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "알 수 없는 오류"
    for marker in CODEX_MODEL_ERROR_MARKERS:
        for line in lines:
            if marker in line.lower():
                return line
    for line in lines:
        normalized = line.lower()
        if "error" in normalized and "rmcp::transport" not in normalized:
            return line
    for line in lines:
        normalized = line.lower()
        if "rmcp::transport" not in normalized and "warning" not in normalized:
            return line
    return lines[0]


def _raise_codex_exec_error(text: str) -> None:
    normalized = text.lower()
    detail = _codex_error_detail(text)
    if any(marker in normalized for marker in CODEX_MODEL_ERROR_MARKERS):
        raise LLMError(f"Codex CLI에서 현재 설정된 모델을 사용할 수 없어요: {detail}")
    if any(marker in normalized for marker in CODEX_LOGIN_ERROR_MARKERS):
        raise CodexConnectionError(CODEX_NOT_CONNECTED_MESSAGE)
    if any(marker in normalized for marker in CODEX_TOKEN_REFRESH_MARKERS):
        raise LLMError(
            "Codex CLI 실행 중 인증 토큰 갱신에 실패했어요. "
            "상단 상태가 준비됨이어도 CLI 실행 세션을 다시 연결해야 할 수 있어요."
        )
    raise LLMError(f"Codex 호출이 실패했습니다: {detail}")


class CodexCliProvider(LLMProvider):
    def __init__(
        self,
        *,
        command: str,
        timeout_seconds: int = CODEX_EXEC_TIMEOUT_SECONDS,
        model: str | None = None,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.model = normalize_codex_model(model)

    @staticmethod
    def _emit_progress(
        progress: Optional[ProviderProgressCallback],
        *,
        detail_key: str,
        percent: int,
        indeterminate: bool = False,
    ) -> None:
        if progress is None:
            return
        progress(
            {
                "status": "running",
                "phase": "write",
                "step_key": "loading.step.write",
                "detail_key": detail_key,
                "percent": percent,
                "indeterminate": indeterminate,
            }
        )

    def generate_markdown(
        self,
        prompt: str,
        *,
        output_language: str | None = None,
        progress: Optional[ProviderProgressCallback] = None,
        should_cancel: Optional[CancellationCheck] = None,
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="codex-diary-codex-") as tmpdir:
            tmp_path = Path(tmpdir)
            output_path = tmp_path / "final.md"
            stdout_path = tmp_path / "stdout.log"
            stderr_path = tmp_path / "stderr.log"
            cmd = [
                self.command,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "-C",
                str(tmp_path),
                "-o",
                str(output_path),
                "-",
            ]
            if self.model:
                cmd[2:2] = ["-m", self.model]
            self._emit_progress(
                progress,
                detail_key="loading.detail.writePrepare",
                percent=70,
            )
            if should_cancel is not None and should_cancel():
                raise GenerationCancelledError("생성을 취소했어요.")
            try:
                with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
                    "w", encoding="utf-8"
                ) as stderr_handle:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        text=True,
                    )
                    self._emit_progress(
                        progress,
                        detail_key="loading.detail.writeStart",
                        percent=74,
                    )
                    stdin_handle = proc.stdin
                    try:
                        if stdin_handle is not None:
                            stdin_handle.write(prompt)
                    except BrokenPipeError:
                        pass
                    finally:
                        if stdin_handle is not None:
                            try:
                                stdin_handle.close()
                            except BrokenPipeError:
                                pass

                    self._emit_progress(
                        progress,
                        detail_key="loading.detail.writeWait",
                        percent=78,
                        indeterminate=True,
                    )
                    deadline = time.monotonic() + self.timeout_seconds
                    next_heartbeat = time.monotonic() + CODEX_PROGRESS_HEARTBEAT_SECONDS
                    while proc.poll() is None:
                        if should_cancel is not None and should_cancel():
                            proc.kill()
                            proc.wait(timeout=5)
                            raise GenerationCancelledError("생성을 취소했어요.")
                        now = time.monotonic()
                        if now >= deadline:
                            proc.kill()
                            proc.wait(timeout=5)
                            raise LLMError("Codex 응답이 너무 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.")
                        if now >= next_heartbeat:
                            self._emit_progress(
                                progress,
                                detail_key="loading.detail.writeWait",
                                percent=78,
                                indeterminate=True,
                            )
                            next_heartbeat = now + CODEX_PROGRESS_HEARTBEAT_SECONDS
                        time.sleep(0.1)
                    return_code = proc.returncode
            except FileNotFoundError as exc:
                raise CodexConnectionError(CODEX_MISSING_MESSAGE) from exc

            self._emit_progress(
                progress,
                detail_key="loading.detail.writeCheck",
                percent=84,
            )
            stdout_text = stdout_path.read_text(encoding="utf-8").strip() if stdout_path.exists() else ""
            stderr_text = stderr_path.read_text(encoding="utf-8").strip() if stderr_path.exists() else ""

            if return_code != 0:
                combined = "\n".join(part for part in (stderr_text, stdout_text) if part).strip()
                _raise_codex_exec_error(combined)

            if not output_path.exists():
                raise LLMError("Codex 응답 파일을 찾지 못했습니다.")
            self._emit_progress(
                progress,
                detail_key="loading.detail.writeReady",
                percent=88,
            )
            markdown = output_path.read_text(encoding="utf-8").strip()
            if not markdown:
                raise LLMError("Codex가 비어 있는 응답을 돌려줬어요.")
            return markdown


CodexCLIProvider = CodexCliProvider


def load_provider_from_codex(
    *,
    diary_length: str | None = None,
    codex_model: str | None = None,
) -> LLMProvider:
    status = ensure_codex_connected()
    if not status.command:
        raise CodexConnectionError(CODEX_MISSING_MESSAGE)
    return CodexCliProvider(
        command=status.command,
        timeout_seconds=codex_timeout_seconds_for_length(diary_length),
        model=codex_model,
    )
