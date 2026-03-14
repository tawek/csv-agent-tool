from pathlib import Path

import pytest
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QGroupBox, QMessageBox

from product_description_tool.config import AppConfig, ConfigStore, FieldConfig
from product_description_tool.generation import USER_PROMPT
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
    def validate_template(self, template: str, headers: list[str]) -> None:
        return None

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

    def exec(self) -> bool:
        return True

    def get_config(self):
        return self._config


@pytest.fixture(autouse=True)
def _auto_discard_unsaved_changes(monkeypatch) -> None:
    def fake_warning(*args, **kwargs):
        title = args[1] if len(args) > 1 else kwargs.get("title", "")
        if title == "Unsaved changes":
            return QMessageBox.StandardButton.Discard
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("product_description_tool.main_window.QMessageBox.warning", fake_warning)


def _write_csv(tmp_path: Path, row_count: int = 2) -> Path:
    csv_path = tmp_path / "products.csv"
    rows = ['A-1,"<p>Alpha</p>","<p>Existing</p>"']
    for index in range(1, row_count):
        rows.append(f'B-{index + 1},"<p>Beta {index}</p>",""')
    csv_path.write_text(
        "sku,description,generated\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return csv_path


def _patch_csv_dialog(monkeypatch, csv_path: Path) -> None:
    monkeypatch.setattr(
        "product_description_tool.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"),
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
    window._update_preview_field_selectors(preserve_selection=True)


def test_loading_and_selecting_row_updates_previews(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    csv_path = _write_csv(tmp_path)
    _import_window_csv(window, monkeypatch, csv_path)

    assert window.right_field_combo.currentText() == "sku"

    window.table_view.selectRow(1)
    qtbot.waitUntil(lambda: window.last_original_preview_html == "<p>Beta 1</p>")
    qtbot.waitUntil(lambda: window.table_view.viewport().width() > 0)

    assert window.last_result_preview_html == "B-2"
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
    monkeypatch.setattr(
        "product_description_tool.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(project_path), "Project Files (*.project.json)"),
    )
    assert window.save_project(save_as=True)
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

    monkeypatch.setattr(
        "product_description_tool.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    window.process_all_rows()

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
