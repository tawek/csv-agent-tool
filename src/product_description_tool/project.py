from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from product_description_tool.config import CsvConfig

PROJECT_SUFFIX = ".project.json"


@dataclass(slots=True)
class ProjectPrompt:
    output_field: str
    prompt: str = ""
    enabled: bool = True
    prompt_file: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectPrompt":
        return cls(
            output_field=data.get("output-field", "").strip(),
            prompt=data.get("prompt", ""),
            enabled=bool(data.get("enabled", True)),
            prompt_file=data.get("prompt-file"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "output-field": self.output_field,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }
        if self.prompt_file:
            payload["prompt-file"] = self.prompt_file
        return payload


@dataclass(slots=True)
class Project:
    prompts: list[ProjectPrompt] = field(default_factory=list)
    csv: CsvConfig = field(default_factory=CsvConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            prompts=[
                prompt
                for prompt in (
                    ProjectPrompt.from_dict(item) for item in data.get("prompts", [])
                )
                if prompt.output_field
            ],
            csv=CsvConfig.from_dict(data.get("csv", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompts": [prompt.to_dict() for prompt in self.prompts],
            "csv": self.csv.to_dict(),
        }


def normalize_project_path(path: str | Path) -> Path:
    project_path = Path(path)
    if project_path.name.endswith(PROJECT_SUFFIX):
        return project_path
    return project_path.with_name(f"{project_path.stem}{PROJECT_SUFFIX}")


def project_csv_path(path: str | Path) -> Path:
    project_path = normalize_project_path(path)
    base_name = project_path.name[: -len(PROJECT_SUFFIX)]
    return project_path.with_name(f"{base_name}.csv")


def _prompt_filename(output_field: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", output_field).strip("._") or "prompt"
    return f"{sanitized}.prompt.txt"


class ProjectRepository:
    def load(self, path: str | Path) -> Project:
        project_path = normalize_project_path(path)
        data = json.loads(project_path.read_text(encoding="utf-8"))
        project = Project.from_dict(data)
        for prompt in project.prompts:
            if not prompt.prompt_file:
                continue
            prompt_path = project_path.parent / prompt.prompt_file
            if prompt_path.exists():
                prompt.prompt = prompt_path.read_text(encoding="utf-8")
        return project

    def save(self, path: str | Path, project: Project) -> Path:
        project_path = normalize_project_path(path)
        project_path.parent.mkdir(parents=True, exist_ok=True)
        for prompt in project.prompts:
            prompt.prompt_file = prompt.prompt_file or _prompt_filename(prompt.output_field)
            (project_path.parent / prompt.prompt_file).write_text(prompt.prompt, encoding="utf-8")
        project_path.write_text(
            json.dumps(project.to_dict(), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return project_path

    def csv_path_for(self, path: str | Path) -> Path:
        return project_csv_path(path)
