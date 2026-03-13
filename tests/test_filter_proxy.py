from PySide6.QtGui import QStandardItem, QStandardItemModel

from product_description_tool.filter_proxy import WildcardFilterProxyModel


def test_wildcard_filter_matches_case_insensitively() -> None:
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["sku", "name"])
    model.appendRow([QStandardItem("A-100"), QStandardItem("Desk Lamp")])
    model.appendRow([QStandardItem("B-200"), QStandardItem("Chair")])

    proxy = WildcardFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.set_filter_pattern(1, "*lamp")

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data() == "A-100"


def test_exact_pattern_without_wildcard_still_filters() -> None:
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["sku"])
    model.appendRow([QStandardItem("A-100")])
    model.appendRow([QStandardItem("A-101")])

    proxy = WildcardFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.set_filter_pattern(0, "A-100")

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data() == "A-100"
