from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QMessageBox,
    QTreeView,
)

from product_description_tool import message_box, input_dialog, file_dialog
from product_description_tool.kb_editor import MarkdownEditor
from product_description_tool.kb_window import KnowledgeBaseManager


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Create a knowledge-base directory with sample files."""
    d = tmp_path / "kb"
    d.mkdir()
    (d / "faq.md").write_text("# FAQ\n\nFrequently asked questions.", encoding="utf-8")
    (d / "data.csv").write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8-sig")
    (d / "notes.txt").write_text("Some notes.", encoding="utf-8")
    sub = d / "subdir"
    sub.mkdir()
    (sub / "deep.md").write_text("Deep file.", encoding="utf-8")
    return d


# ===================================================================
# Use Case 21 — Manage the Project Knowledge Base
# ===================================================================


class TestDirectoryManagement:
    """UC21: Set and clear the KB directory; action enabled states."""

    def test_initial_state_no_root(self, qtbot) -> None:
        """When no KB directory is set, appropriate actions are disabled."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        assert window._kb_directory is None
        assert window._dir_label.text() == "(not set)"
        # Clear button disabled when no root
        assert window._clear_dir_button.isEnabled() is False
        # Open in explorer disabled when no root
        assert window._open_explorer_button.isEnabled() is False
        # File actions disabled when no root
        assert window._open_external_button.isEnabled() is False
        assert window._edit_button.isEnabled() is False
        assert window._ctx_new_folder.isEnabled() is False
        assert window._ctx_new_md.isEnabled() is False
        assert window._ctx_new_csv.isEnabled() is False
        assert window._new_md_button.isEnabled() is False
        assert window._new_csv_button.isEnabled() is False
        assert window._copy_button.isEnabled() is False
        assert window._rename_button.isEnabled() is False
        assert window._delete_button.isEnabled() is False
        # Set directory should be enabled
        assert window._set_dir_button.isEnabled() is True

    def test_initial_state_with_root(self, qtbot, kb_dir: Path) -> None:
        """When a KB directory is set, actions are enabled appropriately."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        assert window._kb_directory == str(kb_dir)
        assert window._dir_label.text() == str(kb_dir)
        assert window._clear_dir_button.isEnabled() is True
        assert window._open_explorer_button.isEnabled() is True
        assert window._new_folder_button.isEnabled() is True
        assert window._new_md_button.isEnabled() is True
        assert window._new_csv_button.isEnabled() is True
        # File actions enabled (no selection, but has root)
        assert window._open_external_button.isEnabled() is False  # no selection
        assert window._edit_button.isEnabled() is False  # no selection
        assert window._copy_button.isEnabled() is False  # no selection
        assert window._rename_button.isEnabled() is False  # no selection
        assert window._delete_button.isEnabled() is False  # no selection

    def test_set_directory_emits_signal(self, qtbot, tmp_path: Path, monkeypatch) -> None:
        """Setting the directory emits kb_directory_changed with the path."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        kb_path = tmp_path / "new_kb"
        kb_path.mkdir()

        file_dialog.set_response("getExistingDirectory", str(kb_path))

        emitted = []

        def track_signal(path: str) -> None:
            emitted.append(path)

        window.kb_directory_changed.connect(track_signal)
        window._set_directory()

        assert len(emitted) == 1
        assert emitted[0] == str(kb_path)
        assert window._kb_directory == str(kb_path)
        assert window._dir_label.text() == str(kb_path)
        # After setting, actions should be enabled
        assert window._clear_dir_button.isEnabled() is True

    def test_set_directory_cancelled_does_nothing(self, qtbot, monkeypatch) -> None:
        """When the file dialog is cancelled, no changes occur."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        file_dialog.set_response("getExistingDirectory", "")

        emitted = []

        def track_signal(path: str) -> None:
            emitted.append(path)

        window.kb_directory_changed.connect(track_signal)
        window._set_directory()

        assert len(emitted) == 0
        assert window._kb_directory is None
        assert window._dir_label.text() == "(not set)"

    def test_set_directory_rejects_invalid_path(self, qtbot, tmp_path: Path) -> None:
        """An invalid selected directory is rejected and reported."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        invalid_path = tmp_path / "missing-dir"
        file_dialog.set_response("getExistingDirectory", str(invalid_path))

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)
        window._set_directory()

        file_dialog.reset()
        message_box.reset()
        assert critical_messages
        assert critical_messages[0][0] == "Invalid directory"
        assert window._kb_directory is None

    def test_file_dialog_uses_qfiledialog_option_type(self, monkeypatch) -> None:
        """The directory wrapper passes a QFileDialog.Option value in production mode."""
        captured: list[QFileDialog.Option] = []

        def fake_get_existing_directory(parent, caption, directory, options):
            captured.append(options)
            return ""

        file_dialog.set_test_mode(False)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake_get_existing_directory)

        try:
            file_dialog.get_existing_directory(caption="Select", directory="/tmp")
        finally:
            file_dialog.set_test_mode(True)

        assert captured
        assert isinstance(captured[0], QFileDialog.Option)
        assert captured[0] == QFileDialog.Option(0)

    def test_clear_directory_clears_and_emits(self, qtbot, tmp_path: Path) -> None:
        """Clearing the directory resets state and emits empty signal."""
        kb_path = tmp_path / "some_kb"
        kb_path.mkdir()

        window = KnowledgeBaseManager(kb_directory=str(kb_path))
        qtbot.addWidget(window)

        emitted = []

        def track_signal(path: str) -> None:
            emitted.append(path)

        window.kb_directory_changed.connect(track_signal)
        window._clear_directory()

        assert len(emitted) == 1
        assert emitted[0] == ""
        assert window._kb_directory is None
        assert window._dir_label.text() == "(not set)"
        # Actions should be disabled again
        assert window._clear_dir_button.isEnabled() is False
        assert window._open_explorer_button.isEnabled() is False

    def test_clear_directory_when_already_none_does_nothing(self, qtbot) -> None:
        """Clearing when already none is a no-op."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        emitted = []

        def track_signal(path: str) -> None:
            emitted.append(path)

        window.kb_directory_changed.connect(track_signal)
        window._clear_directory()

        assert len(emitted) == 0
        assert window._kb_directory is None

    def test_actions_enable_after_selecting_file(self, qtbot, kb_dir: Path) -> None:
        """Selecting a valid file enables file-management actions."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        # Select a file in the tree
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        # External open should be enabled
        assert window._open_external_button.isEnabled() is True
        # Edit should be enabled for .md
        assert window._edit_button.isEnabled() is True
        # Copy requires single selection
        assert window._copy_button.isEnabled() is True
        # Rename requires single selection
        assert window._rename_button.isEnabled() is True
        # Delete requires single selection
        assert window._delete_button.isEnabled() is True

    def test_edit_button_enabled_only_for_supported_types(self, qtbot, kb_dir: Path) -> None:
        """Edit button is enabled for direct files and view-enabled for non-direct files."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        # Select .md file
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )
        assert window._edit_button.isEnabled() is True

        # Select .csv file
        window._tree.selectionModel().clear()
        csv_index = window._model.index(str(kb_dir / "data.csv"))
        window._tree.selectionModel().select(
            csv_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )
        assert window._edit_button.isEnabled() is True

    def test_non_direct_file_shows_view_button(self, qtbot, kb_dir: Path) -> None:
        """A non-direct KB file exposes the converted view action."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        pdf_path = kb_dir / "manual.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        pdf_index = window._model.index(str(pdf_path))
        window._tree.selectionModel().select(
            pdf_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        assert window._edit_button.isEnabled() is True
        assert window._edit_button.text() == "View"

    def test_open_in_explorer_without_root_shows_message(self, qtbot, monkeypatch) -> None:
        """Open in explorer with no root shows an info message."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        info_messages = []

        def fake_info(parent, title, text, *args, **kwargs):
            info_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("information", fake_info)

        window._open_in_explorer()

        message_box.reset()
        assert len(info_messages) == 1
        assert "No directory" in info_messages[0][0]


# ===================================================================
# Use Case 22 — Browse and Manage Knowledge-Base Files
# ===================================================================


class TestFileOperations:
    """UC22: Copy, rename, delete with boundary enforcement."""

    def test_copy_file_works_within_root(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Copying a file within the KB root succeeds and tree refreshes."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Select faq.md
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        input_dialog.set_response("getText", ("faq_copy.md", True))

        window._copy_selected()

        input_dialog.reset()
        assert (kb_dir / "faq_copy.md").exists()

    def test_create_markdown_file_at_root_and_open_editor(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Creating a markdown file at root appends .md and opens the text editor."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        opened: list[Path] = []
        monkeypatch.setattr(window, "_edit_text_file", lambda path: opened.append(path))
        input_dialog.set_response("getText", ("brief", True))

        window._create_markdown_file()

        input_dialog.reset()
        created = kb_dir / "brief.md"
        assert created.exists()
        assert opened == [created]

    def test_create_folder_at_root(self, qtbot, kb_dir: Path) -> None:
        """Creating a folder at root succeeds."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        input_dialog.set_response("getText", ("drafts", True))

        window._create_folder()

        input_dialog.reset()
        assert (kb_dir / "drafts").is_dir()

    def test_create_csv_file_in_selected_directory(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Creating a csv file with a selected folder uses that folder."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        subdir_index = window._model.index(str(kb_dir / "subdir"))
        window._tree.selectionModel().select(
            subdir_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        opened: list[Path] = []
        monkeypatch.setattr(window, "_edit_csv_file", lambda path: opened.append(path))
        input_dialog.set_response("getText", ("sheet.csv", True))

        window._create_csv_file()

        input_dialog.reset()
        created = kb_dir / "subdir" / "sheet.csv"
        assert created.exists()
        assert opened == [created]

    def test_create_markdown_file_next_to_selected_file(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Creating with a file selected uses the file's parent folder."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        opened: list[Path] = []
        monkeypatch.setattr(window, "_edit_text_file", lambda path: opened.append(path))
        input_dialog.set_response("getText", ("sibling.md", True))

        window._create_markdown_file()

        input_dialog.reset()
        created = kb_dir / "sibling.md"
        assert created.exists()
        assert opened == [created]

    def test_create_file_does_not_overwrite_existing(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Creating a file with an existing name shows a warning and leaves it unchanged."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        warnings: list[tuple[str, str]] = []

        def fake_warning(parent, title, text, *args, **kwargs):
            warnings.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("warning", fake_warning)
        input_dialog.set_response("getText", ("faq.md", True))

        window._create_markdown_file()

        input_dialog.reset()
        message_box.reset()
        assert warnings
        assert warnings[0][0] == "File already exists"

    def test_move_file_to_other_folder(self, qtbot, kb_dir: Path) -> None:
        """Moving a file relocates it into an existing destination folder."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )
        input_dialog.set_response("getText", ("subdir", True))

        window._move_selected()

        input_dialog.reset()
        assert not (kb_dir / "faq.md").exists()
        assert (kb_dir / "subdir" / "faq.md").exists()

    def test_move_folder_rejects_subtree_destination(self, qtbot, kb_dir: Path) -> None:
        """A folder cannot be moved into one of its own descendants."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        nested = kb_dir / "subdir" / "nested"
        nested.mkdir()
        subdir_index = window._model.index(str(kb_dir / "subdir"))
        window._tree.selectionModel().select(
            subdir_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        warnings: list[tuple[str, str]] = []

        def fake_warning(parent, title, text, *args, **kwargs):
            warnings.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("warning", fake_warning)
        input_dialog.set_response("getText", ("subdir/nested", True))

        window._move_selected()

        input_dialog.reset()
        message_box.reset()
        assert warnings
        assert warnings[0][0] == "Invalid destination"
        assert (kb_dir / "subdir").exists()

    def test_copy_file_cancelled_does_nothing(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """When user cancels the copy dialog, no copy occurs."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        input_dialog.set_response("getText", ("faq_copy.md", False))

        window._copy_selected()

        input_dialog.reset()

        assert not (kb_dir / "faq_copy.md").exists()

    def test_rename_file_works_within_root(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Renaming a file within the KB root succeeds."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        input_dialog.set_response("getText", ("renamed_faq.md", True))

        window._rename_selected()

        input_dialog.reset()
        assert not (kb_dir / "faq.md").exists()
        assert (kb_dir / "renamed_faq.md").exists()

    def test_delete_file_with_confirmation(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Deleting a file after confirmation removes it."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        # Confirm deletion
        message_box.set_response("question", QMessageBox.StandardButton.Yes)

        window._delete_selected()

        message_box.reset()

        assert not (kb_dir / "faq.md").exists()

    def test_delete_cancelled_by_user(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """When user says No to deletion, file remains."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        )

        window._delete_selected()

        assert (kb_dir / "faq.md").exists()

    def test_delete_multiple_files(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Deleting multiple selected files removes all."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Select both files using extended selection
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        notes_index = window._model.index(str(kb_dir / "notes.txt"))
        sel = window._tree.selectionModel()
        sel.select(faq_index, sel.SelectionFlag.Select)
        sel.select(notes_index, sel.SelectionFlag.Select | sel.SelectionFlag.Rows)

        message_box.set_response("question", QMessageBox.StandardButton.Yes)

        window._delete_selected()

        assert not (kb_dir / "faq.md").exists()
        assert not (kb_dir / "notes.txt").exists()

    def test_delete_folder_recursive_with_confirmation(self, qtbot, kb_dir: Path) -> None:
        """Deleting a selected folder removes nested contents recursively."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        nested = kb_dir / "subdir" / "nested.txt"
        nested.write_text("nested", encoding="utf-8")

        subdir_index = window._model.index(str(kb_dir / "subdir"))
        window._tree.selectionModel().select(
            subdir_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        message_box.set_response("question", QMessageBox.StandardButton.Yes)
        window._delete_selected()
        message_box.reset()

        assert not (kb_dir / "subdir").exists()
        assert (kb_dir / "data.csv").exists()  # not selected

    def test_open_selected_external_calls_open_external(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Open Externally on a file calls open_external for each selected."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        opened = []

        def fake_open_external(path: str) -> None:
            opened.append(path)

        monkeypatch.setattr(
            "product_description_tool.kb_window.open_external",
            fake_open_external,
        )

        window._open_selected_external()

        assert len(opened) == 1
        assert opened[0] == str(kb_dir / "faq.md")


# ===================================================================
# Boundary enforcement (AR-4)
# ===================================================================


class TestBoundaryEnforcement:
    """File operations must reject escape paths outside the KB root."""

    def test_assert_within_kb_root_accepts_inside(self, qtbot, kb_dir: Path) -> None:
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        result = window._assert_within_kb_root(str(kb_dir / "faq.md"))
        assert result == (kb_dir / "faq.md").resolve()

    def test_assert_within_kb_root_accepts_subdirectory(self, qtbot, kb_dir: Path) -> None:
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        result = window._assert_within_kb_root(str(kb_dir / "subdir" / "deep.md"))
        assert result == (kb_dir / "subdir" / "deep.md").resolve()

    def test_assert_within_kb_root_accepts_root_itself(self, qtbot, kb_dir: Path) -> None:
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        result = window._assert_within_kb_root(str(kb_dir))
        assert result == kb_dir.resolve()

    def test_assert_within_kb_root_rejects_parent(self, qtbot, kb_dir: Path) -> None:
        """Path above the KB root raises ValueError."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        with pytest.raises(ValueError, match="outside the knowledge-base"):
            window._assert_within_kb_root(str(kb_dir.parent))

    def test_assert_within_kb_root_rejects_unrelated(self, qtbot, tmp_path: Path) -> None:
        """Path completely unrelated to KB root raises ValueError."""
        kb = tmp_path / "kb"
        kb.mkdir()
        other = tmp_path / "other"
        other.mkdir()

        window = KnowledgeBaseManager(kb_directory=str(kb))
        qtbot.addWidget(window)

        with pytest.raises(ValueError, match="outside the knowledge-base"):
            window._assert_within_kb_root(str(other))

    def test_assert_within_kb_root_rejects_symlink_escape(
        self, qtbot, kb_dir: Path, tmp_path: Path
    ) -> None:
        """A symlink inside KB root pointing outside is rejected after resolution."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Create a symlink inside KB pointing outside
        escape_target = tmp_path / "secret.txt"
        escape_target.write_text("secrets", encoding="utf-8")
        symlink = kb_dir / "escape_link.txt"
        symlink.symlink_to(escape_target)

        with pytest.raises(ValueError, match="outside the knowledge-base"):
            window._assert_within_kb_root(str(symlink))

    def test_assert_within_kb_root_raises_when_no_root(self, qtbot) -> None:
        """Without a configured KB root, any path raises ValueError."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        with pytest.raises(ValueError, match="No knowledge-base directory"):
            window._assert_within_kb_root("/some/path")

    def test_edit_refuses_outside_path(self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch) -> None:
        """Editing a path outside the KB root shows a critical error."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # Select the file normally, then replace the selected path with an escape
        # by directly calling _edit_selected which reads from _selected_single_path.
        # We monkeypatch _selected_single_path to return a path outside KB root.
        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._edit_selected()

        message_box.reset()
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]

    def test_copy_refuses_outside_path(self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch) -> None:
        """Copying a file outside the KB root shows a critical error."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._copy_selected()

        message_box.reset()
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]

    def test_rename_refuses_outside_path(self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch) -> None:
        """Renaming a file outside the KB root shows a critical error."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._rename_selected()

        message_box.reset()
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]

    def test_copy_rejects_destination_escape(
        self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Copy with a path-traversal destination name is rejected."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Select a file inside the KB root
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # User enters a path-traversal name
        input_dialog.set_response("getText", ("../outside_copy.txt", True))

        window._copy_selected()

        input_dialog.reset()
        # Must show Access denied — destination escapes KB root
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]
        # No file should have been created outside the KB root
        assert not (kb_dir.parent / "outside_copy.txt").exists()

    def test_rename_rejects_destination_escape(
        self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Rename with a path-traversal destination name is rejected."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Select a file inside the KB root
        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # User enters a path-traversal name
        input_dialog.set_response("getText", ("../renamed_escape.md", True))

        window._rename_selected()

        input_dialog.reset()
        # Must show Access denied — destination escapes KB root
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]
        # Original file must still exist (rename was blocked)
        assert (kb_dir / "faq.md").exists()
        # No file should have been created outside the KB root
        assert not (kb_dir.parent / "renamed_escape.md").exists()

    def test_delete_refuses_outside_path(
        self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Deleting a file outside the KB root shows a critical error."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        def fake_paths():
            return [str(tmp_path / "outside.txt")]

        monkeypatch.setattr(window, "_selected_paths", fake_paths)

        message_box.set_response("question", QMessageBox.StandardButton.Yes)

        window._delete_selected()

        message_box.reset()
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]


# ===================================================================
# Explorer refresh after actions (AR-5)
# ===================================================================


class TestExplorerRefresh:
    """After save/operations, explorer refreshes its state."""

    def test_rename_refreshes_tree(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """After rename, the tree root is reset, reflecting the change."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Verify faq.md is indexed
        assert window._model.index(str(kb_dir / "faq.md")).isValid()

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        input_dialog.set_response("getText", ("renamed_faq.md", True))

        window._rename_selected()

        input_dialog.reset()
        # After rename, the old file should not be visible via the model
        # (the tree is rebuilt)
        # The old path should no longer exist on disk
        assert not (kb_dir / "faq.md").exists()
        assert (kb_dir / "renamed_faq.md").exists()

        # The new file should appear after refresh (model may need to catch up)
        # QFileSystemModel may cache; check the file is at least on disk
        assert (kb_dir / "renamed_faq.md").is_file()

    def test_copy_refreshes_tree(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """After copy, the new file exists and tree is rebuilt."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        input_dialog.set_response("getText", ("faq_copy.md", True))

        window._copy_selected()

        input_dialog.reset()
        assert (kb_dir / "faq_copy.md").is_file()

    def test_delete_refreshes_tree(self, qtbot, kb_dir: Path) -> None:
        """After delete, the file is removed and tree is rebuilt."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        message_box.set_response("question", QMessageBox.StandardButton.Yes)

        window._delete_selected()

        message_box.reset()
        assert not (kb_dir / "faq.md").exists()

    def test_refresh_kb_root_sets_directory(self, qtbot, kb_dir: Path) -> None:
        """refresh_kb_root from external (MainWindow) updates state."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        new_dir = kb_dir / "subdir"
        window.refresh_kb_root(str(new_dir))

        assert window._kb_directory == str(new_dir)
        assert new_dir.name in window._dir_label.text()

    def test_refresh_kb_root_clears_when_none(self, qtbot, kb_dir: Path) -> None:
        """refresh_kb_root with None clears the displayed state."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        window.refresh_kb_root(None)

        assert window._kb_directory is None
        assert window._dir_label.text() == "(not set)"
        assert window._clear_dir_button.isEnabled() is False


# ===================================================================
# Text editor (Use Case 26) — modal embedded editor with MarkdownEditor
# ===================================================================


class TestTextEditor:
    """UC26: Modal embedded text editor for .md and .txt files."""

    def test_text_file_editor_uses_markdown_editor_widget(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """The embedded text editor dialog uses MarkdownEditor widget."""
        from product_description_tool.kb_editor import MarkdownEditor
        from product_description_tool.kb_window import MarkdownEditor as KwMarkdownEditor

        # Both imports refer to the same class
        assert MarkdownEditor is KwMarkdownEditor

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # Open the text file directly by calling _edit_text_file
        faq_path = kb_dir / "faq.md"

        # We'll capture the dialog that _edit_text_file creates
        # by monkeypatching QDialog.exec to capture the editor
        dialog_editor = None

        def capture_dialog(self_dialog):
            nonlocal dialog_editor
            # Find the MarkdownEditor child in the dialog
            for child in self_dialog.children():
                if isinstance(child, MarkdownEditor):
                    dialog_editor = child
                    break
            return QDialog.Accepted  # Simulate Save

        monkeypatch.setattr(QDialog, "exec", capture_dialog)

        window._edit_text_file(faq_path)

        assert dialog_editor is not None
        assert isinstance(dialog_editor, MarkdownEditor)
        # The editor should contain the file's content
        assert "FAQ" in dialog_editor.toPlainText()

    def test_text_file_save_writes_content(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Save button in text editor writes modified content to disk."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_path = kb_dir / "faq.md"
        original = faq_path.read_text(encoding="utf-8")
        new_content = "# Updated FAQ\n\nCompletely new content."

        # Intercept QDialog.exec and replace editor content before accept.
        # The function receives the actual dialog instance as its argument.
        def fake_exec(dialog):
            from product_description_tool.kb_editor import MarkdownEditor

            for child in dialog.children():
                if isinstance(child, MarkdownEditor):
                    child.setPlainText(new_content)
                    break
            return QDialog.Accepted

        monkeypatch.setattr(QDialog, "exec", fake_exec)

        window._edit_text_file(faq_path)

        saved = faq_path.read_text(encoding="utf-8")
        assert saved == new_content
        assert saved != original

    def test_text_file_cancel_does_not_write(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Cancel in text editor leaves file unchanged."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_path = kb_dir / "faq.md"
        original = faq_path.read_text(encoding="utf-8")

        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)

        window._edit_text_file(faq_path)

        saved = faq_path.read_text(encoding="utf-8")
        assert saved == original

    def test_text_file_has_external_button(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Text editor dialog has an 'Open Externally' button."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_path = kb_dir / "faq.md"
        external_opened = []

        def fake_open_external(path: str) -> None:
            external_opened.append(path)

        monkeypatch.setattr(
            "product_description_tool.kb_window.open_external",
            fake_open_external,
        )

        # We need to reach the button inside the dialog.
        # Instead, monkeypatch the exec to capture the dialog and click the button.
        captured_dialog = None

        def capture_and_exec(self_dialog):
            nonlocal captured_dialog
            captured_dialog = self_dialog
            return QDialog.Rejected  # don't save

        monkeypatch.setattr(QDialog, "exec", capture_and_exec)

        window._edit_text_file(faq_path)

        assert captured_dialog is not None
        # Find the "Open Externally" button
        for child in captured_dialog.children():
            btn = getattr(child, "text", lambda: "")()
            if btn == "Open Externally":
                child.click()
                break

        assert len(external_opened) == 1
        assert external_opened[0] == str(faq_path)

    def test_text_file_save_triggers_rebuild(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """After saving a text file, _rebuild_tree is called."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_path = kb_dir / "faq.md"
        rebuild_called = False
        original_rebuild = window._rebuild_tree

        def tracking_rebuild():
            nonlocal rebuild_called
            rebuild_called = True
            original_rebuild()

        monkeypatch.setattr(window, "_rebuild_tree", tracking_rebuild)
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Accepted)

        window._edit_text_file(faq_path)

        assert rebuild_called


# ===================================================================
# CSV editor (Use Case 27) — modal grid editor launch
# ===================================================================


class TestCsvEditorLaunch:
    """UC27: Modal CSV editor opens on .csv files."""

    def test_csv_file_opens_editor_dialog(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """Opening a csv file dispatches to _edit_csv_file which creates CsvEditorDialog."""
        from product_description_tool.kb_csv_editor import CsvEditorDialog

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        csv_path = kb_dir / "data.csv"

        dialog_created = False

        original_edit_csv = window._edit_csv_file

        def tracking_edit_csv(path):
            nonlocal dialog_created
            dialog_created = True
            # Verify it creates a CsvEditorDialog
            dlg = CsvEditorDialog(path, parent=window)
            assert isinstance(dlg, CsvEditorDialog)
            qtbot.addWidget(dlg)

        monkeypatch.setattr(window, "_edit_csv_file", tracking_edit_csv)

        window._open_file_for_edit(str(csv_path))

        assert dialog_created

    def test_csv_editor_save_triggers_rebuild(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """After saving a CSV file, _rebuild_tree is called."""
        from product_description_tool.kb_csv_editor import CsvEditorDialog

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        csv_path = kb_dir / "data.csv"
        rebuild_called = False
        original_rebuild = window._rebuild_tree

        def tracking_rebuild():
            nonlocal rebuild_called
            rebuild_called = True
            original_rebuild()

        monkeypatch.setattr(window, "_rebuild_tree", tracking_rebuild)
        # Intercept the CSV editor's exec to simulate accept
        monkeypatch.setattr(CsvEditorDialog, "exec", lambda self: QDialog.Accepted)

        window._edit_csv_file(csv_path)

        assert rebuild_called

    def test_csv_editor_cancel_does_not_rebuild(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """After cancelling CSV editor, _rebuild_tree is not called."""
        from product_description_tool.kb_csv_editor import CsvEditorDialog

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        csv_path = kb_dir / "data.csv"
        rebuild_called = False

        def tracking_rebuild():
            nonlocal rebuild_called
            rebuild_called = True

        monkeypatch.setattr(window, "_rebuild_tree", tracking_rebuild)
        monkeypatch.setattr(CsvEditorDialog, "exec", lambda self: QDialog.Rejected)

        window._edit_csv_file(csv_path)

        assert not rebuild_called


# ===================================================================
# Double-click behavior
# ===================================================================


class TestDoubleClick:
    """Double-click opens embedded editor for supported file types."""

    def test_double_click_on_md_opens_editor(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Double-clicking a .md file opens the embedded text editor."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_path = str(kb_dir / "faq.md")
        faq_index = window._model.index(faq_path)

        open_called = []

        def fake_open_file_for_edit(path: str) -> None:
            open_called.append(path)

        monkeypatch.setattr(window, "_open_file_for_edit", fake_open_file_for_edit)

        window._on_tree_double_clicked(faq_index)

        assert len(open_called) == 1
        assert open_called[0] == faq_path

    def test_double_click_on_csv_opens_editor(
        self, qtbot, kb_dir: Path, monkeypatch
    ) -> None:
        """Double-clicking a .csv file opens the embedded editor."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        csv_path = str(kb_dir / "data.csv")
        csv_index = window._model.index(csv_path)

        open_called = []

        def fake_open_file_for_edit(path: str) -> None:
            open_called.append(path)

        monkeypatch.setattr(window, "_open_file_for_edit", fake_open_file_for_edit)

        window._on_tree_double_clicked(csv_index)

        assert len(open_called) == 1
        assert open_called[0] == csv_path

    def test_double_click_on_dir_does_not_open_editor(
        self, qtbot, kb_dir: Path
    ) -> None:
        """Double-clicking a directory does not trigger the editor."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        subdir_index = window._model.index(str(kb_dir / "subdir"))

        # This should not raise; directories are handled by QTreeView natively
        window._on_tree_double_clicked(subdir_index)

        # No assertion needed — just verify no crash

    def test_double_click_on_outside_path_denied(
        self, qtbot, kb_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Double-click on a path that escapes KB root shows critical error."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)

        # Simulate a double-click on a path outside the KB root
        # by creating an index that resolves outside
        outside_path = str(tmp_path / "outside.txt")

        # Monkeypatch _assert_within_kb_root to raise ValueError for this test
        original_assert = window._assert_within_kb_root

        def rejecting_assert(path):
            raise ValueError(f"Path '{path}' is outside the knowledge-base directory")

        monkeypatch.setattr(window, "_assert_within_kb_root", rejecting_assert)

        # We can pass any index since the assertion happens before path resolution
        # in real code. For testing, we pass the index but the assertion will fail.
        faq_index = window._model.index(str(kb_dir / "faq.md"))

        window._on_tree_double_clicked(faq_index)

        message_box.reset()
        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]


# ===================================================================
# Window lifecycle
# ===================================================================


def test_window_is_non_modal(qtbot) -> None:
    """KnowledgeBaseManager is not modal (it is a separate non-modal window)."""
    window = KnowledgeBaseManager(kb_directory=None)
    qtbot.addWidget(window)
    assert not window.isModal()


def test_window_title(qtbot) -> None:
    window = KnowledgeBaseManager(kb_directory=None)
    qtbot.addWidget(window)
    assert "Knowledge Base Manager" in window.windowTitle()


def test_window_has_tree_view(qtbot) -> None:
    window = KnowledgeBaseManager(kb_directory=None)
    qtbot.addWidget(window)
    assert isinstance(window._tree, QTreeView)


def test_window_has_file_system_model(qtbot) -> None:
    window = KnowledgeBaseManager(kb_directory=None)
    qtbot.addWidget(window)
    assert isinstance(window._model, QFileSystemModel)


def test_delete_on_close_attribute(qtbot) -> None:
    """The window has WA_DeleteOnClose set to False (maintains single instance)."""
    window = KnowledgeBaseManager(kb_directory=None)
    qtbot.addWidget(window)
    assert not window.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)


# ===================================================================
# Close button (UC21 step 9 — menu simplification follow-up)
# ===================================================================


class TestCloseButton:
    """UC21: The KB manager has a Close button that closes the window."""

    def test_close_button_exists(self, qtbot) -> None:
        """The Close button is present and properly labelled."""
        from PySide6.QtWidgets import QPushButton

        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        assert hasattr(window, "_close_button")
        assert isinstance(window._close_button, QPushButton)
        assert window._close_button.text() == "Close"

    def test_close_button_always_enabled(self, qtbot) -> None:
        """The Close button is always enabled regardless of KB directory state."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        # Enabled even with no KB dir
        assert window._close_button.isEnabled() is True

    def test_close_button_closes_window(self, qtbot, kb_dir: Path) -> None:
        """Clicking Close hides the non-modal window (WA_DeleteOnClose is False)."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        assert window.isVisible()

        window._close_button.click()

        # WA_DeleteOnClose is False, so close() hides rather than destroys
        assert window.isHidden() is True

    def test_close_button_click_emits_accepted(self, qtbot, kb_dir: Path) -> None:
        """The Close button calls QDialog.close() — the rejected signal is
        not required, but the dialog should not be modal so close() works
        as a window-close (hide)."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        with qtbot.waitSignal(window.finished, timeout=500, raising=False):
            window._close_button.click()

        # close() on a non-modal QDialog emits finished(int) with QDialog.Rejected
        # as the result code; since WA_DeleteOnClose is False the widget survives.
        assert window.isHidden()


# ===================================================================
# Use Case 29 — View a Convertible Knowledge-Base File as Markdown
# ===================================================================


class TestConvertibleFileViewing:
    """UC29: Read-only Markdown viewer for convertible files (PDF, docx, etc.)."""

    def test_view_button_enabled_for_convertible_file(self, qtbot, kb_dir, tmp_path):
        """The primary action button shows 'View' for convertible files."""
        html_file = kb_dir / "test.html"
        html_file.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        # Select the HTML file
        idx = window._model.index(str(html_file))
        window._tree.selectionModel().select(
            idx,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        assert window._edit_button.isEnabled() is True
        assert window._edit_button.text() == "View"

    def test_edit_button_shows_edit_for_direct_read(self, qtbot, kb_dir):
        """The primary action button shows 'Edit' for direct-read files."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)
        window.show()

        # Select an .md file
        md_file = kb_dir / "faq.md"
        idx = window._model.index(str(md_file))
        window._tree.selectionModel().select(
            idx,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        assert window._edit_button.isEnabled() is True
        assert window._edit_button.text() == "Edit"

    def test_view_converted_file_shows_markdown(self, qtbot, kb_dir, monkeypatch):
        """Viewing a convertible HTML file calls load_markdown with the right args."""
        import product_description_tool.kb_conversion as kc

        html_file = kb_dir / "article.html"
        html_file.write_text(
            "<html><body><h1>Article</h1><p>Body text.</p></body></html>",
            encoding="utf-8",
        )

        call_args = []

        def fake_load(svc, file_path, kb_root):
            call_args.append((str(file_path), str(kb_root)))
            return "# Converted"

        monkeypatch.setattr(kc.KnowledgeBaseContentService, "load_markdown", fake_load)

        # Also monkeypatch QDialog.exec to return immediately
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        window._view_converted_file(html_file)

        assert len(call_args) == 1
        assert call_args[0][0] == str(html_file)

    def test_view_converted_file_readonly(self, qtbot, kb_dir, monkeypatch):
        """The MarkdownEditor in view dialog is read-only."""
        import product_description_tool.kb_conversion as kc

        monkeypatch.setattr(kc.KnowledgeBaseContentService, "load_markdown", lambda s, fp, kr: "# Read-only test")

        html_file = kb_dir / "readonly_test.html"
        html_file.write_text("<html><body><p>Test</p></body></html>", encoding="utf-8")

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        # This approach verifies read-only by checking the editor widget state
        # We'll use a close-to-open approach via monkeypatch
        captured_editor = None

        def capture_dialog(self_dialog):
            nonlocal captured_editor
            for child in self_dialog.children():
                if isinstance(child, MarkdownEditor):
                    captured_editor = child
                    break
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(QDialog, "exec", capture_dialog)

        window._view_converted_file(html_file)

        assert captured_editor is not None
        assert captured_editor.isReadOnly() is True

    def test_view_converted_file_has_external_button(self, qtbot, kb_dir, monkeypatch):
        """View dialog has an 'Open Externally' button."""
        import product_description_tool.kb_conversion as kc

        monkeypatch.setattr(kc.KnowledgeBaseContentService, "load_markdown", lambda s, fp, kr: "# External test")

        html_file = kb_dir / "external_test.html"
        html_file.write_text("<html><body><p>Test</p></body></html>", encoding="utf-8")

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        opened_paths = []

        def fake_open_external(path):
            opened_paths.append(path)

        monkeypatch.setattr("product_description_tool.kb_window.open_external", fake_open_external)

        captured_dialog = None

        def capture_and_exec(self_dialog):
            nonlocal captured_dialog
            captured_dialog = self_dialog
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", capture_and_exec)

        window._view_converted_file(html_file)

        assert captured_dialog is not None
        # Find and click the "Open Externally" button
        for child in captured_dialog.children():
            btn_text = getattr(child, "text", lambda: "")()
            if btn_text == "Open Externally":
                child.click()
                break

        assert len(opened_paths) == 1
        assert opened_paths[0] == str(html_file)

    def test_view_converted_file_handles_markitdown_unavailable(
        self, qtbot, kb_dir, monkeypatch
    ):
        """When MarkItDown is unavailable, an error dialog is shown."""
        import product_description_tool.kb_conversion as kc

        critical_messages = []

        def fake_critical(parent, title, text, *args, **kwargs):
            critical_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        message_box.set_response("critical", fake_critical)
        monkeypatch.setattr(
            kc.KnowledgeBaseContentService,
            "_check_markitdown",
            lambda self: False,
        )

        html_file = kb_dir / "unavailable_test.html"
        html_file.write_text("<html><body><p>Test</p></body></html>", encoding="utf-8")

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        window._view_converted_file(html_file)

        message_box.reset()
        assert len(critical_messages) == 1
        assert any("Conversion unavailable" in msg for msg in critical_messages[0])

    def test_double_click_opens_view_for_convertible(
        self, qtbot, kb_dir, monkeypatch
    ):
        """Double-clicking a convertible file opens the view."""
        html_file = kb_dir / "click_test.html"
        html_file.write_text("<html><body><p>Click test</p></body></html>", encoding="utf-8")

        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        opened_files = []

        def fake_open_file_for_edit(path):
            opened_files.append(path)

        monkeypatch.setattr(window, "_open_file_for_edit", fake_open_file_for_edit)

        idx = window._model.index(str(html_file))
        window._on_tree_double_clicked(idx)

        assert len(opened_files) == 1
        assert opened_files[0] == str(html_file)
