from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable

import httpx
from openai import OpenAI

from product_description_tool.config import AppConfig


class ProviderError(RuntimeError):
    pass


class GenerationCancelled(RuntimeError):
    pass


class ProviderClient(ABC):
    def cancel(self) -> None:
        return None

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


def _sorted_model_names(names: Iterable[str]) -> list[str]:
    return sorted({name.strip() for name in names if name and name.strip()}, key=str.casefold)


def list_ollama_models(*, base_url: str) -> list[str]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
        payload = response.json()

    models = payload.get("models")
    if not isinstance(models, list):
        raise ProviderError("Ollama returned an unexpected model list response.")

    model_names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("model") or item.get("name")
        if isinstance(name, str):
            model_names.append(name)
    return _sorted_model_names(model_names)


def list_openai_models(*, base_url: str, api_key: str) -> list[str]:
    if not api_key:
        raise ProviderError("OpenAI API key is not configured.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.models.list()
    models = getattr(response, "data", None)
    if models is None:
        models = list(response)

    model_ids: list[str] = []
    for item in models:
        if isinstance(item, dict):
            model_id = item.get("id")
        else:
            model_id = getattr(item, "id", None)
        if isinstance(model_id, str):
            model_ids.append(model_id)
    return _sorted_model_names(model_ids)


class OllamaProvider(ProviderClient):
    def __init__(self, base_url: str, model: str, options: dict[str, Any]) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.options = options
        self._http_client: httpx.Client | None = None
        self._http_client_lock = threading.Lock()

    def cancel(self) -> None:
        with self._http_client_lock:
            client = self._http_client
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

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
        if should_cancel is not None and should_cancel():
            raise GenerationCancelled("Generation cancelled.")
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
        http_client = httpx.Client(timeout=120.0)
        with self._http_client_lock:
            self._http_client = http_client
        chunks: list[str] = []
        try:
            with http_client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
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
        except httpx.HTTPError as exc:
            if should_cancel is not None and should_cancel():
                raise GenerationCancelled("Generation cancelled.") from exc
            raise
        finally:
            with self._http_client_lock:
                self._http_client = None
            try:
                http_client.close()
            except Exception:  # noqa: BLE001
                pass
        if should_cancel is not None and should_cancel():
            raise GenerationCancelled("Generation cancelled.")
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
        self._http_client: httpx.Client | None = None
        self._http_client_lock = threading.Lock()

    def cancel(self) -> None:
        with self._http_client_lock:
            client = self._http_client
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

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
        if should_cancel is not None and should_cancel():
            raise GenerationCancelled("Generation cancelled.")

        http_client = httpx.Client()
        with self._http_client_lock:
            self._http_client = http_client
        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, http_client=http_client)
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
            except Exception as exc:  # noqa: BLE001
                if should_cancel is not None and should_cancel():
                    raise GenerationCancelled("Generation cancelled.") from exc
                raise
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:  # noqa: BLE001
                        pass
        except httpx.RemoteProtocolError as exc:
            if should_cancel is not None and should_cancel():
                raise GenerationCancelled("Generation cancelled.") from exc
            raise ProviderError(str(exc)) from exc
        except httpx.HTTPError as exc:
            if should_cancel is not None and should_cancel():
                raise GenerationCancelled("Generation cancelled.") from exc
            raise
        finally:
            with self._http_client_lock:
                self._http_client = None
            try:
                http_client.close()
            except Exception:  # noqa: BLE001
                pass

        if should_cancel is not None and should_cancel():
            raise GenerationCancelled("Generation cancelled.")
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
