from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QPainter, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from product_description_tool.config import (
    AppConfig,
    CsvConfig,
    FieldConfig,
)
from product_description_tool.generation import estimate_tokens_from_chars
from product_description_tool.highlighter import HtmlSyntaxHighlighter


class SpinnerWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._advance)
        self._timer.start()
        self.setMinimumSize(28, 28)

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        side = min(self.width(), self.height())
        radius = side / 2 - 3
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.rect().center())
        base = self.palette().color(self.foregroundRole())
        for index in range(12):
            color = QColor(base)
            color.setAlphaF((index + 1) / 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.save()
            painter.rotate(self._angle - index * 30)
            painter.translate(0, -radius)
            painter.drawRoundedRect(-2, -4, 4, 8, 2, 2)
            painter.restore()


class ActivityDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(520, 260)

        self._elapsed_seconds = 0
        self._allow_close = False
        self._cancel_requested = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.spinner = SpinnerWidget()
        header.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignTop)

        title_column = QVBoxLayout()
        self.title_label = QLabel("Processing")
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.status_label = QLabel("Working...")
        title_column.addWidget(self.title_label)
        title_column.addWidget(self.status_label)
        header.addLayout(title_column, 1)

        elapsed_column = QVBoxLayout()
        elapsed_column.addWidget(QLabel("Elapsed"), alignment=Qt.AlignmentFlag.AlignRight)
        self.elapsed_label = QLabel("0:00:00")
        elapsed_font = self.elapsed_label.font()
        elapsed_font.setBold(True)
        self.elapsed_label.setFont(elapsed_font)
        elapsed_column.addWidget(self.elapsed_label, alignment=Qt.AlignmentFlag.AlignRight)
        header.addLayout(elapsed_column)
        layout.addLayout(header)

        self.record_label = QLabel("Records: 0 / 0")
        layout.addWidget(self.record_label)

        self.record_progress_bar = QProgressBar()
        self.record_progress_bar.setTextVisible(True)
        self.record_progress_bar.setRange(0, 1)
        self.record_progress_bar.setValue(0)
        layout.addWidget(self.record_progress_bar)

        self.input_stats_label = QLabel("Input prompt: 0 chars (~0 tokens)")
        self.output_stats_label = QLabel("Output: 0 chars (~0 tokens)")
        layout.addWidget(self.input_stats_label)
        layout.addWidget(self.output_stats_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.request_cancel)
        footer.addWidget(self.cancel_button)
        layout.addLayout(footer)

    def start_activity(
        self,
        *,
        title: str,
        status: str,
        total_records: int,
        input_chars: int,
    ) -> None:
        self._allow_close = False
        self._cancel_requested = False
        self._elapsed_seconds = 0
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.status_label.setText(status)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Cancel")
        self.elapsed_label.setText("0:00:00")
        self.set_record_progress(0, total_records)
        self.set_input_stats(input_chars)
        self.set_output_stats(0)
        self._timer.start()
        self.show()

    def set_record_progress(self, completed: int, total: int) -> None:
        total = max(total, 1)
        self.record_label.setText(f"Records: {completed} / {total}")
        self.record_progress_bar.setRange(0, total)
        self.record_progress_bar.setValue(min(completed, total))

    def set_input_stats(self, char_count: int) -> None:
        tokens = estimate_tokens_from_chars(char_count)
        self.input_stats_label.setText(f"Input prompt: {char_count:,} chars (~{tokens:,} tokens)")

    def set_output_stats(self, char_count: int) -> None:
        tokens = estimate_tokens_from_chars(char_count)
        self.output_stats_label.setText(f"Output: {char_count:,} chars (~{tokens:,} tokens)")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def request_cancel(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self.status_label.setText("Cancelling...")
        self.cancel_requested.emit()

    def close_activity(self) -> None:
        self._timer.stop()
        self._allow_close = True
        self.close()
        self.deleteLater()

    def reject(self) -> None:
        self.request_cancel()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close:
            event.ignore()
            self.request_cancel()
            return
        super().closeEvent(event)

    def _tick(self) -> None:
        self._elapsed_seconds += 1
        hours, remainder = divmod(self._elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_label.setText(f"{hours}:{minutes:02}:{seconds:02}")


class HtmlEditorDialog(QDialog):
    def __init__(self, *, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(text)
        self.highlighter = HtmlSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self.editor.toPlainText()


class FilterDialog(QDialog):
    def __init__(
        self,
        *,
        column_labels: list[tuple[str, str]],
        current_filters: dict[str, str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Filters")
        self.resize(700, 500)
        self._edits: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Use * as a wildcard. Filters affect the table view only."))

        form = QFormLayout()
        for key, label in column_labels:
            edit = QLineEdit(current_filters.get(key, ""))
            edit.setPlaceholderText("* wildcard")
            form.addRow(label, edit)
            self._edits[key] = edit
        layout.addLayout(form)

        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self._clear_all)
        layout.addWidget(clear_button, alignment=Qt.AlignmentFlag.AlignLeft)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_all(self) -> None:
        for edit in self._edits.values():
            edit.clear()

    def filters(self) -> dict[str, str]:
        return {
            key: edit.text().strip()
            for key, edit in self._edits.items()
            if edit.text().strip()
        }


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: AppConfig,
        *,
        current_headers: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(720, 640)
        self._config = AppConfig.from_dict(config.to_dict())
        self._current_headers = list(current_headers or [])

        root_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self._build_provider_tab()
        self._build_generation_tab()
        self._build_csv_tab()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _build_provider_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_form = QFormLayout()
        self.active_provider_combo = QComboBox()
        self.active_provider_combo.addItems(["ollama", "openai"])
        self.active_provider_combo.setCurrentText(self._config.provider.active)
        top_form.addRow("Active provider", self.active_provider_combo)
        layout.addLayout(top_form)

        provider_tabs = QTabWidget()
        layout.addWidget(provider_tabs)

        ollama_tab = QWidget()
        ollama_form = QFormLayout(ollama_tab)
        self.ollama_base_url_edit = QLineEdit(self._config.provider.ollama.base_url)
        self.ollama_model_edit = QLineEdit(self._config.provider.ollama.model)
        self.ollama_options_edit = QPlainTextEdit(
            json.dumps(self._config.provider.ollama.options, indent=2)
        )
        ollama_form.addRow("Base URL", self.ollama_base_url_edit)
        ollama_form.addRow("Model", self.ollama_model_edit)
        ollama_form.addRow("Options JSON", self.ollama_options_edit)
        provider_tabs.addTab(ollama_tab, "Ollama")

        openai_tab = QWidget()
        openai_form = QFormLayout(openai_tab)
        self.openai_base_url_edit = QLineEdit(self._config.provider.openai.base_url)
        self.openai_api_key_edit = QLineEdit(self._config.provider.openai.api_key)
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_edit = QLineEdit(self._config.provider.openai.model)
        self.openai_options_edit = QPlainTextEdit(
            json.dumps(self._config.provider.openai.options, indent=2)
        )
        openai_form.addRow("Base URL", self.openai_base_url_edit)
        openai_form.addRow("API key", self.openai_api_key_edit)
        openai_form.addRow("Model", self.openai_model_edit)
        openai_form.addRow("Options JSON", self.openai_options_edit)
        provider_tabs.addTab(openai_tab, "OpenAI-compatible")

        self.tabs.addTab(tab, "Provider")

    def _build_generation_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(self._config.generation.temperature)

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(self._config.generation.top_p)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 200000)
        self.max_tokens_spin.setValue(self._config.generation.max_output_tokens)

        layout.addRow("Temperature", self.temperature_spin)
        layout.addRow("Top P", self.top_p_spin)
        layout.addRow("Max output tokens", self.max_tokens_spin)
        self.tabs.addTab(tab, "Generation")

    def _build_csv_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.original_description_edit = QLineEdit(self._config.csv.original_description)
        self.delimiter_edit = QLineEdit(self._config.csv.delimiter)
        self.quotechar_edit = QLineEdit(self._config.csv.quotechar)
        self.encoding_edit = QLineEdit(self._config.csv.encoding)
        self.newline_edit = QLineEdit(self._config.csv.newline)
        self.write_header_checkbox = QCheckBox()
        self.write_header_checkbox.setChecked(self._config.csv.write_header)

        form.addRow("Original description column", self.original_description_edit)
        form.addRow("Delimiter", self.delimiter_edit)
        form.addRow("Quote char", self.quotechar_edit)
        form.addRow("Encoding", self.encoding_edit)
        form.addRow("Newline", self.newline_edit)
        form.addRow("Write header", self.write_header_checkbox)
        layout.addLayout(form)

        columns_row = QHBoxLayout()
        columns_row.addWidget(QLabel("Columns"))
        self.reset_columns_button = QPushButton("Reset From Current CSV")
        self.reset_columns_button.setEnabled(bool(self._current_headers))
        self.reset_columns_button.clicked.connect(self._reset_columns_from_current_csv)
        columns_row.addStretch(1)
        columns_row.addWidget(self.reset_columns_button)
        layout.addLayout(columns_row)

        self.fields_table = QTableWidget(0, 3)
        self.fields_table.setHorizontalHeaderLabels(["Header", "Visible", "Label"])
        self.fields_table.verticalHeader().setVisible(False)
        self.fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fields_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._populate_fields_table()
        self.fields_table.resizeColumnsToContents()
        layout.addWidget(self.fields_table)
        self.tabs.addTab(tab, "CSV")

    def _field_rows(self) -> list[tuple[str, FieldConfig]]:
        rows: list[tuple[str, FieldConfig]] = []
        seen: set[str] = set()
        for header in self._current_headers:
            config = self._config.csv.fields.get(header, FieldConfig(label=header, show=True))
            rows.append((header, config))
            seen.add(header)
        for header, config in self._config.csv.fields.items():
            if header not in seen:
                rows.append((header, config))
        return rows

    def _populate_fields_table(self) -> None:
        rows = self._field_rows()
        self.fields_table.setRowCount(len(rows))
        for row_index, (header, field_config) in enumerate(rows):
            header_item = QTableWidgetItem(header)
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.fields_table.setItem(row_index, 0, header_item)

            visible_item = QTableWidgetItem()
            visible_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            visible_item.setCheckState(
                Qt.CheckState.Checked if field_config.show else Qt.CheckState.Unchecked
            )
            self.fields_table.setItem(row_index, 1, visible_item)

            label_item = QTableWidgetItem(field_config.label or header)
            self.fields_table.setItem(row_index, 2, label_item)

    def _reset_columns_from_current_csv(self) -> None:
        if not self._current_headers:
            return
        self._config.csv.fields = {
            header: FieldConfig(label=header, show=True) for header in self._current_headers
        }
        self._populate_fields_table()
        self.fields_table.resizeColumnsToContents()

    def _collect_fields(self) -> dict[str, FieldConfig]:
        fields: dict[str, FieldConfig] = {}
        for row_index in range(self.fields_table.rowCount()):
            header_item = self.fields_table.item(row_index, 0)
            visible_item = self.fields_table.item(row_index, 1)
            label_item = self.fields_table.item(row_index, 2)
            if header_item is None or visible_item is None:
                continue
            header = header_item.text()
            label = label_item.text().strip() if label_item is not None else header
            fields[header] = FieldConfig(
                label=label or header,
                show=visible_item.checkState() == Qt.CheckState.Checked,
            )
        return fields

    def _parse_json(self, text: str, field_name: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must contain valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{field_name} must be a JSON object.")
        return data

    def _accept(self) -> None:
        try:
            self.get_config()
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid settings", str(exc))
            return
        self.accept()

    def _single_char_value(self, text: str, field_name: str, default: str) -> str:
        value = text or default
        if len(value) != 1:
            raise ValueError(f"{field_name} must be a single character.")
        return value

    def get_config(self) -> AppConfig:
        csv_fields = self._collect_fields()
        config = AppConfig.from_dict(
            {
                "provider": {
                    "active": self.active_provider_combo.currentText(),
                    "ollama": {
                        "base_url": self.ollama_base_url_edit.text().strip(),
                        "model": self.ollama_model_edit.text().strip(),
                        "options": self._parse_json(
                            self.ollama_options_edit.toPlainText(),
                            "Ollama options JSON",
                        ),
                    },
                    "openai": {
                        "base_url": self.openai_base_url_edit.text().strip(),
                        "api_key": self.openai_api_key_edit.text().strip(),
                        "model": self.openai_model_edit.text().strip(),
                        "options": self._parse_json(
                            self.openai_options_edit.toPlainText(),
                            "OpenAI options JSON",
                        ),
                    },
                },
                "generation": {
                    "temperature": self.temperature_spin.value(),
                    "top_p": self.top_p_spin.value(),
                    "max_output_tokens": self.max_tokens_spin.value(),
                },
                "csv": {
                    "original-description": self.original_description_edit.text().strip(),
                    "fields": {key: asdict(value) for key, value in csv_fields.items()},
                    "delimiter": self._single_char_value(
                        self.delimiter_edit.text(),
                        "Delimiter",
                        ",",
                    ),
                    "quotechar": self._single_char_value(
                        self.quotechar_edit.text(),
                        "Quote char",
                        '"',
                    ),
                    "encoding": self.encoding_edit.text().strip() or "utf-8-sig",
                    "newline": self.newline_edit.text(),
                    "write_header": self.write_header_checkbox.isChecked(),
                },
            }
        )
        return config
