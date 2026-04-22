from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Optional


CODEX_NOT_CONNECTED_MESSAGE = "먼저 codex를 연결해주세요."
CODEX_MISSING_MESSAGE = "먼저 codex를 연결해주세요. Codex CLI를 찾지 못했습니다."
CODEX_LOGIN_LAUNCHED_MESSAGE = "Codex 로그인 창을 열었어요. 연결이 끝나면 다시 생성해 주세요."
CODEX_EXEC_TIMEOUT_SECONDS = 240
CODEX_PROGRESS_HEARTBEAT_SECONDS = 0.8
COMMON_CODEX_PATHS = (
    "/opt/homebrew/bin/codex",
    "/usr/local/bin/codex",
    "/usr/bin/codex",
    "~/.local/bin/codex",
)

ProviderProgressCallback = Callable[[dict[str, Any]], None]
CancellationCheck = Callable[[], bool]


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

    def to_json(self) -> dict[str, Optional[str] | bool]:
        return {
            "available": self.available,
            "connected": self.connected,
            "auth_mode": self.auth_mode,
            "message": self.message,
            "command": self.command,
            "raw_output": self.raw_output,
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


def get_codex_status() -> CodexStatus:
    command = find_codex_command()
    if not command:
        return CodexStatus(
            available=False,
            connected=False,
            auth_mode=None,
            message=CODEX_MISSING_MESSAGE,
            command=None,
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
        )
    except subprocess.TimeoutExpired:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message="Codex 연결 상태를 확인하는 중 시간이 너무 오래 걸렸어요. 잠시 후 다시 시도해 주세요.",
            command=command,
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
        )
    if "not logged in" in normalized or "login required" in normalized:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message=CODEX_NOT_CONNECTED_MESSAGE,
            command=command,
            raw_output=raw_output,
        )
    if proc.returncode != 0:
        return CodexStatus(
            available=True,
            connected=False,
            auth_mode=None,
            message=CODEX_NOT_CONNECTED_MESSAGE,
            command=command,
            raw_output=raw_output,
        )
    return CodexStatus(
        available=True,
        connected=False,
        auth_mode=None,
        message=CODEX_NOT_CONNECTED_MESSAGE,
        command=command,
        raw_output=raw_output,
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


class CodexCliProvider(LLMProvider):
    def __init__(self, *, command: str, timeout_seconds: int = CODEX_EXEC_TIMEOUT_SECONDS) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

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
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "-C",
                str(tmp_path),
                "-o",
                str(output_path),
                "-",
            ]
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
                normalized = combined.lower()
                if "not logged in" in normalized or "login required" in normalized or "invalid refresh token" in normalized:
                    raise CodexConnectionError(CODEX_NOT_CONNECTED_MESSAGE)
                detail = combined.splitlines()[0] if combined else "알 수 없는 오류"
                raise LLMError(f"Codex 호출이 실패했습니다: {detail}")

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


def load_provider_from_codex() -> LLMProvider:
    status = ensure_codex_connected()
    if not status.command:
        raise CodexConnectionError(CODEX_MISSING_MESSAGE)
    return CodexCliProvider(command=status.command)
