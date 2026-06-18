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
    strip_html_whitespace: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldConfig":
        return cls(
            label=data.get("label"),
            show=bool(data.get("show", True)),
            strip_html_whitespace=bool(data.get("strip_html_whitespace", False)),
        )


@dataclass(slots=True)
class CsvReadSettings:
    """Low-level parsing settings for CSV import/open.

    These are the settings established by auto-detection or fallback defaults
    and are used when reading CSV data into memory.
    """
    delimiter: str = ";"
    quotechar: str = '"'
    encoding: str = "utf-8-sig"
    newline: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CsvReadSettings":
        return cls(
            delimiter=data.get("delimiter", ";") or ";",
            quotechar=data.get("quotechar", '"') or '"',
            encoding=data.get("encoding", "utf-8-sig"),
            newline=data.get("newline", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "encoding": self.encoding,
            "newline": self.newline,
        }


@dataclass(slots=True)
class CsvWriteSettings:
    """Export-oriented CSV settings for project save and explicit export.

    Includes all low-level parsing attributes plus export metadata such as
    column order, header writing, field labels/visibility, and export path.
    """
    delimiter: str = ";"
    quotechar: str = '"'
    encoding: str = "utf-8-sig"
    newline: str = ""
    write_header: bool = True
    export_path: str = ""
    export_only_visible: bool = True
    export_order: list[str] = field(default_factory=list)
    fields: dict[str, FieldConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CsvWriteSettings":
        fields = {
            key: FieldConfig.from_dict(value)
            for key, value in data.get("fields", {}).items()
        }
        return cls(
            delimiter=data.get("delimiter", ";") or ";",
            quotechar=data.get("quotechar", '"') or '"',
            encoding=data.get("encoding", "utf-8-sig"),
            newline=data.get("newline", ""),
            write_header=bool(data.get("write_header", True)),
            export_path=data.get("export-path", ""),
            export_only_visible=bool(data.get("export-only-visible", True)),
            export_order=list(data.get("export-order", [])),
            fields=fields,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "encoding": self.encoding,
            "newline": self.newline,
            "write_header": self.write_header,
            "export-path": self.export_path,
            "export-only-visible": self.export_only_visible,
            "export-order": self.export_order,
            "fields": {
                key: asdict(value)
                for key, value in self.fields.items()
            },
        }


@dataclass
class CsvConfig:
    """Container for separated import and export CSV settings.

    Backward-compatible properties on this class delegate to ``export_settings``
    so existing code that accesses ``csv.delimiter``, ``csv.fields`` etc. still
    works without changes.
    """
    import_settings: CsvReadSettings = field(default_factory=CsvReadSettings)
    export_settings: CsvWriteSettings = field(default_factory=CsvWriteSettings)
    export_settings_initialized: bool = False

    # -- Backward-compatible forwarding properties ---------------------------

    @property
    def delimiter(self) -> str:
        return self.export_settings.delimiter

    @delimiter.setter
    def delimiter(self, value: str) -> None:
        self.export_settings.delimiter = value

    @property
    def quotechar(self) -> str:
        return self.export_settings.quotechar

    @quotechar.setter
    def quotechar(self, value: str) -> None:
        self.export_settings.quotechar = value

    @property
    def encoding(self) -> str:
        return self.export_settings.encoding

    @encoding.setter
    def encoding(self, value: str) -> None:
        self.export_settings.encoding = value

    @property
    def newline(self) -> str:
        return self.export_settings.newline

    @newline.setter
    def newline(self, value: str) -> None:
        self.export_settings.newline = value

    @property
    def write_header(self) -> bool:
        return self.export_settings.write_header

    @write_header.setter
    def write_header(self, value: bool) -> None:
        self.export_settings.write_header = value

    @property
    def export_path(self) -> str:
        return self.export_settings.export_path

    @export_path.setter
    def export_path(self, value: str) -> None:
        self.export_settings.export_path = value

    @property
    def export_only_visible(self) -> bool:
        return self.export_settings.export_only_visible

    @export_only_visible.setter
    def export_only_visible(self, value: bool) -> None:
        self.export_settings.export_only_visible = value

    @property
    def export_order(self) -> list[str]:
        return self.export_settings.export_order

    @export_order.setter
    def export_order(self, value: list[str]) -> None:
        self.export_settings.export_order = value

    @property
    def fields(self) -> dict[str, FieldConfig]:
        return self.export_settings.fields

    @fields.setter
    def fields(self, value: dict[str, FieldConfig]) -> None:
        self.export_settings.fields = value

    # -- Serialisation -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CsvConfig":
        # Detect new-style vs legacy flat structure.
        if "import_settings" in data or "export_settings" in data:
            return cls(
                import_settings=CsvReadSettings.from_dict(data.get("import_settings", {})),
                export_settings=CsvWriteSettings.from_dict(data.get("export_settings", {})),
                export_settings_initialized=bool(data.get("export_settings_initialized", False)),
            )
        # Legacy flat data — treated as export-oriented with both import and
        # export populated from the same flat values, and export marked as
        # initialised (legacy data always had concrete values).
        return cls(
            import_settings=CsvReadSettings.from_dict(data),
            export_settings=CsvWriteSettings.from_dict(data),
            export_settings_initialized=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_settings": self.import_settings.to_dict(),
            "export_settings": self.export_settings.to_dict(),
            "export_settings_initialized": self.export_settings_initialized,
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
    enable_thinking: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationConfig":
        return cls(
            temperature=float(data.get("temperature", 0.2)),
            top_p=float(data.get("top_p", 1.0)),
            max_output_tokens=int(data.get("max_output_tokens", 500)),
            enable_thinking=bool(data.get("enable_thinking", False)),
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
        persisted = {
            "provider": {
                "active": config.provider.active,
                "ollama": asdict(config.provider.ollama),
                "openai": asdict(config.provider.openai),
            },
            "generation": asdict(config.generation),
            "csv": config.csv.to_dict(),
        }
        self.path.write_text(
            json.dumps(persisted, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )


MAX_RECENT = 10


class RecentProjectsStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path
        else:
            base_dir = Path(user_config_dir("product-description-tool", "Codex"))
            self.path = base_dir / "recent.json"

    def load(self) -> list[Path]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [Path(p).resolve() for p in data.get("recent", [])]
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, paths: list[Path]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"recent": [str(p.resolve()) for p in paths]},
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

    def add(self, path: Path) -> None:
        resolved = path.resolve()
        paths = self.load()
        paths = [p for p in paths if p.resolve() != resolved]
        paths.insert(0, resolved)
        self.save(paths[:MAX_RECENT])

    def remove(self, path: Path) -> None:
        resolved = path.resolve()
        paths = self.load()
        paths = [p for p in paths if p.resolve() != resolved]
        self.save(paths)

    def clear(self) -> None:
        self.save([])
