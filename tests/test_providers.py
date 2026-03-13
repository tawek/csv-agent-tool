from types import SimpleNamespace

import pytest

from product_description_tool.providers import OllamaProvider, OpenAIProvider


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._data


def test_ollama_provider_uses_chat_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["init"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse({"message": {"content": "<p>Output</p>"}})

    monkeypatch.setattr("product_description_tool.providers.httpx.Client", FakeClient)

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3",
        options={"top_k": 20},
    )
    output = provider.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=300,
    )

    assert output == "<p>Output</p>"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["options"]["top_k"] == 20


def test_openai_provider_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="<p>Out</p>"))]
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
    output = provider.generate(
        system_prompt="system",
        user_prompt="user",
        temperature=0.3,
        top_p=0.8,
        max_output_tokens=111,
    )

    assert output == "<p>Out</p>"
    assert captured["client_kwargs"] == {
        "api_key": "secret",
        "base_url": "https://example.com/v1",
    }
    assert captured["max_tokens"] == 111
    assert captured["extra_body"] == {"frequency_penalty": 0.2}
