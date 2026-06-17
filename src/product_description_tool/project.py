from __future__ import annotations

import json
import os
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
    knowledge_base_dir: str | None = None

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
            knowledge_base_dir=data.get("knowledge-base-dir"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "prompts": [prompt.to_dict() for prompt in self.prompts],
            "csv": self.csv.to_dict(),
        }
        if self.knowledge_base_dir is not None:
            result["knowledge-base-dir"] = self.knowledge_base_dir
        return result


def normalize_project_path(path: str | Path) -> Path:
    project_path = Path(path)
    if project_path.name.endswith(PROJECT_SUFFIX):
        return project_path
    return project_path.with_name(f"{project_path.stem}{PROJECT_SUFFIX}")


def project_csv_path(path: str | Path) -> Path:
    project_path = normalize_project_path(path)
    base_name = project_path.name[: -len(PROJECT_SUFFIX)]
    return project_path.with_name(f"{base_name}.csv")


def _make_kb_relative(kb_directory: str, project_dir: Path) -> str:
    """Convert a KB directory path to relative form if under *project_dir*.

    If *kb_directory* is already relative it is returned unchanged.
    If it is absolute and under *project_dir* a relative form is returned.
    Otherwise the absolute path is returned as-is.
    """
    kb_path = Path(kb_directory)
    if not kb_path.is_absolute():
        return kb_directory  # already relative
    try:
        rel = os.path.relpath(kb_path, project_dir)
        # Only store as relative if it doesn't escape the project directory
        if not rel.startswith(".."):
            return rel
    except ValueError:
        pass
    return str(kb_path)


def _prompt_filename(output_field: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", output_field).strip("._") or "prompt"
    return f"{sanitized}.prompt.txt"


class ProjectRepository:
    def load(self, path: str | Path) -> Project:
        project_path = normalize_project_path(path)
        data = json.loads(project_path.read_text(encoding="utf-8"))
        project = Project.from_dict(data)
        # Resolve KB directory relative to the project file location
        if project.knowledge_base_dir is not None:
            kb_path = Path(project.knowledge_base_dir)
            if not kb_path.is_absolute():
                kb_path = (project_path.parent / kb_path).resolve()
            project.knowledge_base_dir = str(kb_path)
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
        # Serialize project with KB directory as relative path when possible
        data = project.to_dict()
        if project.knowledge_base_dir is not None:
            data["knowledge-base-dir"] = _make_kb_relative(
                project.knowledge_base_dir, project_path.parent
            )
        project_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return project_path

    def csv_path_for(self, path: str | Path) -> Path:
        return project_csv_path(path)
