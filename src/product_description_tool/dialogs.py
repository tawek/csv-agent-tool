from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QPainter, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from product_description_tool import message_box, file_dialog
from product_description_tool.config import (
    AppConfig,
    CsvConfig,
    FieldConfig,
)
from product_description_tool.generation import estimate_tokens_from_chars
from product_description_tool.highlighter import HtmlSyntaxHighlighter
from product_description_tool.providers import list_ollama_models, list_openai_models

from .message_box import information, warning, critical, question, QMessageBoxStandardButton as StandardButton
from .file_dialog import get_open_file_name, get_save_file_name, get_existing_directory


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
        self.resize(520, 360)

        self._elapsed_seconds = 0
        self._allow_close = False
        self._cancel_requested = False
        self._close_on_finish = False
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

        run_config_group = QGroupBox("Run configuration")
        run_config_layout = QFormLayout(run_config_group)
        run_config_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.provider_value_label = QLabel("Not set")
        self.provider_value_label.setWordWrap(True)
        self.model_value_label = QLabel("Not set")
        self.model_value_label.setWordWrap(True)
        self.temperature_value_label = QLabel("Not set")
        self.top_p_value_label = QLabel("Not set")
        self.max_output_tokens_value_label = QLabel("Not set")
        run_config_layout.addRow("Provider", self.provider_value_label)
        run_config_layout.addRow("Model", self.model_value_label)
        run_config_layout.addRow("Temperature", self.temperature_value_label)
        run_config_layout.addRow("Top P", self.top_p_value_label)
        run_config_layout.addRow("Max output tokens", self.max_output_tokens_value_label)
        layout.addWidget(run_config_group)

        self.input_stats_label = QLabel("Input prompt: 0 chars (~0 tokens)")
        self.output_stats_label = QLabel("Output: 0 chars (~0 tokens)")
        layout.addWidget(self.input_stats_label)
        layout.addWidget(self.output_stats_label)

        self.close_on_finish_checkbox = QCheckBox("Close on finish")
        layout.addWidget(self.close_on_finish_checkbox)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._handle_action_button)
        footer.addWidget(self.cancel_button)
        layout.addLayout(footer)

    def start_activity(
        self,
        *,
        title: str,
        status: str,
        total_records: int,
        input_chars: int,
        close_on_finish: bool,
        provider_name: str = "",
        model_name: str = "",
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self.setModal(True)
        self._allow_close = False
        self._cancel_requested = False
        self._close_on_finish = close_on_finish
        self._elapsed_seconds = 0
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.status_label.setText(status)
        self.close_on_finish_checkbox.setChecked(close_on_finish)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Cancel")
        self.elapsed_label.setText("0:00:00")
        self.set_record_progress(0, total_records)
        self.set_run_configuration(
            provider_name=provider_name,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
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

    def set_run_configuration(
        self,
        *,
        provider_name: str,
        model_name: str,
        temperature: float | None,
        top_p: float | None,
        max_output_tokens: int | None,
    ) -> None:
        self.provider_value_label.setText(provider_name or "Not set")
        self.model_value_label.setText(model_name or "Not set")
        self.temperature_value_label.setText(
            "Not set" if temperature is None else str(temperature)
        )
        self.top_p_value_label.setText("Not set" if top_p is None else str(top_p))
        self.max_output_tokens_value_label.setText(
            "Not set" if max_output_tokens is None else str(max_output_tokens)
        )

    def request_cancel(self) -> None:
        if self._allow_close:
            self.close()
            return
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self.status_label.setText("Cancelling...")
        self.cancel_requested.emit()

    def close_activity(self, *, force_close: bool = False) -> None:
        self._timer.stop()
        self._allow_close = True
        if force_close or self.close_on_finish_checkbox.isChecked():
            self.close()
            self.deleteLater()
            return
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Close")

    def finish_status(self, text: str) -> None:
        self.status_label.setText(text)

    def reject(self) -> None:
        if self._allow_close:
            super().reject()
            return
        self.request_cancel()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._allow_close:
            event.ignore()
            self.request_cancel()
            return
        super().closeEvent(event)

    def _handle_action_button(self) -> None:
        if self._allow_close:
            self.close()
            return
        self.request_cancel()

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

    def _configure_form_layout(self, layout: QFormLayout) -> None:
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _expand_control(
        self,
        widget: QWidget,
        *,
        minimum_width: int = 320,
    ) -> None:
        widget.setMinimumWidth(minimum_width)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, widget.sizePolicy().verticalPolicy())

    def _build_provider_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_form = QFormLayout()
        self._configure_form_layout(top_form)
        self.active_provider_combo = QComboBox()
        self.active_provider_combo.addItems(["ollama", "openai"])
        self.active_provider_combo.setCurrentText(self._config.provider.active)
        self._expand_control(self.active_provider_combo)
        top_form.addRow("Active provider", self.active_provider_combo)
        layout.addLayout(top_form)

        provider_tabs = QTabWidget()
        layout.addWidget(provider_tabs)

        ollama_tab = QWidget()
        ollama_form = QFormLayout(ollama_tab)
        self._configure_form_layout(ollama_form)
        self.ollama_base_url_edit = QLineEdit(self._config.provider.ollama.base_url)
        self._expand_control(self.ollama_base_url_edit, minimum_width=420)
        (
            self.ollama_model_combo,
            self.ollama_model_refresh_button,
        ) = self._create_model_selector(
            self._config.provider.ollama.model,
            self._refresh_ollama_models,
        )
        self.ollama_options_edit = QPlainTextEdit(
            json.dumps(self._config.provider.ollama.options, indent=2)
        )
        self._expand_control(self.ollama_options_edit, minimum_width=420)
        ollama_form.addRow("Base URL", self.ollama_base_url_edit)
        ollama_form.addRow("Model", self.ollama_model_combo.parentWidget())
        ollama_form.addRow("Options JSON", self.ollama_options_edit)
        provider_tabs.addTab(ollama_tab, "Ollama")

        openai_tab = QWidget()
        openai_form = QFormLayout(openai_tab)
        self._configure_form_layout(openai_form)
        self.openai_base_url_edit = QLineEdit(self._config.provider.openai.base_url)
        self._expand_control(self.openai_base_url_edit, minimum_width=420)
        self.openai_api_key_edit = QLineEdit(self._config.provider.openai.api_key)
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._expand_control(self.openai_api_key_edit, minimum_width=420)
        (
            self.openai_model_combo,
            self.openai_model_refresh_button,
        ) = self._create_model_selector(
            self._config.provider.openai.model,
            self._refresh_openai_models,
        )
        self.openai_options_edit = QPlainTextEdit(
            json.dumps(self._config.provider.openai.options, indent=2)
        )
        self._expand_control(self.openai_options_edit, minimum_width=420)
        openai_form.addRow("Base URL", self.openai_base_url_edit)
        openai_form.addRow("API key", self.openai_api_key_edit)
        openai_form.addRow("Model", self.openai_model_combo.parentWidget())
        openai_form.addRow("Options JSON", self.openai_options_edit)
        provider_tabs.addTab(openai_tab, "OpenAI-compatible")

        self.tabs.addTab(tab, "Provider")

    def _create_model_selector(
        self,
        current_value: str,
        refresh_handler,
    ) -> tuple[QComboBox, QPushButton]:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        container.setMinimumWidth(420)

        combo = QComboBox(container)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setDuplicatesEnabled(False)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumContentsLength(24)
        if current_value:
            combo.addItem(current_value)
        combo.setEditText(current_value)
        layout.addWidget(combo, 1)

        refresh_button = QPushButton("Refresh", container)
        refresh_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        refresh_button.clicked.connect(refresh_handler)
        layout.addWidget(refresh_button)

        return combo, refresh_button

    def _replace_model_choices(self, combo: QComboBox, model_names: list[str]) -> None:
        current_text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(model_names)
        combo.setEditText(current_text)
        combo.blockSignals(False)

    def _refresh_model_choices(
        self,
        *,
        combo: QComboBox,
        refresh_button: QPushButton,
        provider_name: str,
        loader,
    ) -> None:
        refresh_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            model_names = loader()
        except Exception as exc:
            warning(
                self,
                f"{provider_name} Models",
                f"Could not load models from {provider_name}: {exc}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()
            refresh_button.setEnabled(True)

        self._replace_model_choices(combo, model_names)
        if not model_names:
            information(
                self,
                f"{provider_name} Models",
                f"{provider_name} did not return any models.",
            )

    def _refresh_ollama_models(self) -> None:
        self._refresh_model_choices(
            combo=self.ollama_model_combo,
            refresh_button=self.ollama_model_refresh_button,
            provider_name="Ollama",
            loader=lambda: list_ollama_models(
                base_url=self.ollama_base_url_edit.text().strip(),
            ),
        )

    def _refresh_openai_models(self) -> None:
        self._refresh_model_choices(
            combo=self.openai_model_combo,
            refresh_button=self.openai_model_refresh_button,
            provider_name="OpenAI-compatible endpoint",
            loader=lambda: list_openai_models(
                base_url=self.openai_base_url_edit.text().strip(),
                api_key=self.openai_api_key_edit.text().strip(),
            ),
        )

    def _build_generation_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        self._configure_form_layout(layout)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(self._config.generation.temperature)
        self._expand_control(self.temperature_spin, minimum_width=180)

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(self._config.generation.top_p)
        self._expand_control(self.top_p_spin, minimum_width=180)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 200000)
        self.max_tokens_spin.setValue(self._config.generation.max_output_tokens)
        self._expand_control(self.max_tokens_spin, minimum_width=180)

        self.enable_thinking_checkbox = QCheckBox()
        self.enable_thinking_checkbox.setChecked(self._config.generation.enable_thinking)

        layout.addRow("Temperature", self.temperature_spin)
        layout.addRow("Top P", self.top_p_spin)
        layout.addRow("Max output tokens", self.max_tokens_spin)
        layout.addRow("Enable thinking", self.enable_thinking_checkbox)
        self.tabs.addTab(tab, "Generation")

    def _build_csv_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self._configure_form_layout(form)
        self.delimiter_edit = QLineEdit(self._config.csv.delimiter)
        self.quotechar_edit = QLineEdit(self._config.csv.quotechar)
        self.encoding_edit = QLineEdit(self._config.csv.encoding)
        self.newline_edit = QLineEdit(self._config.csv.newline)
        self.write_header_checkbox = QCheckBox()
        self.write_header_checkbox.setChecked(self._config.csv.write_header)
        self._expand_control(self.delimiter_edit, minimum_width=120)
        self._expand_control(self.quotechar_edit, minimum_width=120)
        self._expand_control(self.encoding_edit)
        self._expand_control(self.newline_edit)

        form.addRow("Delimiter", self.delimiter_edit)
        form.addRow("Quote char", self.quotechar_edit)
        form.addRow("Encoding", self.encoding_edit)
        form.addRow("Newline", self.newline_edit)
        form.addRow("Write header", self.write_header_checkbox)
        self.export_only_visible_checkbox = QCheckBox()
        self.export_only_visible_checkbox.setChecked(self._config.csv.export_only_visible)
        form.addRow("Export only visible rows", self.export_only_visible_checkbox)
        layout.addLayout(form)

        columns_row = QHBoxLayout()
        columns_row.addWidget(QLabel("Columns"))
        self.move_up_button = QPushButton("▲")
        self.move_up_button.setToolTip("Move selected field up in export order")
        self.move_up_button.clicked.connect(self._move_field_up)
        columns_row.addWidget(self.move_up_button)
        self.move_down_button = QPushButton("▼")
        self.move_down_button.setToolTip("Move selected field down in export order")
        self.move_down_button.clicked.connect(self._move_field_down)
        columns_row.addWidget(self.move_down_button)
        columns_row.addStretch(1)
        self.reset_columns_button = QPushButton("Reset From Current CSV")
        self.reset_columns_button.setEnabled(bool(self._current_headers))
        self.reset_columns_button.clicked.connect(self._reset_columns_from_current_csv)
        columns_row.addWidget(self.reset_columns_button)
        layout.addLayout(columns_row)

        self.fields_table = QTableWidget(0, 4)
        self.fields_table.setHorizontalHeaderLabels(["Header", "Visible", "Label", "Strip whitespace on export"])
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

        # Determine ordered list of current headers: respect export_order,
        # then append any current headers not yet listed, then extra fields.
        export_order = self._config.csv.export_order or []
        ordered: list[str] = []
        for h in export_order:
            if h in self._current_headers:
                ordered.append(h)
        for h in self._current_headers:
            if h not in ordered:
                ordered.append(h)

        for header in ordered:
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

            strip_item = QTableWidgetItem()
            strip_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            strip_item.setCheckState(
                Qt.CheckState.Checked if field_config.strip_html_whitespace else Qt.CheckState.Unchecked
            )
            self.fields_table.setItem(row_index, 3, strip_item)

    def _reset_columns_from_current_csv(self) -> None:
        if not self._current_headers:
            return
        self._config.csv.export_order = list(self._current_headers)
        self._config.csv.fields = {
            header: FieldConfig(label=header, show=True, strip_html_whitespace=False)
            for header in self._current_headers
        }
        self._populate_fields_table()
        self.fields_table.resizeColumnsToContents()

    def _move_field_up(self) -> None:
        row = self.fields_table.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self.fields_table.setCurrentCell(row - 1, 0)

    def _move_field_down(self) -> None:
        row = self.fields_table.currentRow()
        if row < 0 or row >= self.fields_table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self.fields_table.setCurrentCell(row + 1, 0)

    def _swap_rows(self, row_a: int, row_b: int) -> None:
        for col in range(self.fields_table.columnCount()):
            item_a = self.fields_table.takeItem(row_a, col)
            item_b = self.fields_table.takeItem(row_b, col)
            self.fields_table.setItem(row_a, col, item_b)
            self.fields_table.setItem(row_b, col, item_a)

    def _collect_export_order(self) -> list[str]:
        order: list[str] = []
        for row_index in range(self.fields_table.rowCount()):
            item = self.fields_table.item(row_index, 0)
            if item is not None:
                order.append(item.text())
        return order

    def _collect_fields(self) -> dict[str, FieldConfig]:
        fields: dict[str, FieldConfig] = {}
        for row_index in range(self.fields_table.rowCount()):
            header_item = self.fields_table.item(row_index, 0)
            visible_item = self.fields_table.item(row_index, 1)
            label_item = self.fields_table.item(row_index, 2)
            strip_item = self.fields_table.item(row_index, 3)
            if header_item is None or visible_item is None:
                continue
            header = header_item.text()
            label = label_item.text().strip() if label_item is not None else header
            strip_whitespace = (
                strip_item.checkState() == Qt.CheckState.Checked
                if strip_item is not None
                else False
            )
            fields[header] = FieldConfig(
                label=label or header,
                show=visible_item.checkState() == Qt.CheckState.Checked,
                strip_html_whitespace=strip_whitespace,
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
            critical(self, "Invalid settings", str(exc))
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
                        "model": self.ollama_model_combo.currentText().strip(),
                        "options": self._parse_json(
                            self.ollama_options_edit.toPlainText(),
                            "Ollama options JSON",
                        ),
                    },
                    "openai": {
                        "base_url": self.openai_base_url_edit.text().strip(),
                        "api_key": self.openai_api_key_edit.text().strip(),
                        "model": self.openai_model_combo.currentText().strip(),
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
                    "enable_thinking": self.enable_thinking_checkbox.isChecked(),
                },
                "csv": {
                    "fields": {key: asdict(value) for key, value in csv_fields.items()},
                    "export-order": self._collect_export_order(),
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
                    "export-only-visible": self.export_only_visible_checkbox.isChecked(),
                },
            }
        )
        return config


class ExportDialog(QDialog):
    def __init__(
        self,
        *,
        target_path: str,
        default_only_visible: bool,
        has_visible_rows: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Export CSV")
        self.resize(500, 140)

        self._target_path = target_path
        self._export_only_visible = default_only_visible
        self._confirmed = False

        layout = QVBoxLayout(self)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Target path:"))
        self.path_edit = QLineEdit(target_path)
        path_layout.addWidget(self.path_edit)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_button)
        layout.addLayout(path_layout)

        self.visible_checkbox = QCheckBox("Export only visible rows")
        self.visible_checkbox.setChecked(default_only_visible)
        self.visible_checkbox.setEnabled(has_visible_rows)
        layout.addWidget(self.visible_checkbox)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._on_export)
        button_layout.addWidget(self.export_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def _browse_path(self) -> None:
        path = get_save_file_name(
            self,
            "Export CSV",
            self.path_edit.text(),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.path_edit.setText(path)

    def _on_export(self) -> None:
        target = self.path_edit.text().strip()
        if not target:
            warning(self, "Export", "Target path must not be empty.")
            return

        self._export_only_visible = self.visible_checkbox.isChecked()
        file_exists = Path(target).exists()

        if file_exists:
            reply = question(
                self,
                "Confirm Overwrite",
                f"File '{target}' already exists. Overwrite?",
                StandardButton.Yes | StandardButton.No,
            )
            if reply != StandardButton.Yes:
                return

        if self._export_only_visible and not self.visible_checkbox.isEnabled():
            warning(self, "Export", "No visible rows to export.")
            return

        self._confirmed = True
        self.accept()

    def get_result(self) -> tuple[str, bool]:
        return (self.path_edit.text().strip(), self.visible_checkbox.isChecked())


class AddKbAttachmentsDialog(QDialog):
    """Small modal dialog for selecting one or more KB files as prompt attachments."""

    def __init__(
        self,
        *,
        kb_files: list[str],
        existing_sources: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Knowledge-Base Attachments")
        self.setModal(True)
        self.resize(500, 380)

        self._kb_files = kb_files
        self._existing_sources = existing_sources
        self._selected_sources: list[str] = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Select one or more knowledge-base files to append as prompt "
            "attachments. The prompt text itself will not be modified."
        ))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search files...")
        self.search_edit.textChanged.connect(self._rebuild_list)
        layout.addWidget(self.search_edit)

        self.list_widget = QTableWidget(0, 2)
        self.list_widget.setHorizontalHeaderLabels(["", "File"])
        self.list_widget.verticalHeader().setVisible(False)
        self.list_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.list_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.list_widget, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        self.add_button = QPushButton("Add Selected")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._confirm)
        button_layout.addWidget(self.add_button)
        layout.addLayout(button_layout)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        search_text = self.search_edit.text().strip().lower()
        rows = [p for p in self._kb_files if not search_text or search_text in p.lower()]

        self.list_widget.setRowCount(len(rows))
        for row_idx, path in enumerate(rows):
            already = path in self._existing_sources
            chk = QTableWidgetItem()
            chk.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            if already:
                chk.setCheckState(Qt.CheckState.Unchecked)
                chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                chk.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.setItem(row_idx, 0, chk)

            item = QTableWidgetItem(path)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if already:
                item.setForeground(QColor("gray"))
            self.list_widget.setItem(row_idx, 1, item)

        if not rows:
            if not self._kb_files:
                self.status_label.setText("No supported knowledge-base files are available.")
            else:
                self.status_label.setText("No knowledge-base files match the current search.")
        else:
            self.status_label.setText("")

        self.list_widget.itemChanged.connect(self._update_add_button)
        self._update_add_button()

    def _update_add_button(self) -> None:
        self.add_button.setEnabled(self._count_checked() > 0)

    def _count_checked(self) -> int:
        count = 0
        for row in range(self.list_widget.rowCount()):
            item = self.list_widget.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def _confirm(self) -> None:
        sources = []
        for row in range(self.list_widget.rowCount()):
            item = self.list_widget.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                src_item = self.list_widget.item(row, 1)
                if src_item is not None:
                    sources.append(src_item.text())
        self._selected_sources = sources
        self.accept()

    def selected_sources(self) -> list[str]:
        return self._selected_sources


class AddColumnAttachmentsDialog(QDialog):
    """Small modal dialog for selecting one or more CSV columns as prompt attachments."""

    def __init__(
        self,
        *,
        csv_columns: list[str],
        existing_sources: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Column Attachments")
        self.setModal(True)
        self.resize(460, 340)

        self._csv_columns = csv_columns
        self._existing_sources = existing_sources
        self._selected_sources: list[str] = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Select one or more current CSV columns to append as prompt "
            "attachments. The prompt text itself will not be modified."
        ))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search columns...")
        self.search_edit.textChanged.connect(self._rebuild_list)
        layout.addWidget(self.search_edit)

        self.list_widget = QTableWidget(0, 2)
        self.list_widget.setHorizontalHeaderLabels(["", "Column"])
        self.list_widget.verticalHeader().setVisible(False)
        self.list_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.list_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.list_widget, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        self.add_button = QPushButton("Add Selected")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._confirm)
        button_layout.addWidget(self.add_button)
        layout.addLayout(button_layout)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        search_text = self.search_edit.text().strip().lower()
        rows = [c for c in self._csv_columns if not search_text or search_text in c.lower()]

        self.list_widget.setRowCount(len(rows))
        for row_idx, col_name in enumerate(rows):
            already = col_name in self._existing_sources
            chk = QTableWidgetItem()
            chk.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            if already:
                chk.setCheckState(Qt.CheckState.Unchecked)
                chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                chk.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.setItem(row_idx, 0, chk)

            item = QTableWidgetItem(col_name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if already:
                item.setForeground(QColor("gray"))
            self.list_widget.setItem(row_idx, 1, item)

        if not rows:
            if not self._csv_columns:
                self.status_label.setText("No current CSV columns are available.")
            else:
                self.status_label.setText("No columns match the current search.")
        else:
            self.status_label.setText("")

        self.list_widget.itemChanged.connect(self._update_add_button)
        self._update_add_button()

    def _update_add_button(self) -> None:
        self.add_button.setEnabled(self._count_checked() > 0)

    def _count_checked(self) -> int:
        count = 0
        for row in range(self.list_widget.rowCount()):
            item = self.list_widget.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def _confirm(self) -> None:
        sources = []
        for row in range(self.list_widget.rowCount()):
            item = self.list_widget.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                src_item = self.list_widget.item(row, 1)
                if src_item is not None:
                    sources.append(src_item.text())
        self._selected_sources = sources
        self.accept()

    def selected_sources(self) -> list[str]:
        return self._selected_sources


class AttachmentManager(QDialog):
    """Modal dialog for managing the selected prompt's attachment metadata.

    Supports add, remove, and reorder (Move Up / Move Down).  The order
    shown is the effective processing order.
    """

    def __init__(
        self,
        *,
        prompt_output_field: str,
        attachments: list,
        knowledge_base_dir: str | None = None,
        kb_files: list[str] | None = None,
        csv_columns: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Prompt Attachments — {prompt_output_field}")
        self.setModal(True)
        self.resize(620, 440)

        from product_description_tool.project import PromptAttachment

        self._attachments: list[PromptAttachment] = list(attachments)
        self._prompt_output_field = prompt_output_field
        self._knowledge_base_dir = knowledge_base_dir
        self._kb_files = kb_files or []
        self._csv_columns = csv_columns or []

        layout = QVBoxLayout(self)

        # Info text
        info_label = QLabel(
            "Attachments are stored as prompt metadata and are appended "
            "automatically to the effective prompt with source provenance. "
            "The prompt text itself is not modified."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #555; font-size: 11px; padding: 4px 0;")
        layout.addWidget(info_label)

        # Attachment table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Type", "Source", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_button_states)
        layout.addWidget(self.table, 1)

        # Status area
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Action buttons — two separate add flows per spec
        action_layout = QHBoxLayout()
        self.add_kb_button = QPushButton("Add KB Files\u2026")
        self.add_kb_button.clicked.connect(self._on_add_kb_files)
        action_layout.addWidget(self.add_kb_button)

        self.add_column_button = QPushButton("Add Columns\u2026")
        self.add_column_button.clicked.connect(self._on_add_columns)
        action_layout.addWidget(self.add_column_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._on_remove)
        action_layout.addWidget(self.remove_button)

        action_layout.addStretch(1)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.setEnabled(False)
        self.move_up_button.clicked.connect(self._on_move_up)
        action_layout.addWidget(self.move_up_button)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.setEnabled(False)
        self.move_down_button.clicked.connect(self._on_move_down)
        action_layout.addWidget(self.move_down_button)

        layout.addLayout(action_layout)

        # Help text shown when KB directory is not configured
        self._kb_help_label = QLabel("")
        self._kb_help_label.setStyleSheet(
            "color: #888; font-size: 10px; font-style: italic; padding: 2px 0;"
        )
        self._kb_help_label.setWordWrap(True)
        self._kb_help_label.setVisible(False)
        layout.addWidget(self._kb_help_label)

        # Cost warning label — shown when any CSV column is ordered before a KB file
        self.cost_warning_label = QLabel("")
        self.cost_warning_label.setStyleSheet(
            "color: #888; font-size: 10px; font-style: italic; padding: 2px 0;"
        )
        self.cost_warning_label.setWordWrap(True)
        layout.addWidget(self.cost_warning_label)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_layout.addWidget(close_button)
        layout.addLayout(close_layout)

        self._refresh_table()

    def _resolve_kb_file_status(self, source: str) -> str:
        """Return a status string for a KB file attachment."""
        if not self._knowledge_base_dir:
            return "Missing KB root"
        kb_path = Path(self._knowledge_base_dir).resolve()
        candidate = (kb_path / source).resolve()
        try:
            candidate.relative_to(kb_path)
        except ValueError:
            return "Path escapes KB directory"
        if not candidate.exists():
            return "File not found"
        if candidate.suffix.lower() not in {".md", ".markdown", ".csv"}:
            return "Unsupported type"
        return "Available"

    def _resolve_column_status(self, source: str) -> str:
        """Return a status string for a CSV column attachment."""
        if source in self._csv_columns:
            return "Available"
        return "Column not found"

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._attachments))
        for idx, att in enumerate(self._attachments):
            # Position number
            num_item = QTableWidgetItem(str(idx + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(idx, 0, num_item)

            # Type
            type_label = "KB file" if att.source_type == "kb_file" else "CSV column"
            type_item = QTableWidgetItem(type_label)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(idx, 1, type_item)

            # Source
            source_item = QTableWidgetItem(att.source)
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(idx, 2, source_item)

            # Status/Notes
            if att.source_type == "kb_file":
                status = self._resolve_kb_file_status(att.source)
            else:
                status = self._resolve_column_status(att.source)
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if status != "Available":
                status_item.setForeground(QColor("#cc6600"))
            self.table.setItem(idx, 3, status_item)

        self._update_button_states()
        self._update_status_text()
        self._update_cost_warning()

    def _update_cost_warning(self) -> None:
        """Show fine-print warning if any CSV column is ordered before any KB file."""
        csv_before_kb = False
        found_kb = False
        # Scan from the end to find the first KB file; if we encounter a CSV
        # column after having seen at least one KB file, the condition applies.
        for att in reversed(self._attachments):
            if att.source_type == "kb_file":
                found_kb = True
            elif att.source_type == "csv_column" and found_kb:
                csv_before_kb = True
                break
        if csv_before_kb:
            self.cost_warning_label.setText(
                "Note: Moving a CSV-column attachment above any KB-file "
                "attachment may increase prompt cost because KB content may "
                "be reprocessed instead of benefiting from a more stable prefix."
            )
        else:
            self.cost_warning_label.setText("")

    def _update_status_text(self) -> None:
        # Don't show empty-state message when KB directory is missing;
        # _kb_help_label already explains why attachments can't be added.
        if not self._knowledge_base_dir:
            self.status_label.setText("")
            return
        if not self._attachments:
            self.status_label.setText("No attachments configured for this prompt.")
        else:
            has_issues = False
            for row_idx in range(self.table.rowCount()):
                status_item = self.table.item(row_idx, 3)
                if status_item is not None and status_item.text() != "Available":
                    has_issues = True
                    break
            if has_issues:
                self.status_label.setText(
                    "Some attachments have issues (see Status column). "
                    "Preview and processing will be blocked until resolved."
                )
            else:
                self.status_label.setText("")

    def _update_button_states(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0
        self.remove_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and selected_rows[0].row() > 0)
        self.move_down_button.setEnabled(
            has_selection and selected_rows[0].row() < self.table.rowCount() - 1
        )
        # Disable add flows when no sources of that type are available
        no_kb = not self._knowledge_base_dir or not self._kb_files
        no_columns = not self._csv_columns
        self.add_kb_button.setEnabled(not no_kb)
        self.add_column_button.setEnabled(not no_columns)
        self._update_kb_help()

    def _update_kb_help(self) -> None:
        """Show explanatory text when KB directory is not configured."""
        if not self._knowledge_base_dir:
            self._kb_help_label.setText(
                "Knowledge-base file attachments require a configured "
                "project knowledge-base directory."
            )
            self._kb_help_label.setVisible(True)
        else:
            self._kb_help_label.setVisible(False)

    def _insert_kb_attachments(self, sources: list[str]) -> None:
        """Insert new KB-file attachments before the first CSV column, or at end."""
        from product_description_tool.project import PromptAttachment

        new_attachments = [
            PromptAttachment(source_type="kb_file", source=s)
            for s in sources
        ]
        # Find the index of the first CSV column attachment
        insert_idx = len(self._attachments)
        for idx, att in enumerate(self._attachments):
            if att.source_type == "csv_column":
                insert_idx = idx
                break
        self._attachments[insert_idx:insert_idx] = new_attachments

    def _insert_column_attachments(self, sources: list[str]) -> None:
        """Insert new CSV-column attachments after all existing attachments."""
        from product_description_tool.project import PromptAttachment

        new_attachments = [
            PromptAttachment(source_type="csv_column", source=s)
            for s in sources
        ]
        self._attachments.extend(new_attachments)

    def _on_add_kb_files(self) -> None:
        existing_kb = {a.source for a in self._attachments if a.source_type == "kb_file"}
        dialog = AddKbAttachmentsDialog(
            kb_files=self._kb_files,
            existing_sources=existing_kb,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        sources = dialog.selected_sources()
        if sources:
            self._insert_kb_attachments(sources)
            self._refresh_table()

    def _on_add_columns(self) -> None:
        existing_cols = {a.source for a in self._attachments if a.source_type == "csv_column"}
        dialog = AddColumnAttachmentsDialog(
            csv_columns=self._csv_columns,
            existing_sources=existing_cols,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        sources = dialog.selected_sources()
        if sources:
            self._insert_column_attachments(sources)
            self._refresh_table()

    def _on_remove(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self._attachments):
            del self._attachments[row]
            self._refresh_table()

    def _on_move_up(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row > 0:
            self._attachments[row], self._attachments[row - 1] = (
                self._attachments[row - 1],
                self._attachments[row],
            )
            self._refresh_table()
            self.table.selectRow(row - 1)

    def _on_move_down(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._attachments) - 1:
            self._attachments[row], self._attachments[row + 1] = (
                self._attachments[row + 1],
                self._attachments[row],
            )
            self._refresh_table()
            self.table.selectRow(row + 1)

    def get_attachments(self):
        return list(self._attachments)
