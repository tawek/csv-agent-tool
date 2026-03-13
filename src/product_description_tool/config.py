from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir


@dataclass(slots=True)
class FieldConfig:
    label: str | None = None
    show: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldConfig":
        return cls(label=data.get("label"), show=bool(data.get("show", True)))


@dataclass(slots=True)
class CsvConfig:
    original_description: str = "description"
    result_description: str = "generated_description"
    fields: dict[str, FieldConfig] = field(default_factory=dict)
    delimiter: str = ","
    quotechar: str = '"'
    encoding: str = "utf-8-sig"
    newline: str = ""
    write_header: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CsvConfig":
        fields = {
            key: FieldConfig.from_dict(value)
            for key, value in data.get("fields", {}).items()
        }
        return cls(
            original_description=data.get("original-description", "description"),
            result_description=data.get("result-description", "generated_description"),
            fields=fields,
            delimiter=data.get("delimiter", ",") or ",",
            quotechar=data.get("quotechar", '"') or '"',
            encoding=data.get("encoding", "utf-8-sig"),
            newline=data.get("newline", ""),
            write_header=bool(data.get("write_header", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "original-description": self.original_description,
            "result-description": self.result_description,
            "fields": {
                key: asdict(value)
                for key, value in self.fields.items()
            },
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "encoding": self.encoding,
            "newline": self.newline,
            "write_header": self.write_header,
        }


@dataclass(slots=True)
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OllamaConfig":
        return cls(
            base_url=data.get("base_url", "http://localhost:11434"),
            model=data.get("model", ""),
            options=dict(data.get("options", {})),
        )


@dataclass(slots=True)
class OpenAIConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenAIConfig":
        return cls(
            base_url=data.get("base_url", "https://api.openai.com/v1"),
            api_key=data.get("api_key", ""),
            model=data.get("model", ""),
            options=dict(data.get("options", {})),
        )


@dataclass(slots=True)
class ProviderConfig:
    active: str = "ollama"
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        return cls(
            active=data.get("active", "ollama"),
            ollama=OllamaConfig.from_dict(data.get("ollama", {})),
            openai=OpenAIConfig.from_dict(data.get("openai", {})),
        )


@dataclass(slots=True)
class GenerationConfig:
    temperature: float = 0.2
    top_p: float = 1.0
    max_output_tokens: int = 500

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationConfig":
        return cls(
            temperature=float(data.get("temperature", 0.2)),
            top_p=float(data.get("top_p", 1.0)),
            max_output_tokens=int(data.get("max_output_tokens", 500)),
        )


@dataclass(slots=True)
class AppConfig:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    csv: CsvConfig = field(default_factory=CsvConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            provider=ProviderConfig.from_dict(data.get("provider", {})),
            generation=GenerationConfig.from_dict(data.get("generation", {})),
            csv=CsvConfig.from_dict(data.get("csv", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": {
                "active": self.provider.active,
                "ollama": asdict(self.provider.ollama),
                "openai": asdict(self.provider.openai),
            },
            "generation": asdict(self.generation),
            "csv": self.csv.to_dict(),
        }


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        base_dir = Path(user_config_dir("product-description-tool", "Codex"))
        self.path = path or base_dir / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(config.to_dict(), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
