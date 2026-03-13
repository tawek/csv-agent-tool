from __future__ import annotations

import re

PLACEHOLDER_PATTERN = re.compile(r"{{\s*(.+?)\s*}}")


class PromptTemplateError(ValueError):
    def __init__(self, missing_fields: list[str]) -> None:
        message = "Unknown placeholders: " + ", ".join(sorted(missing_fields))
        super().__init__(message)
        self.missing_fields = sorted(missing_fields)


class PromptRenderer:
    def extract_placeholders(self, template: str) -> list[str]:
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
