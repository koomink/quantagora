import json
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider, LLMProviderError, LLMProviderResult, PromptPackage


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def generate_json(self, *, prompt: PromptPackage) -> LLMProviderResult:
        api_key = self.settings.openai_api_key.strip()
        if not api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")

        base_url = (self.settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(
            base_url=base_url,
            timeout=self.settings.llm_timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                response = client.post("/chat/completions", headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc.response.text}") from exc

        body = response.json()
        parsed = _parse_chat_completion_json(body)
        return LLMProviderResult(
            provider="openai",
            model=self.settings.llm_model,
            parsed_json=parsed,
            request_payload=payload,
            response_payload=body,
        )


def _parse_chat_completion_json(body: dict[str, Any]) -> dict[str, Any]:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError("LLM response did not include a chat completion message.") from exc

    if not isinstance(content, str):
        raise LLMProviderError("LLM message content was not a JSON string.")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("LLM message content was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise LLMProviderError("LLM JSON response must be an object.")
    return parsed
