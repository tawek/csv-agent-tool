from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from product_description_tool.config import AppConfig
from product_description_tool.prompt_renderer import PromptRenderer
from product_description_tool.providers import ProviderClient, build_provider

USER_PROMPT = (
    "Generate the final rewritten product description for this row and return only "
    "the description body as an HTML fragment. Do not include Markdown fences or "
    "any explanatory text."
)


@dataclass(slots=True)
class GenerationResult:
    row_index: int
    content: str


class GenerationService:
    def __init__(
        self,
        *,
        prompt_renderer: PromptRenderer | None = None,
        provider_factory: Callable[[AppConfig], ProviderClient] = build_provider,
    ) -> None:
        self.prompt_renderer = prompt_renderer or PromptRenderer()
        self.provider_factory = provider_factory

    def validate_template(self, template: str, headers: list[str]) -> None:
        self.prompt_renderer.validate(template, headers)

    def process_row(
        self,
        *,
        row_index: int,
        row: dict[str, str],
        template: str,
        config: AppConfig,
    ) -> GenerationResult:
        provider = self.provider_factory(config)
        system_prompt = self.prompt_renderer.render(template, row)
        content = provider.generate(
            system_prompt=system_prompt,
            user_prompt=USER_PROMPT,
            temperature=config.generation.temperature,
            top_p=config.generation.top_p,
            max_output_tokens=config.generation.max_output_tokens,
        )
        return GenerationResult(row_index=row_index, content=content)

    def process_rows(
        self,
        *,
        rows: list[dict[str, str]],
        template: str,
        config: AppConfig,
        on_result: Callable[[GenerationResult], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[GenerationResult]:
        provider = self.provider_factory(config)
        results: list[GenerationResult] = []
        for row_index, row in enumerate(rows):
            if should_cancel is not None and should_cancel():
                break
            system_prompt = self.prompt_renderer.render(template, row)
            result = GenerationResult(
                row_index=row_index,
                content=provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=USER_PROMPT,
                    temperature=config.generation.temperature,
                    top_p=config.generation.top_p,
                    max_output_tokens=config.generation.max_output_tokens,
                ),
            )
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results
