from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMProviderError(RuntimeError):
    pass


class LLMValidationError(LLMProviderError):
    pass


@dataclass(frozen=True)
class PromptPackage:
    system: str
    user: str
    prompt_version: str


@dataclass(frozen=True)
class LLMProviderResult:
    provider: str
    model: str
    parsed_json: dict[str, Any]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, *, prompt: PromptPackage) -> LLMProviderResult:
        raise NotImplementedError
