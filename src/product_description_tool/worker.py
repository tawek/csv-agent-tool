from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from product_description_tool.config import AppConfig
from product_description_tool.generation import GenerationResult, GenerationService
from product_description_tool.providers import GenerationCancelled


class GenerationWorker(QObject):
    row_generated = Signal(int, str)
    chunk_generated = Signal(int, str)
    completed = Signal()
    failed = Signal(str)
    progress = Signal(int, int)
    cancelled = Signal()

    def __init__(
        self,
        *,
        service: GenerationService,
        rows: list[dict[str, str]],
        template: str,
        config: AppConfig,
        selected_row: int | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.rows = rows
        self.template = template
        self.config = config
        self.selected_row = selected_row
        self._cancel_requested = threading.Event()

    def cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        total = 1 if self.selected_row is not None else len(self.rows)
        try:
            self.progress.emit(0, total)
            if self.selected_row is None:
                self.service.process_rows(
                    rows=self.rows,
                    template=self.template,
                    config=self.config,
                    on_result=self._emit_result,
                    on_chunk=self._emit_chunk,
                    should_cancel=self._cancel_requested.is_set,
                )
                if self._cancel_requested.is_set():
                    self.cancelled.emit()
                    return
            else:
                result = self.service.process_row(
                    row_index=self.selected_row,
                    row=self.rows[self.selected_row],
                    template=self.template,
                    config=self.config,
                    on_chunk=self._emit_chunk,
                    should_cancel=self._cancel_requested.is_set,
                )
                self._emit_result(result)
        except GenerationCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.completed.emit()

    def _emit_chunk(self, row_index: int, chunk: str) -> None:
        self.chunk_generated.emit(row_index, chunk)

    def _emit_result(self, result: GenerationResult) -> None:
        self.row_generated.emit(result.row_index, result.content)
        if self.selected_row is None:
            self.progress.emit(result.row_index + 1, len(self.rows))
            return
        self.progress.emit(1, 1)
