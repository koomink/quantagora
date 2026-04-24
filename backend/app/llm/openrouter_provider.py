import httpx

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider, LLMProviderError, LLMProviderResult, PromptPackage
from app.llm.openai_provider import _parse_chat_completion_json


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def generate_json(self, *, prompt: PromptPackage) -> LLMProviderResult:
        api_key = self.settings.openrouter_api_key.strip()
        if not api_key:
            raise LLMProviderError("OPENROUTER_API_KEY is not configured.")

        base_url = (self.settings.llm_base_url or "https://openrouter.ai/api/v1").rstrip("/")
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
            "X-Title": self.settings.openrouter_app_name,
        }
        if self.settings.openrouter_site_url:
            headers["HTTP-Referer"] = self.settings.openrouter_site_url

        with httpx.Client(
            base_url=base_url,
            timeout=self.settings.llm_timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                response = client.post("/chat/completions", headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise LLMProviderError(f"OpenRouter request failed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"OpenRouter request failed: {exc.response.text}") from exc

        body = response.json()
        parsed = _parse_chat_completion_json(body)
        return LLMProviderResult(
            provider="openrouter",
            model=self.settings.llm_model,
            parsed_json=parsed,
            request_payload=payload,
            response_payload=body,
        )
