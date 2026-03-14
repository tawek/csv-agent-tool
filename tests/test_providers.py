import json
from types import SimpleNamespace

import pytest

from product_description_tool.providers import (
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
    list_ollama_models,
    list_openai_models,
)


class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        return iter(self._lines)


def test_ollama_provider_uses_chat_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["init"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, json):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = json
            return FakeStreamResponse(
                [
                    json_module.dumps({"message": {"content": "<p>Out"}}),
                    json_module.dumps({"message": {"content": "put</p>"}, "done": False}),
                    json_module.dumps({"done": True}),
                ]
            )

    json_module = json
    monkeypatch.setattr("product_description_tool.providers.httpx.Client", FakeClient)

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3",
        options={"top_k": 20},
    )
    chunks: list[str] = []
    output = provider.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=300,
        on_chunk=chunks.append,
    )

    assert output == "<p>Output</p>"
    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["stream"] is True
    assert captured["json"]["options"]["top_k"] == 20
    assert chunks == ["<p>Out", "put</p>"]


def test_openai_provider_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return iter(
                [
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content="<p>Out"))]
                    ),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content="</p>"))]
                    ),
                ]
            )

    class FakeOpenAIClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setattr("product_description_tool.providers.OpenAI", FakeOpenAIClient)

    provider = OpenAIProvider(
        base_url="https://example.com/v1",
        api_key="secret",
        model="gpt-test",
        options={"frequency_penalty": 0.2},
    )
    chunks: list[str] = []
    output = provider.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.3,
        top_p=0.8,
        max_output_tokens=111,
        on_chunk=chunks.append,
    )

    assert output == "<p>Out</p>"
    assert captured["client_kwargs"]["api_key"] == "secret"
    assert captured["client_kwargs"]["base_url"] == "https://example.com/v1"
    import httpx
    assert isinstance(captured["client_kwargs"]["http_client"], httpx.Client)
    assert captured["max_tokens"] == 111
    assert captured["stream"] is True
    assert captured["extra_body"] == {"frequency_penalty": 0.2}
    assert chunks == ["<p>Out", "</p>"]


def test_list_ollama_models_reads_api_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "models": [
                    {"name": "llama3.2"},
                    {"model": "mistral:latest"},
                    {"name": "llama3.2"},
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["init"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("product_description_tool.providers.httpx.Client", FakeClient)

    assert list_ollama_models(base_url="http://localhost:11434/") == [
        "llama3.2",
        "mistral:latest",
    ]
    assert captured["url"] == "http://localhost:11434/api/tags"
    assert captured["init"]["timeout"] == 30.0


def test_list_openai_models_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeModels:
        def list(self):
            captured["called"] = True
            return SimpleNamespace(
                data=[
                    SimpleNamespace(id="gpt-5-mini"),
                    SimpleNamespace(id="gpt-5"),
                    SimpleNamespace(id="gpt-5-mini"),
                ]
            )

    class FakeOpenAIClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.models = FakeModels()

    monkeypatch.setattr("product_description_tool.providers.OpenAI", FakeOpenAIClient)

    assert list_openai_models(base_url="https://api.openai.com/v1", api_key="secret") == [
        "gpt-5",
        "gpt-5-mini",
    ]
    assert captured["client_kwargs"] == {
        "api_key": "secret",
        "base_url": "https://api.openai.com/v1",
    }
    assert captured["called"] is True


def test_list_openai_models_requires_api_key() -> None:
    with pytest.raises(ProviderError, match="API key"):
        list_openai_models(base_url="https://api.openai.com/v1", api_key="")
