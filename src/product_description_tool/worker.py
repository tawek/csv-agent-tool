from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from product_description_tool.config import AppConfig
from product_description_tool.generation import GenerationResult, GenerationService


class GenerationWorker(QObject):
    row_generated = Signal(int, str)
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
        try:
            if self.selected_row is None:
                total = len(self.rows)
                self.progress.emit(0, total)
                self.service.process_rows(
                    rows=self.rows,
                    template=self.template,
                    config=self.config,
                    on_result=self._emit_result,
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
                )
                self._emit_result(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.completed.emit()

    def _emit_result(self, result: GenerationResult) -> None:
        self.row_generated.emit(result.row_index, result.content)
        if self.selected_row is None:
            self.progress.emit(result.row_index + 1, len(self.rows))
