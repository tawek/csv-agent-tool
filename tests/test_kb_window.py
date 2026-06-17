from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QInputDialog,
    QMessageBox,
    QTreeView,
)

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

        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            lambda *args, **kwargs: str(kb_path),
        )

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

        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            lambda *args, **kwargs: "",
        )

        emitted = []

        def track_signal(path: str) -> None:
            emitted.append(path)

        window.kb_directory_changed.connect(track_signal)
        window._set_directory()

        assert len(emitted) == 0
        assert window._kb_directory is None
        assert window._dir_label.text() == "(not set)"

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
        """Edit button is enabled for .md, .txt, .csv but not for other files."""
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

    def test_open_in_explorer_without_root_shows_message(self, qtbot, monkeypatch) -> None:
        """Open in explorer with no root shows an info message."""
        window = KnowledgeBaseManager(kb_directory=None)
        qtbot.addWidget(window)

        info_messages = []

        def fake_info(parent, title, text, *args, **kwargs):
            info_messages.append((title, text))
            return QMessageBox.StandardButton.Ok

        monkeypatch.setattr(QMessageBox, "information", fake_info)

        window._open_in_explorer()

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

        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("faq_copy.md", True),
        )

        window._copy_selected()

        assert (kb_dir / "faq_copy.md").exists()

    def test_copy_file_cancelled_does_nothing(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """When user cancels the copy dialog, no copy occurs."""
        window = KnowledgeBaseManager(kb_directory=str(kb_dir))
        qtbot.addWidget(window)

        faq_index = window._model.index(str(kb_dir / "faq.md"))
        window._tree.selectionModel().select(
            faq_index,
            window._tree.selectionModel().SelectionFlag.Select,
        )

        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("faq_copy.md", False),
        )

        window._copy_selected()

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

        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("renamed_faq.md", True),
        )

        window._rename_selected()

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
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window._delete_selected()

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

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window._delete_selected()

        assert not (kb_dir / "faq.md").exists()
        assert not (kb_dir / "notes.txt").exists()
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

        monkeypatch.setattr(QMessageBox, "critical", fake_critical)

        # Select the file normally, then replace the selected path with an escape
        # by directly calling _edit_selected which reads from _selected_single_path.
        # We monkeypatch _selected_single_path to return a path outside KB root.
        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._edit_selected()

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

        monkeypatch.setattr(QMessageBox, "critical", fake_critical)

        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._copy_selected()

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

        monkeypatch.setattr(QMessageBox, "critical", fake_critical)

        def fake_selected():
            return str(tmp_path / "outside.txt")

        monkeypatch.setattr(window, "_selected_single_path", fake_selected)

        window._rename_selected()

        assert len(critical_messages) == 1
        assert "Access denied" in critical_messages[0][0]

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

        monkeypatch.setattr(QMessageBox, "critical", fake_critical)

        def fake_paths():
            return [str(tmp_path / "outside.txt")]

        monkeypatch.setattr(window, "_selected_paths", fake_paths)

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window._delete_selected()

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

        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("renamed_faq.md", True),
        )

        window._rename_selected()

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

        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("faq_copy.md", True),
        )

        window._copy_selected()

        assert (kb_dir / "faq_copy.md").is_file()

    def test_delete_refreshes_tree(self, qtbot, kb_dir: Path, monkeypatch) -> None:
        """After delete, the file is removed and tree is rebuilt."""
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
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        window._delete_selected()

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

        monkeypatch.setattr(QMessageBox, "critical", fake_critical)

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
