from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileSystemModel,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeView,
    QVBoxLayout,
)

from product_description_tool import message_box, input_dialog, file_dialog
from product_description_tool.kb_conversion import (
    CONVERTIBLE_EXTENSIONS,
    ConversionFailedError,
    KnowledgeBaseContentService,
    MarkItDownUnavailableError,
)
from product_description_tool.kb_csv_editor import CsvEditorDialog
from product_description_tool.kb_editor import MarkdownEditor, open_external

from .message_box import information, warning, critical, question, QMessageBoxStandardButton as StandardButton


# File types supported for embedded editing (text and CSV).
_EMBEDDED_EDIT_SUFFIXES: frozenset[str] = frozenset({
    ".md", ".markdown", ".txt", ".csv",
})


class KnowledgeBaseManager(QDialog):
    """Non-modal window for browsing and managing the project knowledge base.

    Shows the configured knowledge-base root directory, provides a
    filesystem tree rooted at that directory, and offers file-management
    actions (copy, rename, delete) as well as access to embedded editors
    for supported file types and external open for any file.

    Emits *kb_directory_changed* when the user changes or clears the
    configured knowledge-base directory.
    """

    kb_directory_changed = Signal(str)  # emitted with the new dir path, or "" when cleared

    def __init__(self, kb_directory: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Knowledge Base Manager")
        self.resize(900, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._kb_directory: str | None = kb_directory
        self._model = QFileSystemModel(self)
        self._model.setRootPath("")
        self._model.setReadOnly(False)
        self._model.setNameFilters(["*"])
        self._model.setNameFilterDisables(False)

        self._build_ui()
        if self._kb_directory:
            self._set_tree_root(self._kb_directory)
        self._refresh_actions()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # -- Header: KB directory path + action buttons -----------------
        header = QHBoxLayout()
        header.addWidget(QLabel("Knowledge Base Directory:"))
        self._dir_label = QLabel(self._kb_directory or "(not set)")
        self._dir_label.setStyleSheet(
            "font-weight: bold; padding: 2px 6px;",
        )
        header.addWidget(self._dir_label, 1)

        self._set_dir_button = QPushButton("Set Directory...")
        self._set_dir_button.clicked.connect(self._set_directory)
        header.addWidget(self._set_dir_button)

        self._clear_dir_button = QPushButton("Clear")
        self._clear_dir_button.clicked.connect(self._clear_directory)
        header.addWidget(self._clear_dir_button)

        self._open_explorer_button = QPushButton("Open in File Explorer")
        self._open_explorer_button.clicked.connect(self._open_in_explorer)
        header.addWidget(self._open_explorer_button)
        layout.addLayout(header)

        # -- Tree view -------------------------------------------------
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setAnimated(False)
        self._tree.setIndentation(20)
        self._tree.setSortingEnabled(True)
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._tree.doubleClicked.connect(self._on_tree_double_clicked)
        self._tree.selectionModel().selectionChanged.connect(
            lambda: self._refresh_actions(),
        )
        self._tree.setColumnWidth(0, 300)
        layout.addWidget(self._tree, 1)

        # -- Action buttons row ----------------------------------------
        actions_row = QHBoxLayout()

        self._edit_button = QPushButton("Edit")
        self._edit_button.clicked.connect(self._edit_selected)
        actions_row.addWidget(self._edit_button)

        self._open_external_button = QPushButton("Open Externally")
        self._open_external_button.clicked.connect(self._open_selected_external)
        actions_row.addWidget(self._open_external_button)

        actions_row.addStretch(1)

        self._copy_button = QPushButton("Copy...")
        self._copy_button.clicked.connect(self._copy_selected)
        actions_row.addWidget(self._copy_button)

        self._rename_button = QPushButton("Rename...")
        self._rename_button.clicked.connect(self._rename_selected)
        actions_row.addWidget(self._rename_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.clicked.connect(self._delete_selected)
        actions_row.addWidget(self._delete_button)

        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.close)
        actions_row.addWidget(self._close_button)

        layout.addLayout(actions_row)

        # -- Context menu ----------------------------------------------
        self._ctx_edit = QAction("Edit", self)
        self._ctx_edit.triggered.connect(self._edit_selected)
        self._tree.addAction(self._ctx_edit)

        self._ctx_open_external = QAction("Open Externally", self)
        self._ctx_open_external.triggered.connect(self._open_selected_external)
        self._tree.addAction(self._ctx_open_external)

        self._tree.addAction(QAction("---", self))  # separator

        self._ctx_copy = QAction("Copy...", self)
        self._ctx_copy.triggered.connect(self._copy_selected)
        self._tree.addAction(self._ctx_copy)

        self._ctx_rename = QAction("Rename...", self)
        self._ctx_rename.triggered.connect(self._rename_selected)
        self._tree.addAction(self._ctx_rename)

        self._ctx_delete = QAction("Delete", self)
        self._ctx_delete.triggered.connect(self._delete_selected)
        self._tree.addAction(self._ctx_delete)

    # ------------------------------------------------------------------
    # Tree management
    # ------------------------------------------------------------------

    def _set_tree_root(self, directory: str) -> None:
        """Point the filesystem tree at *directory*."""
        path = Path(directory).resolve()
        if not path.is_dir():
            return
        self._model.setRootPath(str(path))
        self._tree.setRootIndex(self._model.index(str(path)))
        for col in range(1, self._model.columnCount()):
            self._tree.setColumnHidden(col, True)

    def _selected_paths(self) -> list[str]:
        """Return the absolute paths of all selected items (one per row)."""
        paths: list[str] = []
        for index in self._tree.selectionModel().selectedIndexes():
            if index.column() == 0:
                file_path = self._model.filePath(index)
                if file_path:
                    paths.append(file_path)
        return paths

    def _selected_single_path(self) -> str | None:
        paths = self._selected_paths()
        return paths[0] if len(paths) == 1 else None

    def _refresh_actions(self) -> None:
        """Enable or disable action buttons based on current selection."""
        count = len(self._selected_paths())
        has_root = self._kb_directory is not None

        # Header buttons
        self._clear_dir_button.setEnabled(has_root)
        self._open_explorer_button.setEnabled(has_root)

        # File-management buttons
        self._open_external_button.setEnabled(has_root and count >= 1)
        single = self._selected_single_path()
        single_path = Path(single) if single is not None else None
        single_suffix = single_path.suffix.lower() if single_path is not None else ""
        is_editable = (
            has_root
            and single is not None
            and single_path is not None
            and single_path.is_file()
            and single_suffix in _EMBEDDED_EDIT_SUFFIXES
        )
        is_viewable = (
            has_root
            and single is not None
            and single_path is not None
            and single_path.is_file()
            and single_suffix in CONVERTIBLE_EXTENSIONS
        )
        self._edit_button.setEnabled(is_editable or is_viewable)
        if is_viewable and not is_editable:
            self._edit_button.setText("View")
        else:
            self._edit_button.setText("Edit")
        self._copy_button.setEnabled(has_root and count == 1)
        self._rename_button.setEnabled(has_root and count == 1)
        self._delete_button.setEnabled(has_root and count >= 1)

    # ------------------------------------------------------------------
    # KB-root boundary enforcement
    # ------------------------------------------------------------------

    def _assert_within_kb_root(self, path: str | Path) -> Path:
        """Resolve *path* and verify it is within the configured KB root.

        Returns the resolved Path on success.
        Raises ValueError if the path is outside the KB root or no KB
        root is configured.
        """
        if self._kb_directory is None:
            raise ValueError("No knowledge-base directory is configured.")
        resolved = Path(path).resolve()
        kb_root = Path(self._kb_directory).resolve()
        if resolved != kb_root and kb_root not in resolved.parents:
            raise ValueError(
                f"Path '{resolved}' is outside the knowledge-base "
                f"directory '{kb_root}'.",
            )
        return resolved

    # ------------------------------------------------------------------
    # Directory management
    # ------------------------------------------------------------------

    def _set_directory(self) -> None:
        directory = file_dialog.get_existing_directory(
            self,
            "Select Knowledge Base Directory",
            self._kb_directory or "",
        )
        if not directory:
            return
        self._kb_directory = directory
        self._dir_label.setText(directory)
        self._set_tree_root(directory)
        self._refresh_actions()
        self.kb_directory_changed.emit(directory)

    def _clear_directory(self) -> None:
        if self._kb_directory is None:
            return
        self._kb_directory = None
        self._dir_label.setText("(not set)")
        self._model.setRootPath("")
        self._tree.setRootIndex(QModelIndex())
        self._refresh_actions()
        self.kb_directory_changed.emit("")

    def _open_in_explorer(self) -> None:
        if not self._kb_directory:
            information(
                self,
                "No directory",
                "No knowledge-base directory is configured.",
            )
            return
        open_external(self._kb_directory)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _on_tree_double_clicked(self, index: QModelIndex) -> None:
        path = self._model.filePath(index)
        if not path:
            return
        if Path(path).is_dir():
            return  # QTBUG — QTreeView handles folder expansion natively
        try:
            self._assert_within_kb_root(path)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        self._open_file_for_edit(path)

    def _edit_selected(self) -> None:
        path = self._selected_single_path()
        if not path:
            return
        try:
            self._assert_within_kb_root(path)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        self._open_file_for_edit(path)

    def _open_file_for_edit(self, path: str) -> None:
        """Open *path* in the appropriate embedded editor or viewer."""
        file_path = Path(path)
        if not file_path.is_file():
            warning(self, "Not a file", f"'{path}' is not a file.")
            return

        suffix = file_path.suffix.lower()
        if suffix in {".md", ".markdown", ".txt"}:
            self._edit_text_file(file_path)
        elif suffix == ".csv":
            self._edit_csv_file(file_path)
        elif suffix in CONVERTIBLE_EXTENSIONS:
            self._view_converted_file(file_path)
        else:
            open_external(path)

    def _edit_text_file(self, path: Path) -> None:
        """Open a text/markdown file in a modal embedded editor."""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            critical(
                self,
                "Read failed",
                f"Could not read '{path}':\n{exc}",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit: {path.name}")
        dialog.resize(680, 480)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        editor = MarkdownEditor()
        editor.setPlainText(content)
        layout.addWidget(editor, 1)

        button_layout = QHBoxLayout()

        external_button = QPushButton("Open Externally")
        external_button.clicked.connect(lambda: open_external(str(path)))
        button_layout.addWidget(external_button)

        button_layout.addStretch(1)

        save_button = QPushButton("Save")
        save_button.clicked.connect(dialog.accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.Accepted:
            new_content = editor.toPlainText()
            try:
                path.write_text(new_content, encoding="utf-8")
                self._rebuild_tree()
            except Exception as exc:  # noqa: BLE001
                critical(
                    self,
                    "Save failed",
                    f"Could not write '{path}':\n{exc}",
                )
                return

    def _edit_csv_file(self, path: Path) -> None:
        """Open a CSV file in a modal grid editor dialog."""
        dialog = CsvEditorDialog(path, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._rebuild_tree()

    def _view_converted_file(self, path: Path) -> None:
        """Open a convertible file in a read-only Markdown viewer dialog.

        Converts the file to Markdown (with caching), then displays it in
        a non-editable Markdown viewer.  The dialog also offers an action
        to open the original file externally.
        """
        svc = KnowledgeBaseContentService()
        try:
            kb_root = Path(self._kb_directory).resolve() if self._kb_directory else None
            if kb_root is None:
                critical(
                    self, "No knowledge base",
                    "No knowledge-base directory is configured.",
                )
                return
            markdown = svc.load_markdown(path, kb_root)
        except MarkItDownUnavailableError:
            critical(
                self,
                "Conversion unavailable",
                f"Cannot view '{path.name}': MarkItDown is not available.\n\n"
                "Install the markitdown package or open the file externally.",
            )
            return
        except ConversionFailedError as exc:
            critical(
                self,
                "Conversion failed",
                str(exc),
            )
            return
        except Exception as exc:  # noqa: BLE001
            critical(
                self,
                "View failed",
                f"Could not open '{path.name}' for viewing:\n{exc}",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"View: {path.name} (converted Markdown)")
        dialog.resize(680, 480)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        editor = MarkdownEditor()
        editor.setPlainText(markdown)
        editor.setReadOnly(True)
        layout.addWidget(editor, 1)

        button_layout = QHBoxLayout()

        external_button = QPushButton("Open Externally")
        external_button.clicked.connect(lambda: open_external(str(path)))
        button_layout.addWidget(external_button)

        button_layout.addStretch(1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        dialog.exec()

    def _open_selected_external(self) -> None:
        paths = self._selected_paths()
        for path in paths:
            try:
                self._assert_within_kb_root(path)
            except ValueError as exc:
                critical(self, "Access denied", str(exc))
                continue
            open_external(path)

    def _copy_selected(self) -> None:
        path = self._selected_single_path()
        if not path:
            return
        source = Path(path)
        try:
            self._assert_within_kb_root(source)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        new_name, accepted = input_dialog.get_text(
            self,
            "Copy",
            f"Enter name for the copy of '{source.name}':",
            text=f"Copy of {source.name}",
        )
        if not accepted or not new_name.strip():
            return
        target = source.parent / new_name.strip()
        try:
            self._assert_within_kb_root(target)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        try:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        except Exception as exc:  # noqa: BLE001
            critical(
                self,
                "Copy failed",
                f"Could not copy '{source}' to '{target}':\n{exc}",
            )
            return
        self._rebuild_tree()

    def _rename_selected(self) -> None:
        path = self._selected_single_path()
        if not path:
            return
        source = Path(path)
        try:
            self._assert_within_kb_root(source)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        new_name, accepted = input_dialog.get_text(
            self,
            "Rename",
            f"New name for '{source.name}':",
            text=source.name,
        )
        if not accepted or not new_name.strip():
            return
        target = source.parent / new_name.strip()
        try:
            self._assert_within_kb_root(target)
        except ValueError as exc:
            critical(self, "Access denied", str(exc))
            return
        try:
            source.rename(target)
        except Exception as exc:  # noqa: BLE001
            critical(
                self,
                "Rename failed",
                f"Could not rename '{source}' to '{target}':\n{exc}",
            )
            return
        self._rebuild_tree()

    def _delete_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        for path_str in paths:
            try:
                self._assert_within_kb_root(path_str)
            except ValueError as exc:
                critical(self, "Access denied", str(exc))
                return
        names = "\n".join(f"  • {Path(p).name}" for p in paths)
        label = "these items" if len(paths) > 1 else "this item"
        reply = question(
            self,
            "Confirm deletion",
            f"Delete {label} permanently?\n\n{names}",
            StandardButton.Yes | StandardButton.No,
            StandardButton.No,
        )
        if reply != StandardButton.Yes:
            return
        errors: list[str] = []
        for path_str in paths:
            p = Path(path_str)
            try:
                self._assert_within_kb_root(p)
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except ValueError as exc:
                errors.append(f"  {p.name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"  {p.name}: {exc}")
        if errors:
            critical(
                self,
                "Deletion errors",
                "Some items could not be deleted:\n" + "\n".join(errors),
            )
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """Refresh the tree view to reflect filesystem changes."""
        if self._kb_directory:
            self._set_tree_root(self._kb_directory)

    # ------------------------------------------------------------------
    # External refresh (called from MainWindow when project changes)
    # ------------------------------------------------------------------

    def refresh_kb_root(self, kb_directory: str | None) -> None:
        """Update the displayed KB root without emitting signals.

        Called from MainWindow when the project changes (new / open /
        set KB directory from menu) so this window stays in sync.
        """
        self._kb_directory = kb_directory
        if kb_directory:
            self._dir_label.setText(kb_directory)
            self._set_tree_root(kb_directory)
        else:
            self._dir_label.setText("(not set)")
            self._model.setRootPath("")
            self._tree.setRootIndex(QModelIndex())
        self._refresh_actions()
