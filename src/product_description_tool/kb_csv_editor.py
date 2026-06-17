from __future__ import annotations

import csv
import io
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from product_description_tool.kb_editor import open_external


def _detect_csv_dialect(content: str) -> dict[str, str]:
    """Heuristically detect CSV delimiter for a given text content.

    Tries common delimiters (comma, semicolon, tab, pipe) and returns the one
    that produces the most consistent column count across non‑empty rows.
    Falls back to comma when nothing yields a usable parse.
    """
    candidates = [",", ";", "\t", "|"]
    best_delim = ","
    best_score = 0

    for delim in candidates:
        try:
            reader = csv.reader(io.StringIO(content), delimiter=delim)
            rows: list[list[str]] = []
            for row in reader:
                # Skip rows that are completely empty
                if any(cell.strip() for cell in row):
                    rows.append(row)
            if len(rows) <= 1:
                continue
            col_counts = [len(row) for row in rows]
            min_cols = min(col_counts)
            max_cols = max(col_counts)
            # Consistency: prefer small variance and more columns
            score = max_cols
            if max_cols != min_cols:
                score -= (max_cols - min_cols)
            if score > best_score:
                best_delim = delim
                best_score = score
        except Exception:  # noqa: BLE001
            continue

    return {"delimiter": best_delim, "quotechar": '"'}


class CsvEditorDialog(QDialog):
    """Modal dialog for editing a CSV file in a spreadsheet-like grid.

    Heuristically detects the CSV dialect on open and preserves the
    detected delimiter and quote character when saving.  The user may
    edit existing cells, add or remove rows, add or remove columns,
    then Save or Cancel.
    """

    def __init__(self, file_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._headers: list[str] = []
        self._rows: list[list[str]] = []
        self._delimiter = ","
        self._quotechar = '"'

        self.setWindowTitle(f"Edit CSV: {file_path.name}")
        self.resize(800, 500)
        self.setModal(True)

        if not self._load_file():
            self.reject()
            return
        self._build_ui()

    def _load_file(self) -> bool:
        """Read the CSV file with heuristic dialect detection.

        Returns True on success, False on failure.
        """
        try:
            content = self._file_path.read_text(encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Read failed",
                f"Could not read '{self._file_path}':\n{exc}",
            )
            return False

        dialect = _detect_csv_dialect(content)
        self._delimiter = dialect["delimiter"]
        self._quotechar = dialect["quotechar"]
        reader = csv.DictReader(
            io.StringIO(content),
            delimiter=self._delimiter,
            quotechar=self._quotechar,
        )
        self._headers = list(reader.fieldnames or [])
        self._rows = [
            [row.get(h, "") for h in self._headers]
            for row in reader
        ]
        return True

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(len(self._rows), len(self._headers))
        self._table.setHorizontalHeaderLabels(self._headers)
        self._table.verticalHeader().setVisible(True)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )

        for row_idx, row_data in enumerate(self._rows):
            for col_idx, cell in enumerate(row_data):
                item = QTableWidgetItem(cell)
                self._table.setItem(row_idx, col_idx, item)

        layout.addWidget(self._table, 1)

        # -- Row / Column editing buttons ---------------------------------
        grid_actions = QHBoxLayout()

        self._add_row_button = QPushButton("Add Row")
        self._add_row_button.clicked.connect(self._add_row)
        grid_actions.addWidget(self._add_row_button)

        self._remove_row_button = QPushButton("Remove Row")
        self._remove_row_button.clicked.connect(self._remove_row)
        grid_actions.addWidget(self._remove_row_button)

        grid_actions.addStretch(1)

        self._add_column_button = QPushButton("Add Column")
        self._add_column_button.clicked.connect(self._add_column)
        grid_actions.addWidget(self._add_column_button)

        self._remove_column_button = QPushButton("Remove Column")
        self._remove_column_button.clicked.connect(self._remove_column)
        grid_actions.addWidget(self._remove_column_button)

        layout.addLayout(grid_actions)

        # -- Save / Cancel / External -------------------------------------
        button_layout = QHBoxLayout()

        self._external_button = QPushButton("Open Externally")
        self._external_button.clicked.connect(
            lambda: open_external(str(self._file_path)),
        )
        button_layout.addWidget(self._external_button)

        button_layout.addStretch(1)

        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_file)
        button_layout.addWidget(self._save_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Row operations
    # ------------------------------------------------------------------

    def _add_row(self) -> None:
        """Append a new empty row to the table."""
        row_count = self._table.rowCount()
        self._table.insertRow(row_count)
        for col in range(self._table.columnCount()):
            self._table.setItem(row_count, col, QTableWidgetItem(""))

    def _remove_row(self) -> None:
        """Remove the selected row (first selected)."""
        current_row = self._table.currentRow()
        if current_row < 0:
            QMessageBox.information(
                self, "No row selected", "Select a row to remove first.",
            )
            return
        self._table.removeRow(current_row)

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    def _add_column(self) -> None:
        """Add a new column, prompting for its header name."""
        name, accepted = QInputDialog.getText(
            self,
            "New Column",
            "Column header name:",
        )
        if not accepted or not (name := name.strip()):
            return
        # Disallow duplicate headers
        existing_headers = [
            self._table.horizontalHeaderItem(c).text()
            for c in range(self._table.columnCount())
            if self._table.horizontalHeaderItem(c)
        ]
        if name in existing_headers:
            QMessageBox.warning(
                self,
                "Duplicate header",
                f"A column named '{name}' already exists.",
            )
            return
        col_count = self._table.columnCount()
        self._table.insertColumn(col_count)
        self._table.setHorizontalHeaderItem(col_count, QTableWidgetItem(name))
        # Fill new cells with empty strings
        for row in range(self._table.rowCount()):
            self._table.setItem(row, col_count, QTableWidgetItem(""))

    def _remove_column(self) -> None:
        """Remove the selected column (first selected)."""
        current_col = self._table.currentColumn()
        if current_col < 0:
            QMessageBox.information(
                self,
                "No column selected",
                "Select a column to remove first.",
            )
            return
        header = (
            self._table.horizontalHeaderItem(current_col).text()
            if self._table.horizontalHeaderItem(current_col)
            else f"column {current_col}"
        )
        answer = QMessageBox.question(
            self,
            "Remove column",
            f"Remove column '{header}' and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._table.removeColumn(current_col)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_file(self) -> None:
        """Write the table contents back to the CSV file.

        Uses the delimiter and quote character that were heuristically
        detected when the file was opened.
        """
        try:
            with self._file_path.open("w", encoding="utf-8-sig", newline="") as f:
                headers = [
                    (self._table.horizontalHeaderItem(c).text()
                     if self._table.horizontalHeaderItem(c)
                     else "")
                    for c in range(self._table.columnCount())
                ]
                writer = csv.writer(
                    f,
                    delimiter=self._delimiter,
                    quotechar=self._quotechar,
                    quoting=csv.QUOTE_MINIMAL,
                )
                writer.writerow(headers)
                for row_idx in range(self._table.rowCount()):
                    row_data = [
                        (self._table.item(row_idx, col_idx).text()
                         if self._table.item(row_idx, col_idx)
                         else "")
                        for col_idx in range(self._table.columnCount())
                    ]
                    writer.writerow(row_data)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Save failed",
                f"Could not write '{self._file_path}':\n{exc}",
            )
            return
        self.accept()
