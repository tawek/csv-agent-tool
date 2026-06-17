import os
import shutil

import pytest

os.environ.setdefault("PRODUCT_DESCRIPTION_TOOL_DISABLE_WEBENGINE", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PRODUCT_DESCRIPTION_TOOL_TEST_MODE", "1")


@pytest.fixture(autouse=True)
def _setup_test_mode(tmp_path_factory):
    """Enable test mode globally for all dialog abstractions.

    This prevents QMessageBox, QFileDialog, and QInputDialog from blocking
    unattended tests.  Tests can override specific responses via the
    respective ``set_response()`` calls.
    """
    cache_dir = tmp_path_factory.mktemp("kb-markitdown-cache")
    cache_monkeypatch = pytest.MonkeyPatch()

    from product_description_tool.message_box import set_test_mode as msg_set, reset as msg_reset
    from product_description_tool.file_dialog import set_test_mode as fd_set, reset as fd_reset
    from product_description_tool.input_dialog import set_test_mode as id_set, reset as id_reset
    import product_description_tool.kb_conversion as kc

    msg_set(True)
    msg_reset()
    fd_set(True)
    fd_reset()
    id_set(True)
    id_reset()
    cache_monkeypatch.setattr(
        kc.platformdirs,
        "user_cache_dir",
        lambda *args, **kwargs: str(cache_dir),
    )
    yield
    msg_reset()
    fd_reset()
    id_reset()
    cache_monkeypatch.undo()
    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.fixture
def message_box_responses():
    """Fixture providing a helper to configure message box responses in tests.

    Usage:
        def test_something(message_box_responses):
            message_box_responses.question = "yes"  # or "no", "ok", "cancel"
            # ... test code ...
    """
    from product_description_tool.message_box import set_response, reset
    from PySide6.QtWidgets import QMessageBox

    class _Responses:
        def __init__(self):
            self.information = QMessageBox.StandardButton.Ok
            self.warning = QMessageBox.StandardButton.Ok
            self.critical = QMessageBox.StandardButton.Ok
            self.question = QMessageBox.StandardButton.No

        def __getattr__(self, name: str) -> QMessageBox.StandardButton:
            return getattr(self, name)

        def __setattr__(self, name: str, value: QMessageBox.StandardButton | str) -> None:
            if isinstance(value, str):
                btn_map = {
                    "ok": QMessageBox.StandardButton.Ok,
                    "yes": QMessageBox.StandardButton.Yes,
                    "no": QMessageBox.StandardButton.No,
                    "cancel": QMessageBox.StandardButton.Cancel,
                    "discard": QMessageBox.StandardButton.Discard,
                    "save": QMessageBox.StandardButton.Save,
                }
                value = btn_map.get(value.lower(), QMessageBox.StandardButton.Ok)
            set_response(name, value)
            setattr(self, name, value)

    responses = _Responses()
    yield responses
    reset()
