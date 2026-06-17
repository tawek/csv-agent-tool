from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Sequence

PLACEHOLDER_PATTERN = re.compile(r"{{\s*(.+?)\s*}}")

from product_description_tool.kb_conversion import (
    ALL_KB_EXTENSIONS,
    CONVERTIBLE_EXTENSIONS,
    KnowledgeBaseContentService,
)

KB_REF_PREFIX = "@"
# All KB-supported extensions: direct-read and convertible types.
SUPPORTED_KB_EXTENSIONS = ALL_KB_EXTENSIONS


class CycleError(Exception):
    """Raised when a cycle is detected in the prompt dependency graph."""
    def __init__(self, cycle_prompts: list[str], cycle_edges: list[tuple[str, str]]) -> None:
        self.cycle_prompts = cycle_prompts
        self.cycle_edges = cycle_edges
        if cycle_prompts:
            prompt_names = ", ".join(f"'{p}'" for p in cycle_prompts)
            message = f"Cyclic dependency detected among: {prompt_names}"
        else:
            message = "Cyclic dependency detected among prompts"
        super().__init__(message)


class PromptTemplateError(ValueError):
    def __init__(self, missing_fields: list[str]) -> None:
        message = "Unknown placeholders: " + ", ".join(sorted(missing_fields))
        super().__init__(message)
        self.missing_fields = sorted(missing_fields)


class KnowledgeBaseRefError(ValueError):
    """Raised when knowledge-base references cannot be resolved."""
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        message = "Knowledge-base reference errors:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class PromptRenderer:
    @staticmethod
    def extract_placeholders(template: str) -> list[str]:
        placeholders = []
        seen: set[str] = set()
        for match in PLACEHOLDER_PATTERN.finditer(template):
            name = match.group(1)
            if name not in seen:
                placeholders.append(name)
                seen.add(name)
        return placeholders

    @staticmethod
    def extract_kb_references(template: str) -> list[str]:
        """Extract knowledge-base file references (``{{@...}}``) from the template.

        Returns the file paths (without the ``@`` prefix) in order of appearance.
        """
        refs: list[str] = []
        seen: set[str] = set()
        for match in PLACEHOLDER_PATTERN.finditer(template):
            name = match.group(1)
            if name.startswith("@") and name not in seen:
                refs.append(name[1:])
                seen.add(name)
        return refs

    @staticmethod
    def is_kb_placeholder(name: str) -> bool:
        return name.startswith(KB_REF_PREFIX)

    @staticmethod
    def extract_kb_placeholders(template: str) -> list[str]:
        return [ph for ph in PromptRenderer.extract_placeholders(template) if ph.startswith(KB_REF_PREFIX)]

    @staticmethod
    def extract_field_placeholders(template: str) -> list[str]:
        return [ph for ph in PromptRenderer.extract_placeholders(template) if not ph.startswith(KB_REF_PREFIX)]

    def validate(self, template: str, available_fields: list[str], knowledge_base_dir: str | Path | None = None) -> None:
        all_placeholders = self.extract_placeholders(template)
        field_phs = [ph for ph in all_placeholders if not ph.startswith(KB_REF_PREFIX)]
        kb_phs = [ph for ph in all_placeholders if ph.startswith(KB_REF_PREFIX)]

        # Validate field placeholders
        available = set(available_fields)
        missing = [ph for ph in field_phs if ph not in available]
        if missing:
            raise PromptTemplateError(missing)

        # Validate KB refs
        if kb_phs:
            self._validate_kb_refs(kb_phs, knowledge_base_dir)

    @staticmethod
    def _validate_kb_refs(refs: list[str], kb_dir: str | Path | None) -> None:
        errors: list[str] = []
        if kb_dir is None:
            errors.append("No knowledge-base directory configured")
            raise KnowledgeBaseRefError(errors)

        kb_path = Path(kb_dir).resolve()
        for ref in refs:
            ref_path_str = ref[len(KB_REF_PREFIX):]  # strip @ prefix
            placeholder = f"{{@{ref_path_str}}}"

            # Check for path traversal (must not escape KB directory)
            candidate = (kb_path / ref_path_str).resolve()
            try:
                candidate.relative_to(kb_path)
            except ValueError:
                errors.append(f"{placeholder}: path escapes knowledge-base directory")
                continue

            # Check file exists
            if not candidate.exists():
                errors.append(f"{placeholder}: file not found")
                continue

            # Check it is a file (not a directory)
            if not candidate.is_file():
                errors.append(f"{placeholder}: not a file")
                continue

            # Check supported extension
            if candidate.suffix.lower() not in SUPPORTED_KB_EXTENSIONS:
                supported = ", ".join(sorted(SUPPORTED_KB_EXTENSIONS))
                errors.append(
                    f"{placeholder}: unsupported file type '{candidate.suffix}' "
                    f"(supported: {supported})"
                )
                continue

            # For convertible file types, validate the conversion path
            if candidate.suffix.lower() in CONVERTIBLE_EXTENSIONS:
                svc = KnowledgeBaseContentService()
                err_msg = svc.validate_supported(candidate)
                if err_msg is not None:
                    errors.append(f"{placeholder}: {err_msg}")
                    continue

            # Check readable (direct-read files only; convertible files
            # are validated by the conversion service at load time)
            if candidate.suffix.lower() not in CONVERTIBLE_EXTENSIONS:
                try:
                    candidate.read_bytes()
                except (OSError, PermissionError):
                    errors.append(f"{placeholder}: file is not readable")
                    continue

        if errors:
            raise KnowledgeBaseRefError(errors)

    def render(self, template: str, row: dict[str, str], knowledge_base_dir: str | Path | None = None) -> str:
        self.validate(template, list(row.keys()), knowledge_base_dir)

        kb_path: Path | None = None
        if knowledge_base_dir is not None:
            kb_path = Path(knowledge_base_dir).resolve()

        content_svc = KnowledgeBaseContentService()

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name.startswith(KB_REF_PREFIX):
                if kb_path is None:
                    return ""
                ref_path = name[len(KB_REF_PREFIX):]
                resolved = (kb_path / ref_path).resolve()
                try:
                    suffix = resolved.suffix.lower()
                    if suffix in CONVERTIBLE_EXTENSIONS:
                        return content_svc.load_markdown(resolved, kb_path)
                    return resolved.read_text(encoding="utf-8")
                except (OSError, PermissionError, ValueError):
                    return ""
            return row.get(name, "")

        return PLACEHOLDER_PATTERN.sub(replace, template)

    @staticmethod
    def compute_prompt_order(prompts: Sequence["ProjectPrompt"]) -> list["ProjectPrompt"]:
        """Return prompts in topological order based on output-field dependencies.

        Knowledge-base file references (``{{@...}}``) are excluded from the
        dependency graph and never create dependency edges.

        Raises ``CycleError`` when a cycle is detected, carrying the prompts
        involved in the cycle and the dependency edges that form it.
        """
        from product_description_tool.project import ProjectPrompt as _pp  # local import to avoid circular

        # Build name -> prompt mapping
        prompt_map: dict[str, "ProjectPrompt"] = {}
        for p in prompts:
            if p.output_field:
                prompt_map[p.output_field] = p

        # Build dependency map: output_field -> set of output_fields it depends on
        deps: dict[str, set[str]] = {}
        edges: list[tuple[str, str]] = []  # (dependent, dependency)

        for p in prompts:
            name = p.output_field
            placeholders = PromptRenderer.extract_placeholders(p.prompt)
            dep_set: set[str] = set()
            for ph in placeholders:
                # KB refs do not create prompt dependencies
                if ph.startswith(KB_REF_PREFIX):
                    continue
                if ph in prompt_map and ph != name:
                    dep_set.add(ph)
                    edges.append((name, ph))
            deps[name] = dep_set

        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = {name: len(dep_set) for name, dep_set in deps.items()}
        queue: deque[str] = deque(sorted(name for name, deg in in_degree.items() if deg == 0))
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)
            for name, dep_set in deps.items():
                if current in dep_set:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
            queue = deque(sorted(queue))  # maintain deterministic ordering

        if len(ordered) != len(deps):
            # Cycle detected - find remaining nodes
            remaining = set(deps.keys()) - set(ordered)
            cycle_edges = [e for e in edges if e[0] in remaining and e[1] in remaining]
            raise CycleError(sorted(remaining), cycle_edges)

        return [prompt_map[name] for name in ordered]
