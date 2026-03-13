from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx
from openai import OpenAI

from product_description_tool.config import AppConfig


class ProviderError(RuntimeError):
    pass


class ProviderClient(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        top_p: float,
        max_output_tokens: int,
    ) -> str:
        raise NotImplementedError


class OllamaProvider(ProviderClient):
    def __init__(self, base_url: str, model: str, options: dict[str, Any]) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.options = options

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        top_p: float,
        max_output_tokens: int,
    ) -> str:
        if not self.model:
            raise ProviderError("Ollama model is not configured.")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_output_tokens,
                **self.options,
            },
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        if not content:
            raise ProviderError("Ollama returned an empty response.")
        return content


class OpenAIProvider(ProviderClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        options: dict[str, Any],
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.options = options

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        top_p: float,
        max_output_tokens: int,
    ) -> str:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured.")
        if not self.model:
            raise ProviderError("OpenAI model is not configured.")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_output_tokens,
            extra_body=self.options or None,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ProviderError("OpenAI-compatible endpoint returned an empty response.")
        return content


def build_provider(config: AppConfig) -> ProviderClient:
    if config.provider.active == "openai":
        settings = config.provider.openai
        return OpenAIProvider(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            options=settings.options,
        )

    settings = config.provider.ollama
    return OllamaProvider(
        base_url=settings.base_url,
        model=settings.model,
        options=settings.options,
    )
