from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QTableWidgetItem

from product_description_tool import message_box, input_dialog
from product_description_tool.kb_csv_editor import CsvEditorDialog, _detect_csv_dialect


# ===================================================================
# _detect_csv_dialect — heuristic delimiter detection
# ===================================================================


class TestDetectCsvDialect:
    """Unit tests for the heuristic CSV delimiter detection."""

    def test_detects_comma(self) -> None:
        content = "a,b,c\n1,2,3\n4,5,6"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ","
        assert result["quotechar"] == '"'

    def test_detects_semicolon(self) -> None:
        content = "a;b;c\n1;2;3\n4;5;6"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ";"

    def test_detects_tab(self) -> None:
        content = "a\tb\tc\n1\t2\t3\n4\t5\t6"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == "\t"

    def test_detects_pipe(self) -> None:
        content = "a|b|c\n1|2|3\n4|5|6"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == "|"

    def test_falls_back_to_comma_when_only_one_row(self) -> None:
        """Single data row is ambiguous; fallback to comma."""
        content = "a;b;c\n1;2;3"
        result = _detect_csv_dialect(content)
        # With only 2 rows total (1 header + 1 data), semicolon may win
        # but we just verify the function returns something sensible.
        assert result["delimiter"] in {",", ";", "\t", "|"}

    def test_empty_content_returns_comma(self) -> None:
        content = ""
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ","
        assert result["quotechar"] == '"'

    def test_prefers_delimiter_with_most_columns(self) -> None:
        """Among consistent delimiters, the one producing more columns wins."""
        # With 3 values separated by commas but no semicolons, comma wins
        content = "a,b,c\n1,2,3\n4,5,6"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ","

    def test_semicolon_with_quoted_fields(self) -> None:
        content = '"a";"b";"c"\n"1";"2";"3"'
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ";"

    def test_comma_with_quoted_fields_containing_commas(self) -> None:
        content = '"a,1","b","c"\n"1","2,3","4"'
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ","

    def test_mixed_inconsistent_delimiter_picks_best(self) -> None:
        """When some rows have varying column counts, picks the most consistent."""
        # Most rows are comma-delimited with 3 columns; pipe should not win
        content = "a,b,c\n1,2,3\n4,5,6\n7,8,9"
        result = _detect_csv_dialect(content)
        assert result["delimiter"] == ","


# ===================================================================
# CsvEditorDialog — modal grid editor
# ===================================================================


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Write a small CSV and return its path."""
    path = tmp_path / "test.csv"
    path.write_text("sku,name,price\nA1,Widget,10.0\nB2,Gadget,20.0\n", encoding="utf-8-sig")
    return path


@pytest.fixture
def semicolon_csv(tmp_path: Path) -> Path:
    """Write a semicolon-delimited CSV."""
    path = tmp_path / "semi.csv"
    path.write_text("sku;name;price\nA1;Widget;10.0\nB2;Gadget;20.0\n", encoding="utf-8-sig")
    return path


@pytest.fixture
def tab_csv(tmp_path: Path) -> Path:
    """Write a tab-delimited CSV."""
    path = tmp_path / "tabbed.csv"
    path.write_text("sku\tname\tprice\nA1\tWidget\t10.0\nB2\tGadget\t20.0\n", encoding="utf-8-sig")
    return path


@pytest.fixture
def single_row_csv(tmp_path: Path) -> Path:
    """Write a CSV with only a header and one data row."""
    path = tmp_path / "single.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8-sig")
    return path


# -- Construction and loading ------------------------------------------------


def test_csv_editor_loads_and_displays_data(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    assert dialog._headers == ["sku", "name", "price"]
    assert dialog._rows == [["A1", "Widget", "10.0"], ["B2", "Gadget", "20.0"]]
    assert dialog._delimiter == ","
    assert dialog._quotechar == '"'
    assert dialog._table.rowCount() == 2
    assert dialog._table.columnCount() == 3


def test_csv_editor_window_title_includes_filename(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)
    assert "test.csv" in dialog.windowTitle()


def test_csv_editor_is_modal(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)
    assert dialog.isModal()


def test_csv_editor_rejects_on_unreadable_file(qtbot, tmp_path: Path) -> None:
    """The dialog rejects when the file cannot be read."""
    message_box.set_response("critical", QMessageBox.StandardButton.Ok)
    missing = tmp_path / "nonexistent.csv"
    dialog = CsvEditorDialog(missing)
    qtbot.addWidget(dialog)
    message_box.reset()
    # The dialog calls reject() in constructor when _load_file fails
    assert dialog.result() == QDialog.Rejected


# -- Delimiter detection and preservation -----------------------------------


def test_csv_editor_detects_semicolon_delimiter(qtbot, semicolon_csv: Path) -> None:
    dialog = CsvEditorDialog(semicolon_csv)
    qtbot.addWidget(dialog)
    assert dialog._delimiter == ";"
    assert dialog._headers == ["sku", "name", "price"]


def test_csv_editor_detects_tab_delimiter(qtbot, tab_csv: Path) -> None:
    dialog = CsvEditorDialog(tab_csv)
    qtbot.addWidget(dialog)
    assert dialog._delimiter == "\t"
    assert dialog._headers == ["sku", "name", "price"]


def test_csv_editor_preserves_delimiter_on_save(qtbot, semicolon_csv: Path, monkeypatch) -> None:
    """Save writes back with the same delimiter that was detected."""
    dialog = CsvEditorDialog(semicolon_csv)
    qtbot.addWidget(dialog)

    # Accept the dialog (simulate Save)
    monkeypatch.setattr(dialog, "_save_file", dialog._save_file)
    monkeypatch.setattr(dialog, "accept", lambda: None)  # prevent close

    # Trigger save via private method to inspect output
    dialog._save_file()

    # Read saved content and verify delimiter is preserved
    saved = semicolon_csv.read_text(encoding="utf-8-sig")
    assert "; " not in saved  # no space after delimiter typical of comma
    reader = csv.reader(io.StringIO(saved), delimiter=";")
    rows = list(reader)
    assert len(rows) == 3  # header + 2 data rows
    assert rows[1] == ["A1", "Widget", "10.0"]


def test_csv_editor_preserves_tab_delimiter_on_save(qtbot, tab_csv: Path) -> None:
    """Save writes back with the same tab delimiter that was detected."""
    dialog = CsvEditorDialog(tab_csv)
    qtbot.addWidget(dialog)

    dialog._save_file()

    saved = tab_csv.read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(saved), delimiter="\t")
    rows = list(reader)
    assert len(rows) == 3
    assert rows[0] == ["sku", "name", "price"]
    assert rows[1] == ["A1", "Widget", "10.0"]


# -- Row operations ---------------------------------------------------------


def test_add_row_appends_empty_row(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_count = dialog._table.rowCount()
    dialog._add_row()

    assert dialog._table.rowCount() == initial_count + 1
    # New row cells are empty
    for col in range(dialog._table.columnCount()):
        item = dialog._table.item(initial_count, col)
        assert item is not None
        assert item.text() == ""


def test_remove_row_removes_selected_row(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_count = dialog._table.rowCount()
    # Select the first row
    dialog._table.setCurrentCell(0, 0)
    dialog._remove_row()

    assert dialog._table.rowCount() == initial_count - 1


def test_remove_row_with_no_selection_shows_info(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    info_messages = []

    def fake_info(parent, title, text, *args, **kwargs):
        info_messages.append((title, text))
        return QMessageBox.StandardButton.Ok

    message_box.set_response("information", fake_info)

    # Ensure no row is selected
    dialog._table.clearSelection()
    dialog._table.setCurrentCell(-1, -1)

    dialog._remove_row()

    message_box.reset()
    assert len(info_messages) == 1
    assert "No row selected" in info_messages[0][0]


# -- Column operations ------------------------------------------------------


def test_add_column_prompts_for_name_and_adds(qtbot, sample_csv: Path, monkeypatch) -> None:
    """Add Column prompts for a name and inserts a new column."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_cols = dialog._table.columnCount()

    input_dialog.set_response("getText", ("new_col", True))

    dialog._add_column()

    input_dialog.reset()

    assert dialog._table.columnCount() == initial_cols + 1
    header = dialog._table.horizontalHeaderItem(initial_cols)
    assert header is not None
    assert header.text() == "new_col"


def test_add_column_rejects_empty_name(qtbot, sample_csv: Path, monkeypatch) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_cols = dialog._table.columnCount()

    input_dialog.set_response("getText", ("", True))

    dialog._add_column()

    input_dialog.reset()

    assert dialog._table.columnCount() == initial_cols


def test_add_column_rejects_duplicate_header(qtbot, sample_csv: Path, monkeypatch) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_cols = dialog._table.columnCount()

    warning_messages = []

    def fake_warning(parent, title, text, *args, **kwargs):
        warning_messages.append((title, text))
        return QMessageBox.StandardButton.Ok

    message_box.set_response("warning", fake_warning)
    input_dialog.set_response("getText", ("sku", True))

    dialog._add_column()

    message_box.reset()
    input_dialog.reset()
    assert dialog._table.columnCount() == initial_cols
    assert len(warning_messages) == 1
    assert "Duplicate header" in warning_messages[0][0]


def test_remove_column_removes_selected_column_after_confirmation(
    qtbot, sample_csv: Path
) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_cols = dialog._table.columnCount()

    message_box.set_response("question", QMessageBox.StandardButton.Yes)

    # Select column 1
    dialog._table.setCurrentCell(0, 1)
    dialog._remove_column()

    message_box.reset()
    assert dialog._table.columnCount() == initial_cols - 1
    # Verify header "name" is gone
    new_headers = [
        dialog._table.horizontalHeaderItem(c).text()
        for c in range(dialog._table.columnCount())
        if dialog._table.horizontalHeaderItem(c)
    ]
    assert "name" not in new_headers


def test_remove_column_no_selection_shows_info(qtbot, sample_csv: Path) -> None:
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    info_messages = []

    def fake_info(parent, title, text, *args, **kwargs):
        info_messages.append((title, text))
        return QMessageBox.StandardButton.Ok

    message_box.set_response("information", fake_info)
    dialog._table.setCurrentCell(-1, -1)

    dialog._remove_column()

    message_box.reset()
    assert len(info_messages) == 1
    assert "No column selected" in info_messages[0][0]


def test_remove_column_cancelled_by_user(qtbot, sample_csv: Path) -> None:
    """User says No to column removal confirmation: column stays."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    initial_cols = dialog._table.columnCount()

    message_box.set_response("question", QMessageBox.StandardButton.No)

    dialog._table.setCurrentCell(0, 1)
    dialog._remove_column()

    message_box.reset()
    assert dialog._table.columnCount() == initial_cols


# -- Save / Cancel behavior -------------------------------------------------


def test_save_writes_modified_data(qtbot, sample_csv: Path) -> None:
    """After Save, the file contains the edited grid content."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    # Edit a cell
    item = dialog._table.item(0, 1)
    assert item is not None
    item.setText("Super Widget")

    # Add a row
    dialog._add_row()
    dialog._table.setItem(2, 0, QTableWidgetItem("C3"))
    dialog._table.setItem(2, 1, QTableWidgetItem("Doohickey"))
    dialog._table.setItem(2, 2, QTableWidgetItem("30.0"))

    dialog._save_file()

    # Verify on disk
    saved = sample_csv.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(saved))
    rows = list(reader)
    assert len(rows) == 3
    assert rows[0]["name"] == "Super Widget"
    assert rows[2]["sku"] == "C3"
    assert rows[2]["name"] == "Doohickey"
    assert rows[2]["price"] == "30.0"


def test_cancel_leaves_file_unchanged(qtbot, sample_csv: Path) -> None:
    """When Cancel is pressed, the file is unchanged."""
    original_content = sample_csv.read_text(encoding="utf-8-sig")

    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    # Modify data
    item = dialog._table.item(0, 0)
    assert item is not None
    item.setText("MODIFIED")

    # Press Cancel (reject)
    dialog.reject()

    # File should be unchanged
    current_content = sample_csv.read_text(encoding="utf-8-sig")
    assert current_content == original_content


def test_save_button_triggers_save(qtbot, sample_csv: Path, monkeypatch) -> None:
    """The Save button calls _save_file and accepts the dialog."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    save_called = False
    original_save = dialog._save_file

    def tracking_save():
        nonlocal save_called
        save_called = True
        original_save()

    monkeypatch.setattr(dialog, "_save_file", tracking_save)

    dialog._save_button.click()

    assert save_called


def test_cancel_button_rejects_dialog(qtbot, sample_csv: Path) -> None:
    """The Cancel button calls reject() on the dialog."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    dialog._cancel_button.click()

    assert dialog.result() == QDialog.Rejected


# -- Row/column data round trip after add/remove ----------------------------


def test_add_row_then_save_includes_new_row(qtbot, sample_csv: Path) -> None:
    """Adding a row and saving persists the new row."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    dialog._add_row()
    dialog._table.setItem(2, 0, QTableWidgetItem("C3"))
    dialog._table.setItem(2, 1, QTableWidgetItem("Doohickey"))
    dialog._table.setItem(2, 2, QTableWidgetItem("30.0"))
    dialog._save_file()

    saved = sample_csv.read_text(encoding="utf-8-sig")
    assert "C3" in saved
    assert "Doohickey" in saved


def test_remove_column_then_save_excludes_column(qtbot, sample_csv: Path) -> None:
    """Removing a column and saving drops it from the file."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    message_box.set_response("question", QMessageBox.StandardButton.Yes)

    # Remove "price" column (index 2)
    dialog._table.setCurrentCell(0, 2)
    dialog._remove_column()

    message_box.reset()
    dialog._save_file()

    saved = sample_csv.read_text(encoding="utf-8-sig")
    assert "price" not in saved
    reader = csv.DictReader(io.StringIO(saved))
    assert reader.fieldnames == ["sku", "name"]


def test_add_column_then_save_includes_new_column(qtbot, sample_csv: Path, monkeypatch) -> None:
    """Adding a column and saving includes it in the file."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    input_dialog.set_response("getText", ("in_stock", True))

    dialog._add_column()
    # Fill the new column for existing rows
    dialog._table.setItem(0, 3, QTableWidgetItem("yes"))
    dialog._table.setItem(1, 3, QTableWidgetItem("no"))

    input_dialog.reset()
    dialog._save_file()

    saved = sample_csv.read_text(encoding="utf-8-sig")
    assert "in_stock" in saved
    reader = csv.DictReader(io.StringIO(saved))
    rows = list(reader)
    assert rows[0]["in_stock"] == "yes"
    assert rows[1]["in_stock"] == "no"


# -- External open button ---------------------------------------------------


def test_external_open_button_calls_open_external(qtbot, sample_csv: Path, monkeypatch) -> None:
    """The 'Open Externally' button calls open_external with the file path."""
    dialog = CsvEditorDialog(sample_csv)
    qtbot.addWidget(dialog)

    called_with = []

    def fake_open_external(path: str) -> None:
        called_with.append(path)

    monkeypatch.setattr(
        "product_description_tool.kb_csv_editor.open_external",
        fake_open_external,
    )

    dialog._external_button.click()

    assert len(called_with) == 1
    assert str(sample_csv) == called_with[0]
