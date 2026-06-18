from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from product_description_tool.config import AppConfig
from product_description_tool.kb_conversion import ConversionFailedError, MarkItDownUnavailableError
from product_description_tool.project import PromptAttachment
from product_description_tool.kb_conversion import KnowledgeBaseContentService
from product_description_tool.prompt_renderer import (
    KB_REF_PREFIX,
    PromptRenderer,
)
from product_description_tool.providers import ProviderClient, build_provider

USER_PROMPT = (
    "Generate the final rewritten product description for this row and return only "
    "the description body as an HTML fragment. Do not include Markdown fences or "
    "any explanatory text."
)

ATTACHMENT_HEADER_TEMPLATE = "\n\n--- Attachment: {provenance} ---\n{content}\n--- End attachment ---"


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
        self._active_provider: ProviderClient | None = None
        self._active_provider_lock = threading.Lock()

    def cancel(self) -> None:
        with self._active_provider_lock:
            provider = self._active_provider
        if provider is not None:
            provider.cancel()

    def _set_active_provider(self, provider: ProviderClient | None) -> None:
        with self._active_provider_lock:
            self._active_provider = provider

    def validate_template(self, template: str, headers: list[str], knowledge_base_dir: str | Path | None = None) -> None:
        self.prompt_renderer.validate(template, headers, knowledge_base_dir)

    @staticmethod
    def validate_attachments(
        attachments: list[PromptAttachment],
        headers: list[str],
        knowledge_base_dir: str | Path | None = None,
    ) -> None:
        """Validate attachment sources.

        Raises ``ValueError`` with a descriptive message on the first invalid
        attachment.  Checks:
          - CSV column attachments reference an existing header.
          - KB file attachments resolve to an existing supported file under
            the configured knowledge-base directory.
        """
        if knowledge_base_dir is not None:
            kb_path = Path(knowledge_base_dir).resolve()
        else:
            kb_path = None

        header_set = set(headers)

        for idx, att in enumerate(attachments):
            if att.source_type == "csv_column":
                if att.source not in header_set:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): column not found "
                        f"in current document headers."
                    )
            elif att.source_type == "kb_file":
                if kb_path is None:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): "
                        "knowledge-base file attachment requires a configured "
                        "knowledge-base directory."
                    )
                candidate = (kb_path / att.source).resolve()
                try:
                    candidate.relative_to(kb_path)
                except ValueError:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): "
                        "path escapes knowledge-base directory."
                    ) from None
                if not candidate.exists():
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): file not found."
                    )
                if not candidate.is_file():
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): not a file."
                    )
                svc = KnowledgeBaseContentService()
                err_msg = svc.validate_supported(candidate)
                if err_msg is not None:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): {err_msg}"
                    )
                try:
                    svc.load_markdown(candidate, kb_path)
                except MarkItDownUnavailableError as exc:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): {exc}"
                    ) from exc
                except ConversionFailedError as exc:
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): {exc}"
                    ) from exc
                except (OSError, PermissionError):
                    raise ValueError(
                        f"Attachment #{idx + 1} ('{att.source}'): file is not readable."
                    ) from None
            else:
                raise ValueError(
                    f"Attachment #{idx + 1}: unknown source type "
                    f"'{att.source_type}'."
                )

    @staticmethod
    def build_effective_prompt(
        *,
        rendered_template: str,
        attachments: list[PromptAttachment],
        row: dict[str, str],
        knowledge_base_dir: str | Path | None = None,
    ) -> str:
        """Append attachment content to a rendered prompt with provenance.

        Each attachment is appended after a clear header/separator that
        identifies its type and source.
        """
        if not attachments:
            return rendered_template

        kb_path: Path | None = None
        if knowledge_base_dir is not None:
            kb_path = Path(knowledge_base_dir).resolve()

        parts = [rendered_template]

        for att in attachments:
            if att.source_type == "csv_column":
                value = row.get(att.source, "")
                provenance = f"column '{att.source}'"
                parts.append(ATTACHMENT_HEADER_TEMPLATE.format(
                    provenance=provenance, content=value,
                ))
            elif att.source_type == "kb_file":
                provenance = f"knowledge-base file '{att.source}'"
                content = ""
                if kb_path is not None:
                    candidate = (kb_path / att.source).resolve()
                    try:
                        candidate.relative_to(kb_path)
                        svc = KnowledgeBaseContentService()
                        content = svc.load_markdown(candidate, kb_path)
                    except (OSError, PermissionError, ValueError):
                        content = ""
                parts.append(ATTACHMENT_HEADER_TEMPLATE.format(
                    provenance=provenance, content=content,
                ))

        return "".join(parts)

    def prepare_prompt(
        self,
        *,
        template: str,
        row: dict[str, str],
        knowledge_base_dir: str | Path | None = None,
        attachments: list[PromptAttachment] | None = None,
    ) -> PromptPayload:
        rendered = self.prompt_renderer.render(template, row, knowledge_base_dir)
        if attachments:
            rendered = self.build_effective_prompt(
                rendered_template=rendered,
                attachments=attachments,
                row=row,
                knowledge_base_dir=knowledge_base_dir,
            )
        return PromptPayload(
            system_prompt=rendered,
            user_prompt=USER_PROMPT,
        )

    def process_row(
        self,
        *,
        row_index: int,
        row: dict[str, str],
        template: str,
        config: AppConfig,
        knowledge_base_dir: str | Path | None = None,
        attachments: list[PromptAttachment] | None = None,
        on_prompt_ready: Callable[[int, PromptPayload], None] | None = None,
        on_chunk: Callable[[int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        provider = self.provider_factory(config)
        self._set_active_provider(provider)
        try:
            prompt = self.prepare_prompt(
                template=template,
                row=row,
                knowledge_base_dir=knowledge_base_dir,
                attachments=attachments,
            )
            if on_prompt_ready is not None:
                on_prompt_ready(row_index, prompt)
            content = provider.generate(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
                temperature=config.generation.temperature,
                top_p=config.generation.top_p,
                max_output_tokens=config.generation.max_output_tokens,
                enable_thinking=config.generation.enable_thinking,
                on_chunk=(lambda chunk: on_chunk(row_index, chunk)) if on_chunk is not None else None,
                should_cancel=should_cancel,
            )
        finally:
            self._set_active_provider(None)
        return GenerationResult(row_index=row_index, content=content)

    def process_rows(
        self,
        *,
        rows: list[dict[str, str]],
        template: str,
        config: AppConfig,
        knowledge_base_dir: str | Path | None = None,
        attachments: list[PromptAttachment] | None = None,
        on_result: Callable[[GenerationResult], None] | None = None,
        on_prompt_ready: Callable[[int, PromptPayload], None] | None = None,
        on_chunk: Callable[[int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[GenerationResult]:
        provider = self.provider_factory(config)
        self._set_active_provider(provider)
        try:
            results: list[GenerationResult] = []
            for row_index, row in enumerate(rows):
                if should_cancel is not None and should_cancel():
                    break
                prompt = self.prepare_prompt(
                    template=template,
                    row=row,
                    knowledge_base_dir=knowledge_base_dir,
                    attachments=attachments,
                )
                if on_prompt_ready is not None:
                    on_prompt_ready(row_index, prompt)
                result = GenerationResult(
                    row_index=row_index,
                    content=provider.generate(
                        system_prompt=prompt.system_prompt,
                        user_prompt=prompt.user_prompt,
                        temperature=config.generation.temperature,
                        top_p=config.generation.top_p,
                        max_output_tokens=config.generation.max_output_tokens,
                        enable_thinking=config.generation.enable_thinking,
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
        finally:
            self._set_active_provider(None)
        return results
