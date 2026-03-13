from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QGroupBox

from product_description_tool.collapsible_panel import CollapsiblePanel
from product_description_tool.config import AppConfig, ConfigStore, FieldConfig
from product_description_tool.main_window import MainWindow


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

    def process_row(self, *, row_index, row, template, config):
        class Result:
            def __init__(self, row_index: int, content: str) -> None:
                self.row_index = row_index
                self.content = content

        return Result(row_index, f"<p>preview-{row['sku']}</p>")

    def process_rows(self, *, rows, template, config, on_result=None, should_cancel=None):
        results = []
        for index, row in enumerate(rows):
            if should_cancel is not None and should_cancel():
                break
            content = f"<p>batch-{row['sku']}</p>"
            result = self.process_row(
                row_index=index,
                row=row,
                template=template,
                config=config,
            )
            result.content = content
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results


class SlowCancellableGenerationService(FakeGenerationService):
    def process_rows(self, *, rows, template, config, on_result=None, should_cancel=None):
        results = []
        for index, row in enumerate(rows):
            QThread.msleep(50)
            if should_cancel is not None and should_cancel():
                break
            result = self.process_row(
                row_index=index,
                row=row,
                template=template,
                config=config,
            )
            result.content = f"<p>batch-{row['sku']}</p>"
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results


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


def _load_window_csv(window: MainWindow, monkeypatch, csv_path: Path) -> None:
    _patch_csv_dialog(monkeypatch, csv_path)
    window.load_csv()


def test_loading_and_selecting_row_updates_previews(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"

    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)

    window.table_view.selectRow(1)
    qtbot.waitUntil(lambda: window.last_original_preview_html == "<p>Beta 1</p>")
    qtbot.waitUntil(lambda: window.table_view.viewport().width() > 0)

    assert window.last_result_preview_html == ""
    assert "Files" not in [group.title() for group in window.findChildren(QGroupBox)]
    total_width = sum(window.table_view.columnWidth(index) for index in range(window.proxy_model.columnCount()))
    assert total_width <= window.table_view.viewport().width() + 4


def test_window_title_tracks_current_document_and_dirty_state(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)

    assert str(csv_path) in window.windowTitle()
    assert not window.isWindowModified()

    window.document.rows[0]["generated"] = "<p>Changed</p>"
    window._set_document_modified(True)

    assert window.isWindowModified()

    save_path = tmp_path / "saved.csv"
    monkeypatch.setattr(
        "product_description_tool.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(save_path), "CSV Files (*.csv)"),
    )
    window.save_csv(save_as=True)

    assert not window.isWindowModified()
    assert str(save_path) in window.windowTitle()


def test_edit_selected_description_updates_model(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("product_description_tool.main_window.HtmlEditorDialog", FakeDialog)
    FakeDialog.next_text = "<p>Updated</p>"

    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)

    window.edit_selected_description("description")

    assert window.document is not None
    assert window.document.rows[0]["description"] == "<p>Updated</p>"
    assert window.last_original_preview_html == "<p>Updated</p>"


def test_preview_selected_updates_only_current_row(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)
    window.prompt_edit.setPlainText("Rewrite {{sku}}")

    window.table_view.selectRow(1)
    window.preview_selected_row()

    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>preview-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>Existing</p>"


def test_process_all_overwrites_every_row(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)
    window.prompt_edit.setPlainText("Rewrite {{sku}}")

    window.process_all_rows()

    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>batch-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>batch-A-1</p>"


def test_filters_do_not_change_underlying_processing_scope(qtbot, tmp_path: Path, monkeypatch) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    window.generation_service = FakeGenerationService()
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)
    window.prompt_edit.setPlainText("Rewrite {{sku}}")

    window.filter_patterns = {"sku": "A-*"}
    window.proxy_model.set_filter_pattern(0, "A-*")
    window._update_filter_button_text()

    assert window.proxy_model.rowCount() == 1

    window.process_all_rows()

    qtbot.waitUntil(lambda: window.document.rows[1]["generated"] == "<p>batch-B-2</p>")
    assert window.document.rows[0]["generated"] == "<p>batch-A-1</p>"
    assert window.filter_button.text() == "Filter (1)"


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
    window.config.csv.result_description = "generated"
    window.generation_service = SlowCancellableGenerationService()
    csv_path = _write_csv(tmp_path, row_count=5)
    _load_window_csv(window, monkeypatch, csv_path)
    window.prompt_edit.setPlainText("Rewrite {{sku}}")

    window.process_all_rows()
    qtbot.waitUntil(lambda: window._progress_dialog is not None)
    qtbot.waitUntil(lambda: window.document.rows[0]["generated"] == "<p>batch-A-1</p>")

    window._cancel_processing()

    qtbot.waitUntil(lambda: window._worker_thread is None)
    assert window.status.currentMessage() == "Processing cancelled"
    assert window.document.rows[-1]["generated"] == ""


def test_open_settings_updates_table_and_preserves_selected_row(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("product_description_tool.main_window.SettingsDialog", FakeSettingsDialog)

    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()
    window.config.csv.result_description = "generated"
    csv_path = _write_csv(tmp_path)
    _load_window_csv(window, monkeypatch, csv_path)
    window.table_view.selectRow(1)

    window.open_settings()

    qtbot.waitUntil(lambda: window._selected_source_row() == 1)
    assert window.table_model.visible_headers == ["description", "generated"]
    assert window.table_model.headerData(0, Qt.Orientation.Horizontal) == "Product Description"


def test_open_settings_persists_updated_config_on_ok(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("product_description_tool.main_window.SettingsDialog", FakeSettingsDialog)
    config_path = tmp_path / "config.json"

    window = MainWindow(config_store=ConfigStore(config_path))
    qtbot.addWidget(window)
    window.show()
    window.open_settings()

    persisted = ConfigStore(config_path).load()
    assert persisted.csv.delimiter == ";"
    assert persisted.csv.quotechar == '"'
    assert persisted.csv.fields["description"].label == "Product Description"


def test_main_window_uses_three_collapsible_panels_with_equal_initial_sizes(qtbot, tmp_path: Path) -> None:
    window = MainWindow(config_store=ConfigStore(tmp_path / "config.json"))
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.sections_splitter.sizes()[0] > 0)
    panels = [window.csv_panel, window.prompt_panel, window.description_panel]

    assert [panel.title for panel in panels] == ["CSV Data", "System Prompt", "Description"]
    sizes = window.sections_splitter.sizes()
    assert max(sizes) - min(sizes) <= 40

    window.prompt_panel.set_expanded(False)
    qtbot.waitUntil(lambda: not window.prompt_panel.content.isVisible())

    collapsed_sizes = window.sections_splitter.sizes()
    assert collapsed_sizes[1] < collapsed_sizes[0]
    assert collapsed_sizes[1] < collapsed_sizes[2]
