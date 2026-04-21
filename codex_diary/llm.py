from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Optional
from urllib import error, request


class LLMError(RuntimeError):
    """Raised when an LLM request fails."""


@dataclass
class LLMConfig:
    provider: Optional[str]
    model: str
    base_url: str
    api_key: Optional[str]


class LLMProvider:
    def generate_markdown(self, prompt: str) -> str:
        raise NotImplementedError


class OpenAIResponsesProvider(LLMProvider):
    def __init__(self, *, model: str, base_url: str, api_key: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def generate_markdown(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You generate Korean work diary drafts from Chronicle summaries. "
                                "Do not invent facts, projects, actions, or emotions. "
                                "If emotion is not explicit, stay restrained and describe focus, comparison, or review only. "
                                "Never quote secrets, tokens, phone numbers, or emails. "
                                "Return Markdown only."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
        }
        encoded = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/responses",
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"OpenAI 응답 호출이 실패했습니다: HTTP {exc.code} - {body}") from exc
        except error.URLError as exc:
            raise LLMError(f"OpenAI 응답 호출이 실패했습니다: {exc.reason}") from exc

        if isinstance(raw.get("output_text"), str) and raw["output_text"].strip():
            return raw["output_text"].strip()

        fragments = []
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    fragments.append(content["text"])
        text = "\n".join(fragment.strip() for fragment in fragments if fragment.strip())
        if not text:
            raise LLMError("LLM 응답에서 본문 텍스트를 찾지 못했습니다.")
        return text


def load_provider_from_env() -> Optional[LLMProvider]:
    provider = os.getenv("DIARY_LLM_PROVIDER", "openai").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    if provider != "openai":
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return OpenAIResponsesProvider(model=model, base_url=base_url, api_key=api_key)
