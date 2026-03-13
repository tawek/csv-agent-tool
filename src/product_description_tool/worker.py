from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from product_description_tool.config import AppConfig
from product_description_tool.generation import GenerationResult, GenerationService
from product_description_tool.project import ProjectPrompt
from product_description_tool.providers import GenerationCancelled


class GenerationWorker(QObject):
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
        rows: list[dict[str, str]],
        prompts: list[ProjectPrompt],
        config: AppConfig,
        selected_row: int | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.rows = rows
        self.prompts = prompts
        self.config = config
        self.selected_row = selected_row
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        total = self._total_operations()
        try:
            self.progress.emit(0, max(total, 1))
            if total == 0:
                self.completed.emit()
                return

            completed = [0]
            if self.selected_row is None:
                for prompt in self.prompts:
                    self.service.process_rows(
                        rows=self.rows,
                        template=prompt.prompt,
                        config=self.config,
                        on_result=(
                            lambda result, current_prompt=prompt: self._emit_result_with_progress(
                                current_prompt.output_field,
                                result,
                                completed,
                                total,
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
                    if self._cancel_requested.is_set():
                        self.cancelled.emit()
                        return
            else:
                row = self.rows[self.selected_row]
                for prompt in self.prompts:
                    result = self.service.process_row(
                        row_index=self.selected_row,
                        row=row,
                        template=prompt.prompt,
                        config=self.config,
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
                    if self._cancel_requested.is_set():
                        self.cancelled.emit()
                        return
        except GenerationCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.completed.emit()

    def _emit_chunk(self, row_index: int, output_field: str, chunk: str) -> None:
        self.chunk_generated.emit(row_index, output_field, chunk)

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
        row_count = 1 if self.selected_row is not None else len(self.rows)
        return row_count * len(self.prompts)
