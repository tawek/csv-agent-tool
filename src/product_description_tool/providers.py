from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Callable

import httpx
from openai import OpenAI

from product_description_tool.config import AppConfig


class ProviderError(RuntimeError):
    pass


class GenerationCancelled(RuntimeError):
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
        on_chunk: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
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
        on_chunk: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if not self.model:
            raise ProviderError("Ollama model is not configured.")
        payload = {
            "model": self.model,
            "stream": True,
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
        chunks: list[str] = []
        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if should_cancel is not None and should_cancel():
                        raise GenerationCancelled("Generation cancelled.")
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ProviderError("Ollama returned malformed streamed output.") from exc
                    chunk = ((data.get("message") or {}).get("content") or "")
                    if chunk:
                        chunks.append(chunk)
                        if on_chunk is not None:
                            on_chunk(chunk)
        content = "".join(chunks).strip()
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
        on_chunk: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured.")
        if not self.model:
            raise ProviderError("OpenAI model is not configured.")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_output_tokens,
            stream=True,
            extra_body=self.options or None,
        )
        chunks: list[str] = []
        try:
            for event in stream:
                if should_cancel is not None and should_cancel():
                    raise GenerationCancelled("Generation cancelled.")
                choice = event.choices[0] if event.choices else None
                delta = choice.delta if choice is not None else None
                chunk = delta.content if delta is not None else ""
                if isinstance(chunk, list):
                    chunk = "".join(
                        part.text
                        for part in chunk
                        if getattr(part, "type", None) == "text" and getattr(part, "text", None)
                    )
                if chunk:
                    chunks.append(chunk)
                    if on_chunk is not None:
                        on_chunk(chunk)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        content = "".join(chunks).strip()
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
