from __future__ import annotations

import re
from collections import deque
from typing import Sequence

PLACEHOLDER_PATTERN = re.compile(r"{{\s*(.+?)\s*}}")


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

    def validate(self, template: str, available_fields: list[str]) -> None:
        available = set(available_fields)
        missing = [
            placeholder
            for placeholder in self.extract_placeholders(template)
            if placeholder not in available
        ]
        if missing:
            raise PromptTemplateError(missing)

    def render(self, template: str, row: dict[str, str]) -> str:
        self.validate(template, list(row.keys()))

        def replace(match: re.Match[str]) -> str:
            return row.get(match.group(1), "")

        return PLACEHOLDER_PATTERN.sub(replace, template)

    @staticmethod
    def compute_prompt_order(prompts: Sequence["ProjectPrompt"]) -> list["ProjectPrompt"]:
        """Return prompts in topological order based on output-field dependencies.

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
