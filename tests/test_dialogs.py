from PySide6.QtCore import Qt

from product_description_tool.config import AppConfig, FieldConfig
from product_description_tool.dialogs import ActivityDialog, SettingsDialog


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


def test_activity_dialog_can_be_closed_after_finish_when_close_on_finish_is_off(qtbot) -> None:
    dialog = ActivityDialog()
    qtbot.addWidget(dialog)

    dialog.start_activity(
        title="Processing",
        status="Working...",
        total_records=2,
        input_chars=10,
        close_on_finish=False,
    )
    dialog.finish_status("Finished")
    dialog.close_activity()

    assert dialog.cancel_button.text() == "Close"

    dialog.reject()

    assert dialog.isVisible() is False


def test_activity_dialog_becomes_modeless_while_cancelling(qtbot) -> None:
    dialog = ActivityDialog()
    qtbot.addWidget(dialog)

    dialog.start_activity(
        title="Processing",
        status="Working...",
        total_records=2,
        input_chars=10,
        close_on_finish=False,
    )
    dialog.request_cancel()

    assert dialog.cancel_button.isEnabled() is False
    assert dialog.cancel_button.text() == "Cancelling..."


def test_activity_dialog_force_close_closes_even_when_close_on_finish_is_off(qtbot) -> None:
    dialog = ActivityDialog()
    qtbot.addWidget(dialog)

    dialog.start_activity(
        title="Processing",
        status="Working...",
        total_records=2,
        input_chars=10,
        close_on_finish=False,
    )
    dialog.finish_status("Cancelled")
    dialog.close_activity(force_close=True)

    assert dialog.isVisible() is False


def test_settings_dialog_uses_editable_model_combos(qtbot) -> None:
    config = AppConfig()
    config.provider.ollama.model = "llama3.2"
    config.provider.openai.model = "gpt-5-mini"

    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    assert dialog.ollama_model_combo.isEditable() is True
    assert dialog.openai_model_combo.isEditable() is True
    assert dialog.ollama_model_combo.currentText() == "llama3.2"
    assert dialog.openai_model_combo.currentText() == "gpt-5-mini"


def test_settings_dialog_expands_primary_controls(qtbot) -> None:
    dialog = SettingsDialog(AppConfig())
    qtbot.addWidget(dialog)

    assert dialog.active_provider_combo.minimumWidth() >= 320
    assert dialog.ollama_base_url_edit.minimumWidth() >= 420
    assert dialog.openai_api_key_edit.minimumWidth() >= 420
    assert dialog.ollama_model_combo.parentWidget().minimumWidth() >= 420
    assert dialog.ollama_options_edit.minimumWidth() >= 420
    assert dialog.original_description_edit.minimumWidth() >= 320


def test_settings_dialog_refreshes_ollama_model_choices(qtbot, monkeypatch) -> None:
    config = AppConfig()
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog.ollama_model_combo.setEditText("custom-model")

    monkeypatch.setattr(
        "product_description_tool.dialogs.list_ollama_models",
        lambda *, base_url: ["llama3.2", "mistral:latest"],
    )

    dialog._refresh_ollama_models()

    assert dialog.ollama_model_combo.count() == 2
    assert dialog.ollama_model_combo.itemText(0) == "llama3.2"
    assert dialog.ollama_model_combo.itemText(1) == "mistral:latest"
    assert dialog.ollama_model_combo.currentText() == "custom-model"


def test_settings_dialog_refreshes_openai_model_choices(qtbot, monkeypatch) -> None:
    config = AppConfig()
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog.openai_api_key_edit.setText("secret")
    dialog.openai_model_combo.setEditText("custom-model")

    monkeypatch.setattr(
        "product_description_tool.dialogs.list_openai_models",
        lambda *, base_url, api_key: ["gpt-5", "gpt-5-mini"],
    )

    dialog._refresh_openai_models()

    assert dialog.openai_model_combo.count() == 2
    assert dialog.openai_model_combo.itemText(0) == "gpt-5"
    assert dialog.openai_model_combo.itemText(1) == "gpt-5-mini"
    assert dialog.openai_model_combo.currentText() == "custom-model"
