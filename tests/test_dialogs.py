from PySide6.QtCore import Qt

from product_description_tool.config import AppConfig, FieldConfig
from product_description_tool.dialogs import SettingsDialog


def test_settings_dialog_reset_from_current_csv_populates_visible_columns(qtbot) -> None:
    config = AppConfig()
    config.csv.fields = {
        "old": FieldConfig(label="Old", show=False),
    }
    dialog = SettingsDialog(
        config,
        current_headers=["sku", "description", "generated"],
    )
    qtbot.addWidget(dialog)

    dialog._reset_columns_from_current_csv()
    updated = dialog.get_config()

    assert list(updated.csv.fields.keys()) == ["sku", "description", "generated"]
    assert all(field.show for field in updated.csv.fields.values())
    assert updated.csv.fields["description"].label == "description"


def test_settings_dialog_collects_visibility_and_labels_from_table(qtbot) -> None:
    config = AppConfig()
    dialog = SettingsDialog(
        config,
        current_headers=["sku", "description"],
    )
    qtbot.addWidget(dialog)

    dialog.fields_table.item(0, 1).setCheckState(Qt.CheckState.Unchecked)
    dialog.fields_table.item(1, 2).setText("Product Description")
    updated = dialog.get_config()

    assert updated.csv.fields["sku"].show is False
    assert updated.csv.fields["description"].label == "Product Description"
    assert updated.csv.delimiter == ","
    assert updated.csv.quotechar == '"'
