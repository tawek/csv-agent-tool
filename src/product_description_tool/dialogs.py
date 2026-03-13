from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
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
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from product_description_tool.config import (
    AppConfig,
    CsvConfig,
    FieldConfig,
)
from product_description_tool.highlighter import HtmlSyntaxHighlighter


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
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(720, 640)
        self._config = config

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
        self.result_description_edit = QLineEdit(self._config.csv.result_description)
        self.delimiter_edit = QLineEdit(self._config.csv.delimiter or "")
        self.quotechar_edit = QLineEdit(self._config.csv.quotechar or "")
        self.encoding_edit = QLineEdit(self._config.csv.encoding)
        self.newline_edit = QLineEdit(self._config.csv.newline)
        self.write_header_checkbox = QCheckBox()
        self.write_header_checkbox.setChecked(self._config.csv.write_header)

        form.addRow("Original description column", self.original_description_edit)
        form.addRow("Result description column", self.result_description_edit)
        form.addRow("Delimiter override", self.delimiter_edit)
        form.addRow("Quote char override", self.quotechar_edit)
        form.addRow("Encoding", self.encoding_edit)
        form.addRow("Newline", self.newline_edit)
        form.addRow("Write header", self.write_header_checkbox)
        layout.addLayout(form)

        layout.addWidget(QLabel("Fields JSON"))
        self.fields_edit = QPlainTextEdit(
            json.dumps(
                {key: asdict(value) for key, value in self._config.csv.fields.items()},
                indent=2,
            )
        )
        layout.addWidget(self.fields_edit)
        self.tabs.addTab(tab, "CSV")

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

    def get_config(self) -> AppConfig:
        csv_fields_raw = self._parse_json(self.fields_edit.toPlainText(), "Fields JSON")
        csv_fields = {
            key: FieldConfig.from_dict(value if isinstance(value, dict) else {})
            for key, value in csv_fields_raw.items()
        }
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
                    "result-description": self.result_description_edit.text().strip(),
                    "fields": {key: asdict(value) for key, value in csv_fields.items()},
                    "delimiter": self.delimiter_edit.text() or None,
                    "quotechar": self.quotechar_edit.text() or None,
                    "encoding": self.encoding_edit.text().strip() or "utf-8-sig",
                    "newline": self.newline_edit.text(),
                    "write_header": self.write_header_checkbox.isChecked(),
                },
            }
        )
        return config
