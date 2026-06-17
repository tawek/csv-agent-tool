from pathlib import Path

import pytest
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QGroupBox, QMessageBox

from product_description_tool import message_box, file_dialog, input_dialog
from product_description_tool.config import AppConfig, ConfigStore, FieldConfig
from product_description_tool.generation import PromptPayload, USER_PROMPT
from product_description_tool.collapsible_panel import PanelState
from product_description_tool.main_window import MainWindow
from product_description_tool.project import ProjectPrompt
from product_description_tool.providers import GenerationCancelled


class FakeDialog:
    next_text = ""

    def __init__(self, *, title: str, text: str, parent=None) -> None:
        self._text = text

    def exec(self) -> bool:
        return True

    def text(self) -> str:
        return self.next_text


class FakeGenerationService:
    def validate_template(self, template: str, headers: list[str], knowledge_base_dir=None) -> None:
        return None

    def validate_attachments(self, attachments, headers, knowledge_base_dir=None) -> None:
        pass

    def prepare_prompt(self, *, template: str, row: dict[str, str], knowledge_base_dir=None, attachments=None):
        rendered = template
        for col, val in row.items():
            rendered = rendered.replace("{{" + col + "}}", val)
        return PromptPayload(
            system_prompt=rendered,
            user_prompt=USER_PROMPT,
        )

    class _PromptPayload:
        def __init__(self, input_char_count: int) -> None:
            self.input_char_count = input_char_count

    def process_row(
        self,
        *,
        row_index,
        row,
        template,
        config,
        knowledge_base_dir=None,
        attachments=None,
        on_prompt_ready=None,
        on_chunk=None,
        should_cancel=None,
    ):
        class Result:
            def __init__(self, row_index: int, content: str) -> None:
                self.row_index = row_index
                self.content = content

        content = f"<p>{template}-{row['sku']}</p>"
        if on_prompt_ready is not None:
            on_prompt_ready(row_index, self._PromptPayload(len(template.replace("{{sku}}", row["sku"])) + len(USER_PROMPT)))
        if on_chunk is not None:
            on_chunk(row_index, content)
        return Result(row_index, content)

    def process_rows(
        self,
        *,
        rows,
        template,
        config,
        knowledge_base_dir=None,
        attachments=None,
        on_result=None,
        on_prompt_ready=None,
        on_chunk=None,
        should_cancel=None,
    ):
        results = []
        for index, row in enumerate(rows):
            if should_cancel is not None and should_cancel():
                break
            result = self.process_row(
                row_index=index,
                row=row,
                template=template,
                config=config,
                knowledge_base_dir=knowledge_base_dir,
                attachments=attachments,
                on_prompt_ready=on_prompt_ready,
                on_chunk=None,
                should_cancel=should_cancel,
            )
            if on_chunk is not None:
                on_chunk(index, result.content)
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results


class SlowCancellableGenerationService(FakeGenerationService):
    def process_row(
        self,
        *,
        row_index,
        row,
        template,
        config,
        knowledge_base_dir=None,
        attachments=None,
        on_prompt_ready=None,
        on_chunk=None,
        should_cancel=None,
    ):
        QThread.msleep(50)
        return super().process_row(
            row_index=row_index,
            row=row,
            template=template,
            config=config,
            knowledge_base_dir=knowledge_base_dir,
            attachments=attachments,
            on_prompt_ready=on_prompt_ready,
            on_chunk=on_chunk,
            should_cancel=should_cancel,
        )


class BlockingCancellableGenerationService(FakeGenerationService):
    def __init__(self) -> None:
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def process_row(
        self,
        *,
        row_index,
        row,
        template,
        config,
        knowledge_base_dir=None,
        attachments=None,
        on_prompt_ready=None,
        on_chunk=None,
        should_cancel=None,
    ):
        if on_prompt_ready is not None:
            on_prompt_ready(
                row_index,
                self._PromptPayload(len(template.replace("{{sku}}", row["sku"])) + len(USER_PROMPT)),
            )
        while not self._cancel_requested:
            QThread.msleep(10)
        raise GenerationCancelled("Generation cancelled.")


class DelayedCancelGenerationService(FakeGenerationService):
    def __init__(self) -> None:
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def process_row(
        self,
        *,
        row_index,
        row,
        template,
        config,
        knowledge_base_dir=None,
        attachments=None,
        on_prompt_ready=None,
        on_chunk=None,
        should_cancel=None,
    ):
        if on_prompt_ready is not None:
            on_prompt_ready(
                row_index,
                self._PromptPayload(len(template.replace("{{sku}}", row["sku"])) + len(USER_PROMPT)),
            )
        while not self._cancel_requested:
            QThread.msleep(10)
        QThread.msleep(250)
        raise GenerationCancelled("Generation cancelled.")


class FakeSettingsDialog:
    def __init__(self, config, *, current_headers=None, parent=None) -> None:
        self._config = AppConfig.from_dict(config.to_dict())
        self._config.csv.fields = {
            "sku": FieldConfig(label="SKU", show=False),
            "description": FieldConfig(label="Product Description", show=True),
            "generated": FieldConfig(label="Generated", show=True),
        }
        self._config.csv.delimiter = ";"
        self._config.csv.quotechar = '"'
        # The real SettingsDialog always marks export as initialized
        # because the user explicitly confirmed settings (AR-8).
        self._config.csv.export_settings_initialized = True

    def exec(self) -> bool:
        return True

    def get_config(self):
        return self._config


def _write_csv(tmp_path: Path, row_count: int = 2) -> Path:
    csv_path = tmp_path / "products.csv"
    rows = ['A-1;"<p>Alpha</p>";"<p>Existing</p>"']
    for index in range(1, row_count):
        rows.append(f'B-{index + 1};"<p>Beta {index}</p>";""')
    csv_path.write_text(
        "sku;description;generated\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return csv_path


def _patch_csv_dialog(monkeypatch, csv_path: Path) -> None:
    file_dialog.set_response(
        "getOpenFileName",
        (str(csv_path), "CSV Files (*.csv)"),
    )


def _import_window_csv(window: MainWindow, monkeypatch, csv_path: Path) -> None:
    _patch_csv_dialog(monkeypatch, csv_path)
    window.load_csv()


def _add_prompt(window: MainWindow, *, output_field: str, prompt: str, enabled: bool = True) -> None:
    window.project.prompts.append(
        ProjectPrompt(output_field=output_field, prompt=prompt, enabled=enabled)
    )
    window._sync_project_with_document()
    window._refresh_prompt_controls(preserve_field=output_field)
    window._refresh_table_from_document()
    window._update_preview_field_selectors(preserve_selection=False)


def test_loading_and_selecting_row_updates_previews(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{description}}")

    window.table_view.selectRow(1)
    qtbot.waitUntil(lambda: window.last_original_preview_html == "<p>Beta 1</p>")
    qtbot.waitUntil(lambda: window.table_view.viewport().width() > 0)

    assert window.last_result_preview_html == ""
    assert window.original_stats_label.text() == "Sections: 0, Paragraphs: 1, Words: 2, Characters: 5"
    assert window.result_stats_label.text() == "Sections: 0, Paragraphs: 0, Words: 0, Characters: 0"
    assert "Files" not in [group.title() for group in window.findChildren(QGroupBox)]
    total_width = sum(window.table_view.columnWidth(index) for index in range(window.proxy_model.columnCount()))
    assert total_width <= window.table_view.viewport().width() + 4


def test_window_title_tracks_current_project_and_dirty_state(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)

    project_path = tmp_path / "catalog.project.json"
    file_dialog.set_response(
        "getSaveFileName",
        (str(project_path), "Project Files (*.project.json)"),
    )
    assert window.save_project(save_as=True)
    file_dialog.reset()
    assert str(project_path) in window.windowTitle()
    assert not window.isWindowModified()
    assert (tmp_path / "catalog.csv").exists()

    window.document.rows[0]["generated"] = "<p>Changed</p>"
    window._set_project_modified(True)

    assert window.isWindowModified()


def test_edit_selected_description_updates_model(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("product_description_tool.main_window.HtmlEditorDialog", FakeDialog)
    FakeDialog.next_text = "<p>Updated</p>"

    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{description}}")

    window.edit_selected_description("description")

    assert window.document.rows[0]["description"] == "<p>Updated</p>"
    assert window.last_original_preview_html == "<p>Updated</p>"


def test_preview_selected_updates_only_current_prompt_field(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.table_view.selectRow(1)
    window.preview_selected_row()

    assert window._activity_dialog is not None
    assert window._activity_dialog.record_progress_bar.maximum() == 1
    expected_input_chars = len("Rewrite B-2") + len(USER_PROMPT)
    assert str(expected_input_chars) in window._activity_dialog.input_stats_label.text()

    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>Rewrite {{sku}}-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>Existing</p>"


def test_preview_activity_dialog_shows_active_provider_and_generation_settings(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    window.config.provider.active = "openai"
    window.config.provider.openai.model = "gpt-5-mini"
    window.config.generation.temperature = 0.4
    window.config.generation.top_p = 0.85
    window.config.generation.max_output_tokens = 750
    window.config.generation.enable_thinking = True
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.preview_selected_row()

    assert window._activity_dialog is not None
    assert window._activity_dialog.provider_value_label.text() == "OpenAI-compatible"
    assert window._activity_dialog.model_value_label.text() == "gpt-5-mini"
    assert window._activity_dialog.temperature_value_label.text() == "0.4"
    assert window._activity_dialog.top_p_value_label.text() == "0.85"
    assert window._activity_dialog.max_output_tokens_value_label.text() == "750"


def test_process_all_runs_only_enabled_prompts(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="One {{sku}}", enabled=True)
    _add_prompt(window, output_field="generated_two", prompt="Two {{sku}}", enabled=False)

    window.process_all_rows()

    assert window._activity_dialog is not None
    assert window._activity_dialog.record_progress_bar.maximum() == 2
    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>One {{sku}}-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>One {{sku}}-A-1</p>"
    assert window.document.rows[0]["generated_two"] == ""


def test_activity_stats_reset_for_each_prompt_run(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    window._show_activity_dialog(
        title="Processing",
        status="Starting...",
        total_records=2,
        input_chars=10,
        close_on_finish=False,
    )
    window._activity_output_chars = 12
    window._activity_row_output_chars = {(0, "generated"): 12}

    window._handle_prompt_started(0, "generated", 42)
    assert "42" in window._activity_dialog.input_stats_label.text()
    assert "0 chars" in window._activity_dialog.output_stats_label.text()

    window._handle_chunk_generated(0, "generated", "abcd")
    assert "4 chars" in window._activity_dialog.output_stats_label.text()

    window._handle_prompt_started(0, "seo", 21)
    assert "21" in window._activity_dialog.input_stats_label.text()
    assert "0 chars" in window._activity_dialog.output_stats_label.text()

    window._close_activity_dialog()


def test_filters_limit_processing_scope_to_visible_rows(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.filter_patterns = {"sku": "A-*"}
    window.proxy_model.set_filter_pattern(0, "A-*")
    window._update_filter_button_text()

    assert window.proxy_model.rowCount() == 1

    window.process_visible_rows()

    qtbot.waitUntil(lambda: window.document.rows[0]["generated"] == "<p>Rewrite {{sku}}-A-1</p>")
    assert window.document.rows[0]["generated"] == "<p>Rewrite {{sku}}-A-1</p>"
    assert window.document.rows[1]["generated"] == ""
    assert window.filter_button.text() == "Filter (1)"


def test_process_all_rows_ignores_filter_scope(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.filter_patterns = {"sku": "A-*"}
    window.proxy_model.set_filter_pattern(0, "A-*")
    window._update_filter_button_text()

    window.process_all_rows()

    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>Rewrite {{sku}}-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>Rewrite {{sku}}-A-1</p>"
    assert window.document.rows[1]["generated"] == "<p>Rewrite {{sku}}-B-2</p>"


def test_description_field_selector_reloads_preview(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)

    window.right_field_combo.setCurrentText("sku")

    qtbot.waitUntil(lambda: window.last_result_preview_html == "A-1")


def test_prompt_selection_updates_right_preview_field(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="First {{sku}}")
    _add_prompt(window, output_field="seo", prompt="Second {{sku}}")

    window.prompt_selector.setCurrentText("generated")
    window.prompt_selector.setCurrentText("seo")

    assert window.right_field_combo.currentText() == "seo"


def test_menu_actions_have_requested_shortcuts(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    assert window.process_all_action.shortcut().toString() == "Ctrl+P"
    assert window.process_current_action.shortcut().toString() == "Ctrl+Enter"
    assert window.edit_original_action.shortcut().toString() == "Ctrl+O"
    assert window.edit_result_action.shortcut().toString() == "Ctrl+R"


def test_cancel_batch_processing_stops_before_all_rows_finish(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = SlowCancellableGenerationService()
    csv_path = _write_csv(tmp_path, row_count=5)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.process_all_rows()
    qtbot.waitUntil(lambda: window._activity_dialog is not None)
    dialog = window._activity_dialog
    qtbot.waitUntil(lambda: window.document.rows[0]["generated"] == "<p>Rewrite {{sku}}-A-1</p>")

    window._cancel_processing()

    qtbot.waitUntil(lambda: window._worker_thread is None)
    assert window.status.currentMessage() == "Processing cancelled"
    assert window.document.rows[-1]["generated"] == ""
    assert window._activity_dialog is None


def test_cancel_batch_processing_restores_main_window_state_after_forced_abort(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = BlockingCancellableGenerationService()
    csv_path = _write_csv(tmp_path, row_count=2)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.process_all_rows()
    qtbot.waitUntil(lambda: window._activity_dialog is not None)
    qtbot.waitUntil(lambda: window._worker_thread is not None)

    window._cancel_processing()

    qtbot.waitUntil(lambda: window._worker_thread is None)
    assert window.status.currentMessage() == "Processing cancelled"
    assert window._busy is False
    assert window.filter_button.isEnabled() is True
    assert window.process_button.isEnabled() is True
    assert window.preview_button.isEnabled() is True


def test_cancel_batch_processing_closes_dialog_immediately_while_worker_unwinds(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = DelayedCancelGenerationService()
    csv_path = _write_csv(tmp_path, row_count=2)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.process_all_rows()
    qtbot.waitUntil(lambda: window._activity_dialog is not None)
    qtbot.waitUntil(lambda: window._worker_thread is not None)

    window._cancel_processing()

    assert window._activity_dialog is None
    assert window.status.currentMessage() == "Cancelling..."
    assert window._worker_thread is not None
    assert window._busy is False
    assert window.filter_button.isEnabled() is True
    assert window.settings_action.isEnabled() is True
    assert window.edit_original_button.isEnabled() is True
    assert window.process_button.isEnabled() is False
    assert window.preview_button.isEnabled() is False

    qtbot.waitUntil(lambda: window._worker_thread is None)
    assert window.status.currentMessage() == "Processing cancelled"


def test_large_processing_run_requires_confirmation(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path, row_count=11)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    message_box.set_response("question", QMessageBox.StandardButton.No)

    window.process_all_rows()

    message_box.reset()
    assert window._worker_thread is None
    assert all(row["generated"] in {"", "<p>Existing</p>"} for row in window.document.rows)


def test_single_preview_defaults_close_on_finish(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.preview_selected_row()

    assert window._activity_dialog is not None
    assert window._activity_dialog.close_on_finish_checkbox.isChecked()


def test_batch_processing_defaults_close_on_finish_off(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="generated", prompt="Rewrite {{sku}}")

    window.process_all_rows()

    assert window._activity_dialog is not None
    assert not window._activity_dialog.close_on_finish_checkbox.isChecked()


def test_open_settings_updates_table_and_preserves_selected_row(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("product_description_tool.main_window.SettingsDialog", FakeSettingsDialog)

    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    window.table_view.selectRow(1)

    window.open_settings()

    qtbot.waitUntil(lambda: window._selected_source_row() == 1)
    assert window.table_model.visible_headers == ["description", "generated"]
    assert window.table_model.headerData(0, Qt.Orientation.Horizontal) == "Product Description"


def test_new_window_does_not_add_default_generated_column(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    assert window.document.headers == []
    assert window.left_field_combo.count() == 0
    assert window.right_field_combo.count() == 0


def test_add_prompt_ensures_output_column_exists(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    _add_prompt(window, output_field="short_description", prompt="Short {{sku}}")

    assert "short_description" in window.document.headers
    assert "short_description" in window.table_model.visible_headers


def test_generation_updates_table_for_non_default_output_field(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="short_description", prompt="Short {{sku}}")

    window.preview_selected_row()

    qtbot.waitUntil(
        lambda: window.document.rows[0]["short_description"] == "<p>Short {{sku}}-A-1</p>"
    )
    column_index = window.table_model.visible_headers.index("short_description")
    assert (
        window.table_model.data(window.table_model.index(0, column_index))
        == "<p>Short {{sku}}-A-1</p>"
    )


def test_main_window_uses_three_collapsible_panels_with_equal_initial_sizes(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.sections_splitter.sizes()[0] > 0)
    panels = [window.csv_panel, window.prompt_panel, window.description_panel]

    assert [panel.title for panel in panels] == ["CSV Data", "Prompts", "Description"]
    sizes = window.sections_splitter.sizes()
    assert max(sizes) - min(sizes) <= 40

    window.prompt_panel.set_expanded(False)
    qtbot.waitUntil(lambda: not window.prompt_panel.content.isVisible())

    collapsed_sizes = window.sections_splitter.sizes()
    assert collapsed_sizes[1] < collapsed_sizes[0]
    assert collapsed_sizes[1] < collapsed_sizes[2]


def test_collapsible_panels_use_palette_roles_in_stylesheet(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    stylesheet = window.csv_panel.styleSheet()

    assert "palette(button)" in stylesheet
    assert "palette(button-text)" in stylesheet
    assert "palette(base)" in stylesheet
    assert "palette(mid)" in stylesheet
    assert "#2d2d2d" not in stylesheet
    assert "#242424" not in stylesheet


def test_process_all_aborts_on_cyclic_prompt_dependencies(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)
    _add_prompt(window, output_field="a", prompt="Use {{b}}")
    _add_prompt(window, output_field="b", prompt="Use {{a}}")

    critical_messages = []
    original_critical = QMessageBox.critical

    @staticmethod
    def fake_critical(parent, title, text, *args, **kwargs):
        critical_messages.append((title, text))
        return QMessageBox.StandardButton.Ok

    message_box.set_response("critical", fake_critical)

    window.process_all_rows()

    message_box.reset()
    assert len(critical_messages) == 1
    title, text = critical_messages[0]
    assert "Cyclic" in text
    assert window._activity_dialog is None


# ── Panel grow/shrink state tests (Use Case 25) ──────────────────────────


def test_panel_plus_button_fixed_text_and_tooltip(qtbot, tmp_path: Path) -> None:
    """'+' always shows '+' text and 'Grow pane' tooltip across all states."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel
    for state in PanelState:
        panel.set_state(state)
        assert panel.maximize_button.text() == "+", f"failed at state {state}"
        assert panel.maximize_button.toolTip() == "Grow pane", f"failed at state {state}"


def test_panel_minus_button_fixed_text_and_tooltip(qtbot, tmp_path: Path) -> None:
    """'-' always shows '-' text and 'Shrink pane' tooltip across all states."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel
    for state in PanelState:
        panel.set_state(state)
        assert panel.minimize_button.text() == "-", f"failed at state {state}"
        assert panel.minimize_button.toolTip() == "Shrink pane", f"failed at state {state}"


def test_panel_plus_button_enabled_states(qtbot, tmp_path: Path) -> None:
    """'+' enabled for NORMAL/MINIMIZED/TEMPORARY_MINIMIZED; disabled for MAXIMIZED."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel

    panel.set_state(PanelState.NORMAL)
    assert panel.maximize_button.isEnabled()

    panel.set_state(PanelState.MINIMIZED)
    assert panel.maximize_button.isEnabled()

    panel.set_state(PanelState.TEMPORARY_MINIMIZED)
    assert panel.maximize_button.isEnabled()

    panel.set_state(PanelState.MAXIMIZED)
    assert not panel.maximize_button.isEnabled()


def test_panel_minus_button_enabled_states(qtbot, tmp_path: Path) -> None:
    """'-' enabled for MAXIMIZED/NORMAL; disabled for MINIMIZED/TEMPORARY_MINIMIZED."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel

    panel.set_state(PanelState.MAXIMIZED)
    assert panel.minimize_button.isEnabled()

    panel.set_state(PanelState.NORMAL)
    assert panel.minimize_button.isEnabled()

    panel.set_state(PanelState.MINIMIZED)
    assert not panel.minimize_button.isEnabled()

    panel.set_state(PanelState.TEMPORARY_MINIMIZED)
    assert not panel.minimize_button.isEnabled()


def test_panel_grow_local_transitions(qtbot, tmp_path: Path) -> None:
    """panel.grow() transitions: MINIMIZED→NORMAL, TEMP_MIN→NORMAL, NORMAL→MAXIMIZED, MAXIMIZED→no-op."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel

    # MINIMIZED → NORMAL
    panel.set_state(PanelState.MINIMIZED)
    panel.grow()
    assert panel.state == PanelState.NORMAL
    assert panel.expanded

    # NORMAL → MAXIMIZED
    panel.grow()
    assert panel.state == PanelState.MAXIMIZED
    assert panel.expanded

    # MAXIMIZED → no-op (grow does nothing when already maximized)
    panel.grow()
    assert panel.state == PanelState.MAXIMIZED

    # TEMPORARY_MINIMIZED → NORMAL
    panel.set_state(PanelState.TEMPORARY_MINIMIZED)
    panel.grow()
    assert panel.state == PanelState.NORMAL
    assert panel.expanded


def test_panel_shrink_local_transitions(qtbot, tmp_path: Path) -> None:
    """panel.shrink() transitions: MAXIMIZED→NORMAL, NORMAL→MINIMIZED, others no-op."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel

    # NORMAL → MINIMIZED
    panel.set_state(PanelState.NORMAL)
    panel.shrink()
    assert panel.state == PanelState.MINIMIZED
    assert panel.collapsed

    # MINIMIZED → no-op (shrink does nothing)
    panel.shrink()
    assert panel.state == PanelState.MINIMIZED

    # TEMPORARY_MINIMIZED → no-op
    panel.set_state(PanelState.TEMPORARY_MINIMIZED)
    panel.shrink()
    assert panel.state == PanelState.TEMPORARY_MINIMIZED

    # MAXIMIZED → NORMAL
    panel.set_state(PanelState.MAXIMIZED)
    panel.shrink()
    assert panel.state == PanelState.NORMAL
    assert panel.expanded


def test_panel_maximize_temp_minimizes_other_normal_panels(qtbot, tmp_path: Path) -> None:
    """_on_panel_grow on NORMAL → MAXIMIZED; other NORMAL panels become TEMPORARY_MINIMIZED."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    assert window.csv_panel.state == PanelState.NORMAL
    assert window.prompt_panel.state == PanelState.NORMAL
    assert window.description_panel.state == PanelState.NORMAL

    window._on_panel_grow(window.prompt_panel)

    assert window.prompt_panel.state == PanelState.MAXIMIZED
    assert window.csv_panel.state == PanelState.TEMPORARY_MINIMIZED
    assert window.description_panel.state == PanelState.TEMPORARY_MINIMIZED
    assert window.csv_panel.collapsed
    assert window.description_panel.collapsed


def test_panel_demaximize_restores_temp_minimized_panels(qtbot, tmp_path: Path) -> None:
    """_on_panel_shrink on MAXIMIZED → NORMAL; TEMPORARY_MINIMIZED panels restore to NORMAL."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    # Maximize, then demaximize
    window._on_panel_grow(window.prompt_panel)
    assert window.csv_panel.state == PanelState.TEMPORARY_MINIMIZED

    window._on_panel_shrink(window.prompt_panel)

    assert window.prompt_panel.state == PanelState.NORMAL
    assert window.csv_panel.state == PanelState.NORMAL
    assert window.description_panel.state == PanelState.NORMAL


def test_panel_already_minimized_unaffected_by_other_maximize(qtbot, tmp_path: Path) -> None:
    """Already MINIMIZED panels stay MINIMIZED when another panel is maximized."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    # Minimize CSV panel manually
    window._on_panel_shrink(window.csv_panel)
    assert window.csv_panel.state == PanelState.MINIMIZED

    # Maximize prompt panel – only NORMAL panels become TEMPORARY_MINIMIZED
    window._on_panel_grow(window.prompt_panel)

    assert window.csv_panel.state == PanelState.MINIMIZED  # unchanged
    assert window.prompt_panel.state == PanelState.MAXIMIZED
    assert window.description_panel.state == PanelState.TEMPORARY_MINIMIZED


def test_panel_temp_minimized_looks_like_minimized(qtbot, tmp_path: Path) -> None:
    """TEMPORARY_MINIMIZED: body hidden, '-' disabled, '+' enabled."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    panel = window.csv_panel

    panel.set_state(PanelState.TEMPORARY_MINIMIZED)

    assert panel.collapsed
    assert not panel.body_frame.isVisible()
    assert not panel.minimize_button.isEnabled()
    assert panel.maximize_button.isEnabled()


def test_panel_switch_maximized_via_shrink_then_grow(qtbot, tmp_path: Path) -> None:
    """Switching maximized panels: shrink current, grow desired one."""
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    # Maximize prompts panel
    window._on_panel_grow(window.prompt_panel)
    assert window.prompt_panel.state == PanelState.MAXIMIZED
    assert window.csv_panel.state == PanelState.TEMPORARY_MINIMIZED
    assert window.description_panel.state == PanelState.TEMPORARY_MINIMIZED

    # Demaximize prompts panel
    window._on_panel_shrink(window.prompt_panel)
    assert all(
        p.state == PanelState.NORMAL
        for p in (window.csv_panel, window.prompt_panel, window.description_panel)
    )

    # Maximize CSV panel instead
    window._on_panel_grow(window.csv_panel)
    assert window.csv_panel.state == PanelState.MAXIMIZED
    assert window.prompt_panel.state == PanelState.TEMPORARY_MINIMIZED
    assert window.description_panel.state == PanelState.TEMPORARY_MINIMIZED


def test_panel_grow_temp_minimized_restores_maximized_and_other_temp_min(
    qtbot, tmp_path: Path,
) -> None:
    """Grow (+) on a TEMPORARY_MINIMIZED panel restores MAXIMIZED→NORMAL and
    all TEMPORARY_MINIMIZED→NORMAL, leaving no panel maximized.

    Edge case: when one panel is MAXIMIZED and another is TEMPORARY_MINIMIZED,
    clicking '+' on the TEMPORARY_MINIMIZED panel (not the MAXIMIZED one)
    should:
    - Demaximize the MAXIMIZED sibling to NORMAL
    - Restore all TEMPORARY_MINIMIZED panels to NORMAL
    - Leave no panel in MAXIMIZED state
    """
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.sections_splitter.size().height() > 0)

    # Start: all NORMAL
    assert all(
        p.state == PanelState.NORMAL
        for p in (window.csv_panel, window.prompt_panel, window.description_panel)
    )

    # Grow prompt → MAXIMIZED; csv + description → TEMPORARY_MINIMIZED
    window._on_panel_grow(window.prompt_panel)
    assert window.prompt_panel.state == PanelState.MAXIMIZED
    assert window.csv_panel.state == PanelState.TEMPORARY_MINIMIZED
    assert window.description_panel.state == PanelState.TEMPORARY_MINIMIZED

    # Grow the TEMPORARY_MINIMIZED csv panel directly (no intermediate shrink)
    window._on_panel_grow(window.csv_panel)

    # csv_panel grew out of TEMP_MIN → NORMAL
    assert window.csv_panel.state == PanelState.NORMAL
    assert window.csv_panel.expanded

    # prompt_panel was MAXIMIZED → restored to NORMAL
    assert window.prompt_panel.state == PanelState.NORMAL
    assert window.prompt_panel.expanded

    # description_panel was TEMPORARY_MINIMIZED → restored to NORMAL
    assert window.description_panel.state == PanelState.NORMAL
    assert window.description_panel.expanded

    # No panel remains maximized
    assert not any(p.state == PanelState.MAXIMIZED for p in (
        window.csv_panel, window.prompt_panel, window.description_panel,
    ))


class TestKnowledgeBaseDirectoryUI:
    """UI-level tests for the knowledge-base directory feature."""

    def test_kb_manager_action_opens_manager_window(
        self, qtbot, tmp_path: Path,
    ) -> None:
        """Clicking the single Knowledge Base menu action opens the KB manager."""
        from product_description_tool.kb_window import KnowledgeBaseManager

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        # Initially no manager window exists
        assert window._kb_manager is None

        # Trigger the single KB action — must open the manager
        window.kb_manager_action.trigger()

        assert window._kb_manager is not None
        assert isinstance(window._kb_manager, KnowledgeBaseManager)
        assert window._kb_manager.isVisible()

    def test_kb_manager_action_raises_existing_window(
        self, qtbot, tmp_path: Path,
    ) -> None:
        """Triggering the action a second time reuses the existing window."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        window.kb_manager_action.trigger()
        first_manager = window._kb_manager

        window.kb_manager_action.trigger()
        # Same instance — not replaced
        assert window._kb_manager is first_manager

    def test_kb_on_directory_changed_updates_project_and_indicator(
        self, qtbot, tmp_path: Path,
    ) -> None:
        """The _on_kb_directory_changed slot updates project and label."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        kb_dir = tmp_path / "my_kb"
        kb_dir.mkdir()

        window._on_kb_directory_changed(str(kb_dir))

        assert window.project.knowledge_base_dir == str(kb_dir)
        assert window.kb_label.text() == f"KB: {kb_dir}"
        assert window.kb_label.toolTip() == str(kb_dir)
        assert window.isWindowModified()

    def test_kb_on_directory_cleared_updates_project_and_indicator(
        self, qtbot, tmp_path: Path,
    ) -> None:
        """Calling _on_kb_directory_changed('') clears the KB project field and label."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        # Set a KB dir first so there's something to clear
        kb_dir = tmp_path / "some_kb"
        kb_dir.mkdir()
        window.project.knowledge_base_dir = str(kb_dir)
        window._update_kb_indicator()
        window._set_project_modified(False)
        assert window.kb_label.text() != ""

        window._on_kb_directory_changed("")

        assert window.project.knowledge_base_dir is None
        assert window.kb_label.text() == ""
        assert window.kb_label.toolTip() == ""
        assert window.isWindowModified()

    def test_new_project_clears_kb_directory(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        # Set a KB directory first
        kb_dir = tmp_path / "existing_kb"
        kb_dir.mkdir()
        window.project.knowledge_base_dir = str(kb_dir)
        window._update_kb_indicator()
        assert window.kb_label.text() != ""

        message_box.set_response("warning", QMessageBox.StandardButton.Discard)

        window.new_project()

        message_box.reset()
        assert window.project.knowledge_base_dir is None
        assert window.kb_label.text() == ""

    def test_kb_directory_restored_on_open_project(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        from product_description_tool.project import Project, ProjectPrompt, ProjectRepository

        # Create and save a project with KB directory
        project_repo = ProjectRepository()
        kb_dir = tmp_path / "knowledge_base"
        kb_dir.mkdir()
        project = Project(
            prompts=[ProjectPrompt(output_field="desc", prompt="Process {{@help.md}} with {{sku}}")],
            knowledge_base_dir=str(kb_dir),
        )
        project_path = project_repo.save(tmp_path / "test.project.json", project)

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        file_dialog.set_response(
            "getOpenFileName",
            lambda *args, **kwargs: (str(project_path), "Project Files (*.project.json)"),
        )
        message_box.set_response("warning", QMessageBox.StandardButton.Discard)

        window.open_project()

        file_dialog.reset()
        message_box.reset()

        # There is no actual project_path set because open_project sets self.project_path = project_path
        # after loading. The KB directory should be restored.
        assert window.project.knowledge_base_dir is not None
        assert Path(window.project.knowledge_base_dir).resolve() == kb_dir.resolve()

    def test_validation_blocks_preview_when_kb_refs_exist_but_no_kb_dir(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="generated", prompt="Rewrite {{@help.md}} with {{sku}}")

        critical_messages = []
        original_critical = QMessageBox.critical

        @staticmethod
        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # The PromptRenderer.validate_template will detect KB refs with no KB dir
        # and raise KnowledgeBaseRefError, which _validate_ready_for_generation catches.
        result = window._validate_ready_for_generation(window._enabled_prompts())

        message_box.reset()
        assert not result
        assert len(critical_messages) == 1
        title, text = critical_messages[0]
        assert "Knowledge-base reference error" in title
        assert window.document.rows[1].get("generated", "") == ""
        assert window._worker_thread is None

    def test_validation_works_with_valid_kb_dir_and_file(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        # Set up KB directory with a referenced file
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        help_file = kb_dir / "help.md"
        help_file.write_text("Helpful content", encoding="utf-8")
        window.project.knowledge_base_dir = str(kb_dir)

        _add_prompt(window, output_field="generated", prompt="Rewrite {{@help.md}} with {{sku}}")

        # Validation should pass with valid KB dir and existing file
        result = window._validate_ready_for_generation(window._enabled_prompts())

        assert result
        assert not window._busy

    def test_validation_blocks_when_kb_dir_does_not_exist(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        # Set KB dir to a non-existent path
        window.project.knowledge_base_dir = str(tmp_path / "nonexistent_kb")
        _add_prompt(window, output_field="generated", prompt="Rewrite {{@help.md}} with {{sku}}")

        critical_messages = []
        original_critical = QMessageBox.critical

        @staticmethod
        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # Validation should fail because KB dir doesn't exist
        result = window._validate_ready_for_generation(window._enabled_prompts())

        message_box.reset()
        assert not result
        assert len(critical_messages) == 1
        title, text = critical_messages[0]
        assert "Knowledge-base reference error" in title
        assert window._worker_thread is None


# ── Prompt Attachment UI (Use Case 28) ────────────────────────────────────


class TestAttachmentMainWindowUI:
    """MainWindow-level tests for the prompt-attachments feature."""

    def test_attachment_count_label_shown_when_attachments_exist(self, qtbot, tmp_path):
        """The attachment count label shows the count when attachments are configured."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="sku"),
        ]
        window._update_attachment_summary()

        assert "1 attachment" in window.attachment_count_label.text().lower()

    def test_attachment_count_label_plural(self, qtbot, tmp_path):
        """Multiple attachments show plural 'attachments' in the label."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="sku"),
            PromptAttachment(source_type="csv_column", source="name"),
        ]
        window._update_attachment_summary()

        assert "2 attachments" in window.attachment_count_label.text().lower()

    def test_attachment_count_label_hidden_when_no_attachments(self, qtbot, tmp_path):
        """The attachment count label is empty when no attachments exist."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")
        window._update_attachment_summary()

        assert window.attachment_count_label.text() == ""

    def test_attachment_count_label_hidden_when_no_prompt(self, qtbot, tmp_path):
        """The attachment count label is empty when no prompt is selected."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        window._update_attachment_summary()
        assert window.attachment_count_label.text() == ""

    def test_attachments_button_enabled_with_prompt(self, qtbot, tmp_path):
        """The 'Attachments…' button is enabled when a prompt is selected."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")
        assert window.attachments_button.isEnabled()

    def test_attachments_button_disabled_without_prompt(self, qtbot, tmp_path):
        """The 'Attachments…' button is disabled when no prompt is selected."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert not window.attachments_button.isEnabled()

    def test_open_attachment_manager_updates_prompt_attachments(self, qtbot, tmp_path, monkeypatch):
        """Opening and confirming the attachment manager updates the prompt's attachments."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Monkeypatch AttachmentManager to return pre-set attachments
        class FakeAttachmentManager:
            def __init__(self, **kwargs):
                self._attachments = list(kwargs.get("attachments", []))

            def exec(self):
                from product_description_tool.project import PromptAttachment
                self._attachments = [
                    PromptAttachment(source_type="csv_column", source="sku"),
                ]
                return True  # accepted

            def get_attachments(self):
                return list(self._attachments)

        monkeypatch.setattr(
            "product_description_tool.main_window.AttachmentManager",
            FakeAttachmentManager,
        )

        window._open_attachment_manager()

        assert len(window.project.prompts[0].attachments) == 1
        assert window.project.prompts[0].attachments[0].source == "sku"

    def test_open_attachment_manager_cancel_does_not_modify(self, qtbot, tmp_path, monkeypatch):
        """Cancelling the attachment manager leaves the prompt's attachments unchanged."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Monkeypatch AttachmentManager to return False (cancel)
        class FakeAttachmentManager:
            def __init__(self, **kwargs):
                pass

            def exec(self):
                return False  # cancelled

            def get_attachments(self):
                return []

        monkeypatch.setattr(
            "product_description_tool.main_window.AttachmentManager",
            FakeAttachmentManager,
        )

        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="name"),
        ]
        window._set_project_modified(False)
        window._open_attachment_manager()

        # Attachments should be unchanged
        assert len(window.project.prompts[0].attachments) == 1
        assert window.project.prompts[0].attachments[0].source == "name"

    def test_validation_blocks_preview_with_invalid_column_attachment(self, qtbot, tmp_path, monkeypatch):
        """An invalid CSV-column attachment blocks preview with an error dialog."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Add an invalid column attachment
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="nonexistent_column"),
        ]

        critical_messages = []
        original_critical = QMessageBox.critical

        @staticmethod
        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        result = window._validate_ready_for_generation(window._enabled_prompts())

        message_box.reset()
        assert not result
        assert len(critical_messages) == 1
        assert "Invalid attachment" in critical_messages[0][0]

    def test_validation_passes_with_valid_column_attachment(self, qtbot, tmp_path, monkeypatch):
        """A valid CSV-column attachment passes validation."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Add a valid column attachment
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="sku"),
        ]

        result = window._validate_ready_for_generation(window._enabled_prompts())

        assert result

    def test_validation_blocks_with_invalid_kb_attachment_missing_file(self, qtbot, tmp_path, monkeypatch):
        """A KB-file attachment for a non-existent file blocks validation."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        window.project.knowledge_base_dir = str(kb_dir)

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="kb_file", source="missing.md"),
        ]

        critical_messages = []
        original_critical = QMessageBox.critical

        @staticmethod
        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        result = window._validate_ready_for_generation(window._enabled_prompts())

        message_box.reset()
        assert not result
        assert len(critical_messages) == 1

    def test_validation_passes_with_valid_kb_attachment(self, qtbot, tmp_path, monkeypatch):
        """A valid KB-file attachment passes validation."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "guide.md").write_text("Guide content", encoding="utf-8")
        window.project.knowledge_base_dir = str(kb_dir)

        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="kb_file", source="guide.md"),
        ]

        result = window._validate_ready_for_generation(window._enabled_prompts())

        assert result

    def test_preview_with_attachments_does_not_crash(self, qtbot, tmp_path, monkeypatch):
        """Previewing a row with valid attachments completes normally through FakeGenerationService."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()
        window.generation_service = FakeGenerationService()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Attach the sku column
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="sku"),
        ]

        window.table_view.selectRow(0)
        window.preview_selected_row()

        qtbot.waitUntil(lambda: window.document.rows[0]["desc"] != "")
        assert window.document.rows[0]["desc"] is not None

    def test_batch_processing_with_attachments_does_not_crash(self, qtbot, tmp_path, monkeypatch):
        """Batch processing with valid attachments completes normally through FakeGenerationService."""
        from product_description_tool.project import PromptAttachment

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()
        window.generation_service = FakeGenerationService()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)
        _add_prompt(window, output_field="desc", prompt="Write {{sku}}")

        # Attach the sku column
        window.project.prompts[0].attachments = [
            PromptAttachment(source_type="csv_column", source="sku"),
        ]

        window.process_all_rows()

        qtbot.waitUntil(lambda: window.document.rows[1]["desc"] != "")
        assert window.document.rows[0]["desc"] is not None
        assert window.document.rows[1]["desc"] is not None


# ── CSV Import/Export Settings Separation ──────────────────────────────────


class TestCsvImportExportSettings:
    """Tests for separated import/export CSV settings and first-import seeding."""

    def test_first_import_seeds_full_export_settings(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """First CSV import seeds *all* parsing settings into export: delimiter,
        quotechar, encoding, newline (AR-7)."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert window.project.csv.export_settings_initialized is False

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        assert window.project.csv.export_settings_initialized is True
        assert window.project.csv.export_settings.delimiter == ";"
        assert window.project.csv.export_settings.quotechar == '"'
        # encoding and newline must also be seeded after first import
        assert window.project.csv.export_settings.encoding in ("utf-8", "utf-8-sig")
        assert window.project.csv.export_settings.newline == "\n"

    def test_first_import_persists_full_import_settings(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """First CSV import persists the full detected contract into
        import_settings: encoding, delimiter, quotechar, newline (AR-6/AR-7)."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        assert window.project.csv.import_settings.delimiter == ";"
        assert window.project.csv.import_settings.quotechar == '"'
        assert window.project.csv.import_settings.encoding in ("utf-8", "utf-8-sig")
        assert window.project.csv.import_settings.newline == "\n"

    def test_subsequent_import_does_not_overwrite_export_settings(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """After first import, later imports must not silently overwrite export settings."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        # First import
        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        # Manually change export settings to something different
        window.project.csv.export_settings.delimiter = "|"
        window.project.csv.export_settings.quotechar = "'"
        window.project.csv.export_settings.encoding = "utf-16"
        window.project.csv.export_settings.newline = "\r\n"

        # Second import with a different file
        csv_path2 = tmp_path / "products2.csv"
        csv_path2.write_text("x,y\n1,2\n", encoding="utf-8")
        _patch_csv_dialog(monkeypatch, csv_path2)
        window.load_csv()

        # Export settings must retain the manually-set values
        assert window.project.csv.export_settings.delimiter == "|"
        assert window.project.csv.export_settings.quotechar == "'"
        assert window.project.csv.export_settings.encoding == "utf-16"
        assert window.project.csv.export_settings.newline == "\r\n"
        assert window.project.csv.export_settings_initialized is True

    def test_export_settings_initialized_after_first_import_only(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """Export settings initialized flag is set after first import."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert window.project.csv.export_settings_initialized is False

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        assert window.project.csv.export_settings_initialized is True

    def test_new_project_defaults_not_initialized(self, qtbot, tmp_path: Path) -> None:
        """Fresh project starts with export_settings_initialized = False."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert window.project.csv.export_settings_initialized is False

    def test_open_settings_preserves_import_settings(self, qtbot, tmp_path: Path, monkeypatch) -> None:
        """Opening and confirming settings preserves existing import settings."""
        monkeypatch.setattr(
            "product_description_tool.main_window.SettingsDialog",
            FakeSettingsDialog,
        )

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        # Set import settings to something distinct
        window.project.csv.import_settings.delimiter = "|"
        window.project.csv.import_settings.encoding = "latin-1"

        window.open_settings()

        # Import settings must not be overwritten by the settings dialog
        assert window.project.csv.import_settings.delimiter == "|"
        assert window.project.csv.import_settings.encoding == "latin-1"

    def test_open_settings_before_first_import_marks_export_initialized(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """Opening and confirming project settings *before* the first CSV import
        marks export settings as established, preventing the first import from
        silently overwriting the user's manually chosen export settings (AR-8)."""
        monkeypatch.setattr(
            "product_description_tool.main_window.SettingsDialog",
            FakeSettingsDialog,
        )

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert window.project.csv.export_settings_initialized is False

        # User opens Settings (before any import) and confirms
        window.open_settings()

        # Export settings must now be marked as established
        assert window.project.csv.export_settings_initialized is True

    def test_first_import_does_not_overwrite_manual_export_settings_after_settings(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """When export settings are marked as initialized (e.g., by having
        opened Settings), the first (or any subsequent) CSV import must not
        overwrite the export parsing settings with detected import values (AR-8)."""
        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        # Simulate: user explicitly set export settings via Settings.
        # Manually set distinct export settings and mark them initialized.
        window.project.csv.export_settings.delimiter = "|"
        window.project.csv.export_settings.quotechar = "'"
        window.project.csv.export_settings.encoding = "utf-16"
        window.project.csv.export_settings.newline = "\r\n"
        window.project.csv.export_settings_initialized = True

        # Now import a CSV — the first import.
        csv_path = _write_csv(tmp_path)
        _import_window_csv(window, monkeypatch, csv_path)

        # Export settings must retain the user-chosen values.
        assert window.project.csv.export_settings.delimiter == "|"
        assert window.project.csv.export_settings.quotechar == "'"
        assert window.project.csv.export_settings.encoding == "utf-16"
        assert window.project.csv.export_settings.newline == "\r\n"
        assert window.project.csv.export_settings_initialized is True

        # Import settings should reflect the detected file content.
        assert window.project.csv.import_settings.delimiter == ";"
        assert window.project.csv.import_settings.quotechar == '"'
        assert window.project.csv.import_settings.newline == "\n"

    def test_open_settings_updates_config_csv_export_settings_initialized(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """After confirming Settings, both project and app-config level
        export_settings_initialized must be True (AR-10)."""
        monkeypatch.setattr(
            "product_description_tool.main_window.SettingsDialog",
            FakeSettingsDialog,
        )

        window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
        qtbot.addWidget(window)
        window.show()

        assert window.project.csv.export_settings_initialized is False
        assert window.config.csv.export_settings_initialized is False

        window.open_settings()

        # Both project and app-config level must be marked as established
        assert window.project.csv.export_settings_initialized is True
        assert window.config.csv.export_settings_initialized is True

    def test_open_settings_persists_export_settings_initialized_after_restart(
        self, qtbot, tmp_path: Path, monkeypatch,
    ) -> None:
        """After confirming Settings, the app config is saved with
        export_settings_initialized=True, which survives ConfigStore
        save/load round-trip (AR-10 restart scenario)."""
        monkeypatch.setattr(
            "product_description_tool.main_window.SettingsDialog",
            FakeSettingsDialog,
        )

        store = ConfigStore(tmp_path / "config.json")
        window = MainWindow(config_store=store)
        qtbot.addWidget(window)
        window.show()

        # Open settings to establish export settings
        window.open_settings()

        # Config is already saved by open_settings; reload from disk.
        reloaded = store.load()

        # After restart, export_settings_initialized must be True
        assert reloaded.csv.export_settings_initialized is True
        # Export values from the fake dialog (semicolons) must be preserved
        assert reloaded.csv.export_settings.delimiter == ";"
        assert reloaded.csv.export_settings.quotechar == '"'
