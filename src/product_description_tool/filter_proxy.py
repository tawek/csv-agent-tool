from __future__ import annotations

import fnmatch

from PySide6.QtCore import QSortFilterProxyModel


class WildcardFilterProxyModel(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self._filters: dict[int, str] = {}

    def set_filter_pattern(self, column: int, pattern: str) -> None:
        pattern = pattern.strip()
        if pattern:
            self._filters[column] = pattern
        else:
            self._filters.pop(column, None)
        self.invalidateFilter()

    def clear_filters(self) -> None:
        self._filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        for column, pattern in self._filters.items():
            source_index = model.index(source_row, column, source_parent)
            value = str(model.data(source_index) or "")
            if not fnmatch.fnmatchcase(value.lower(), pattern.lower()):
                return False
        return True
