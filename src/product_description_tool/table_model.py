from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from product_description_tool.config import CsvConfig
from product_description_tool.csv_repository import CsvDocument


class CsvTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._document: CsvDocument | None = None
        self._config = CsvConfig()
        self._visible_headers: list[str] = []

    @property
    def document(self) -> CsvDocument | None:
        return self._document

    @property
    def visible_headers(self) -> list[str]:
        return list(self._visible_headers)

    def set_document(self, document: CsvDocument | None, config: CsvConfig) -> None:
        self.beginResetModel()
        self._document = document
        self._config = config
        self._visible_headers = self._compute_visible_headers()
        self.endResetModel()

    def update_config(self, config: CsvConfig) -> None:
        self.beginResetModel()
        self._config = config
        self._visible_headers = self._compute_visible_headers()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._document is None:
            return 0
        return len(self._document.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._visible_headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or self._document is None:
            return None
        row = self._document.rows[index.row()]
        header = self._visible_headers[index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return row.get(header, "")
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section >= len(self._visible_headers):
                return None
            header = self._visible_headers[section]
            field_config = self._config.fields.get(header)
            return field_config.label or header if field_config else header
        return str(section + 1)

    def row_data(self, row_index: int) -> dict[str, str]:
        if self._document is None:
            return {}
        return self._document.rows[row_index]

    def set_cell(self, row_index: int, header: str, value: str) -> None:
        if self._document is None:
            return
        self._document.rows[row_index][header] = value
        if header in self._visible_headers:
            column_index = self._visible_headers.index(header)
            top_left = self.index(row_index, column_index)
            self.dataChanged.emit(top_left, top_left, [Qt.ItemDataRole.DisplayRole])

    def refresh_row(self, row_index: int) -> None:
        if self._document is None or not self._visible_headers:
            return
        self.dataChanged.emit(
            self.index(row_index, 0),
            self.index(row_index, len(self._visible_headers) - 1),
            [Qt.ItemDataRole.DisplayRole],
        )

    def _compute_visible_headers(self) -> list[str]:
        if self._document is None:
            return []
        visible = []
        for header in self._document.headers:
            field_config = self._config.fields.get(header)
            if field_config is None or field_config.show:
                visible.append(header)
        return visible
