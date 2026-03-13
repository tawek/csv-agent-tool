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


@dataclass(slots=True)
class PromptPayload:
    system_prompt: str
    user_prompt: str

    @property
    def input_char_count(self) -> int:
        return len(self.system_prompt) + len(self.user_prompt)


def estimate_tokens_from_chars(char_count: int) -> int:
    return round(char_count / 3.5)


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

    def prepare_prompt(self, *, template: str, row: dict[str, str]) -> PromptPayload:
        return PromptPayload(
            system_prompt=self.prompt_renderer.render(template, row),
            user_prompt=USER_PROMPT,
        )

    def process_row(
        self,
        *,
        row_index: int,
        row: dict[str, str],
        template: str,
        config: AppConfig,
        on_chunk: Callable[[int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        provider = self.provider_factory(config)
        prompt = self.prepare_prompt(template=template, row=row)
        content = provider.generate(
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            temperature=config.generation.temperature,
            top_p=config.generation.top_p,
            max_output_tokens=config.generation.max_output_tokens,
            on_chunk=(lambda chunk: on_chunk(row_index, chunk)) if on_chunk is not None else None,
            should_cancel=should_cancel,
        )
        return GenerationResult(row_index=row_index, content=content)

    def process_rows(
        self,
        *,
        rows: list[dict[str, str]],
        template: str,
        config: AppConfig,
        on_result: Callable[[GenerationResult], None] | None = None,
        on_chunk: Callable[[int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[GenerationResult]:
        provider = self.provider_factory(config)
        results: list[GenerationResult] = []
        for row_index, row in enumerate(rows):
            if should_cancel is not None and should_cancel():
                break
            prompt = self.prepare_prompt(template=template, row=row)
            result = GenerationResult(
                row_index=row_index,
                content=provider.generate(
                    system_prompt=prompt.system_prompt,
                    user_prompt=prompt.user_prompt,
                    temperature=config.generation.temperature,
                    top_p=config.generation.top_p,
                    max_output_tokens=config.generation.max_output_tokens,
                    on_chunk=(
                        (lambda chunk, current_index=row_index: on_chunk(current_index, chunk))
                        if on_chunk is not None
                        else None
                    ),
                    should_cancel=should_cancel,
                ),
            )
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results
