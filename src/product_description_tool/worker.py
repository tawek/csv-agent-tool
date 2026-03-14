from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from product_description_tool.config import AppConfig
from product_description_tool.generation import GenerationResult, GenerationService
from product_description_tool.project import ProjectPrompt
from product_description_tool.providers import GenerationCancelled


class GenerationWorker(QObject):
    prompt_started = Signal(int, str, int)
    row_generated = Signal(int, str, str)
    chunk_generated = Signal(int, str, str)
    completed = Signal()
    failed = Signal(str)
    progress = Signal(int, int)
    cancelled = Signal()

    def __init__(
        self,
        *,
        service: GenerationService,
        row_specs: list[tuple[int, dict[str, str]]],
        prompts: list[ProjectPrompt],
        config: AppConfig,
    ) -> None:
        super().__init__()
        self.service = service
        self.row_specs = row_specs
        self.prompts = prompts
        self.config = config
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        self._cancel_requested.set()
        cancel = getattr(self.service, "cancel", None)
        if callable(cancel):
            cancel()

    def run(self) -> None:
        total = self._total_operations()
        try:
            self.progress.emit(0, max(total, 1))
            if total == 0:
                self.completed.emit()
                return

            completed = [0]
            for prompt in self.prompts:
                for row_index, row in self.row_specs:
                    if self._cancel_requested.is_set():
                        self.cancelled.emit()
                        return
                    result = self.service.process_row(
                        row_index=row_index,
                        row=row,
                        template=prompt.prompt,
                        config=self.config,
                        on_prompt_ready=(
                            lambda current_row_index, prompt_payload, current_prompt=prompt: (
                                self._emit_prompt_started(
                                    current_row_index,
                                    current_prompt.output_field,
                                    prompt_payload.input_char_count,
                                )
                            )
                        ),
                        on_chunk=(
                            lambda row_index, chunk, current_prompt=prompt: self._emit_chunk(
                                row_index,
                                current_prompt.output_field,
                                chunk,
                            )
                        ),
                        should_cancel=self._cancel_requested.is_set,
                    )
                    self._emit_result_with_progress(prompt.output_field, result, completed, total)
        except GenerationCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.completed.emit()

    def _emit_chunk(self, row_index: int, output_field: str, chunk: str) -> None:
        self.chunk_generated.emit(row_index, output_field, chunk)

    def _emit_prompt_started(self, row_index: int, output_field: str, input_chars: int) -> None:
        self.prompt_started.emit(row_index, output_field, input_chars)

    def _emit_result(self, output_field: str, result: GenerationResult) -> None:
        self.row_generated.emit(result.row_index, output_field, result.content)

    def _emit_result_with_progress(
        self,
        output_field: str,
        result: GenerationResult,
        completed: list[int],
        total: int,
    ) -> None:
        self._emit_result(output_field, result)
        completed[0] += 1
        self.progress.emit(completed[0], total)

    def _total_operations(self) -> int:
        return len(self.row_specs) * len(self.prompts)
