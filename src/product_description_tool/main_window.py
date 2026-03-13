from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from product_description_tool.collapsible_panel import CollapsiblePanel
from product_description_tool.config import AppConfig, ConfigStore
from product_description_tool.csv_repository import CsvDocument, CsvRepository
from product_description_tool.dialogs import FilterDialog, HtmlEditorDialog, SettingsDialog
from product_description_tool.filter_proxy import WildcardFilterProxyModel
from product_description_tool.generation import GenerationService
from product_description_tool.preview import HtmlPreview
from product_description_tool.prompt_renderer import PromptTemplateError
from product_description_tool.table_model import CsvTableModel
from product_description_tool.worker import GenerationWorker


class MainWindow(QMainWindow):
    def __init__(self, *, config_store: ConfigStore) -> None:
        super().__init__()
        self.setWindowTitle("Product Description Tool")
        self.resize(1500, 960)

        self.config_store = config_store
        self.config = self.config_store.load()
        self.csv_repository = CsvRepository()
        self.generation_service = GenerationService()

        self.document: CsvDocument | None = None
        self.last_original_preview_html = ""
        self.last_result_preview_html = ""
        self._worker_thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self.current_prompt_path: Path | None = None
        self.current_csv_path: Path | None = None
        self._document_modified = False
        self.filter_patterns: dict[str, str] = {}

        self.table_model = CsvTableModel()
        self.proxy_model = WildcardFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()
        self._refresh_table_from_document()
        self._update_window_title()
        QTimer.singleShot(0, self._rebalance_panel_sizes)

    def _build_ui(self) -> None:
        self._build_menus()
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        self.setCentralWidget(central)

        self.sections_splitter = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(self.sections_splitter, 1)

        self.csv_panel = CollapsiblePanel("CSV Data")
        self.prompt_panel = CollapsiblePanel("System Prompt")
        self.description_panel = CollapsiblePanel("Description")

        for panel in [self.csv_panel, self.prompt_panel, self.description_panel]:
            panel.toggled.connect(self._rebalance_panel_sizes)
            self.sections_splitter.addWidget(panel)
        self.sections_splitter.setChildrenCollapsible(False)

        csv_layout = QVBoxLayout(self.csv_panel.content)
        csv_layout.setContentsMargins(0, 0, 0, 0)
        csv_layout.setSpacing(8)

        table_actions = QHBoxLayout()
        self.filter_button = QPushButton("Filter")
        self.filter_button.clicked.connect(self.open_filter_dialog)
        table_actions.addWidget(self.filter_button)
        table_actions.addStretch(1)
        csv_layout.addLayout(table_actions)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setSortingEnabled(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        csv_layout.addWidget(self.table_view, 1)

        prompt_layout = QVBoxLayout(self.prompt_panel.content)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(8)
        self.prompt_path_label = QLabel("Prompt file: unsaved")
        prompt_layout.addWidget(self.prompt_path_label)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Use placeholders like {{product_name}}")
        prompt_layout.addWidget(self.prompt_edit)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.preview_button = QPushButton("Preview Selected")
        self.preview_button.clicked.connect(self.preview_selected_row)
        self.process_button = QPushButton("Process All")
        self.process_button.clicked.connect(self.process_all_rows)
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.process_button)
        prompt_layout.addLayout(action_row)

        description_layout = QVBoxLayout(self.description_panel.content)
        description_layout.setContentsMargins(0, 0, 0, 0)
        description_layout.setSpacing(8)

        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        original_container = QWidget()
        original_layout = QVBoxLayout(original_container)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(6)
        original_layout.addWidget(QLabel("Original"))
        self.original_preview = HtmlPreview()
        original_layout.addWidget(self.original_preview)
        self.edit_original_button = QPushButton("Edit Original")
        self.edit_original_button.clicked.connect(
            lambda checked=False: self.edit_selected_description(self.config.csv.original_description)
        )
        original_layout.addWidget(self.edit_original_button, alignment=Qt.AlignmentFlag.AlignRight)

        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(6)
        result_layout.addWidget(QLabel("Produced"))
        self.result_preview = HtmlPreview()
        result_layout.addWidget(self.result_preview)
        self.edit_result_button = QPushButton("Edit Result")
        self.edit_result_button.clicked.connect(
            lambda checked=False: self.edit_selected_description(self.config.csv.result_description)
        )
        result_layout.addWidget(self.edit_result_button, alignment=Qt.AlignmentFlag.AlignRight)

        preview_splitter.addWidget(original_container)
        preview_splitter.addWidget(result_container)
        preview_splitter.setSizes([1, 1])
        description_layout.addWidget(preview_splitter, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        csv_menu = menu_bar.addMenu("CSV")
        self.load_csv_action = QAction("Load", self)
        self.load_csv_action.triggered.connect(self.load_csv)
        self.store_csv_action = QAction("Store", self)
        self.store_csv_action.triggered.connect(self.save_csv)
        self.store_csv_as_action = QAction("Store As", self)
        self.store_csv_as_action.triggered.connect(lambda checked=False: self.save_csv(save_as=True))
        csv_menu.addActions([self.load_csv_action, self.store_csv_action, self.store_csv_as_action])

        prompt_menu = menu_bar.addMenu("Prompt")
        self.load_prompt_action = QAction("Load", self)
        self.load_prompt_action.triggered.connect(self.load_prompt)
        self.store_prompt_action = QAction("Store", self)
        self.store_prompt_action.triggered.connect(self.save_prompt)
        self.store_prompt_as_action = QAction("Store As", self)
        self.store_prompt_as_action.triggered.connect(
            lambda checked=False: self.save_prompt(save_as=True)
        )
        prompt_menu.addActions(
            [self.load_prompt_action, self.store_prompt_action, self.store_prompt_as_action]
        )

        edit_menu = menu_bar.addMenu("Edit")
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.edit_original_action = QAction("Original", self)
        self.edit_original_action.setShortcut(QKeySequence("Ctrl+O"))
        self.edit_original_action.triggered.connect(
            lambda checked=False: self.edit_selected_description(self.config.csv.original_description)
        )
        self.edit_result_action = QAction("Result", self)
        self.edit_result_action.setShortcut(QKeySequence("Ctrl+R"))
        self.edit_result_action.triggered.connect(
            lambda checked=False: self.edit_selected_description(self.config.csv.result_description)
        )
        edit_menu.addActions([self.settings_action, self.edit_original_action, self.edit_result_action])

        process_menu = menu_bar.addMenu("Process")
        self.process_all_action = QAction("All", self)
        self.process_all_action.setShortcut(QKeySequence("Ctrl+P"))
        self.process_all_action.triggered.connect(self.process_all_rows)
        self.process_current_action = QAction("Current", self)
        self.process_current_action.setShortcut(QKeySequence("Ctrl+Enter"))
        self.process_current_action.triggered.connect(self.preview_selected_row)
        process_menu.addActions([self.process_all_action, self.process_current_action])

    def _refresh_table_from_document(self) -> None:
        selected_source_row = self._selected_source_row()
        self.table_model.set_document(self.document, self.config.csv)
        self.proxy_model.clear_filters()
        self.filter_patterns = {}
        self._fit_table_columns_to_window()
        if selected_source_row is not None:
            self._restore_selected_source_row(selected_source_row)
        elif self.proxy_model.rowCount() > 0:
            self.table_view.selectRow(0)
        else:
            self._update_previews("", "")
        self._update_filter_button_text()

    def open_settings(self) -> None:
        selected_source_row = self._selected_source_row()
        dialog = SettingsDialog(
            self.config,
            current_headers=self.document.headers if self.document is not None else [],
            parent=self,
        )
        if dialog.exec():
            self.config = dialog.get_config()
            self.config_store.save(self.config)
            self.table_model.update_config(self.config.csv)
            self._sync_filter_patterns_with_visible_columns()
            self._apply_filter_patterns()
            self._ensure_result_column()
            self._fit_table_columns_to_window()
            self._update_filter_button_text()
            if selected_source_row is not None:
                self._restore_selected_source_row(selected_source_row)
            else:
                self._refresh_current_selection()

    def load_prompt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Prompt",
            "",
            "Text Files (*.txt *.md *.prompt);;All Files (*)",
        )
        if not path:
            return
        self.current_prompt_path = Path(path)
        self.prompt_edit.setPlainText(Path(path).read_text(encoding="utf-8"))
        self._update_prompt_path_label()

    def save_prompt(self, save_as: bool = False) -> None:
        target_path = self.current_prompt_path if not save_as else None
        if target_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Prompt",
                str(self.current_prompt_path or ""),
                "Text Files (*.txt *.md *.prompt);;All Files (*)",
            )
            if not path:
                return
            target_path = Path(path)
        target_path.write_text(self.prompt_edit.toPlainText(), encoding="utf-8")
        self.current_prompt_path = target_path
        self._update_prompt_path_label()
        self.status.showMessage(f"Saved prompt to {target_path}")

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV",
            str(self.current_csv_path.parent if self.current_csv_path else ""),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        try:
            self.document = self.csv_repository.load(path, self.config.csv)
            self._ensure_result_column()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))
            return

        self.current_csv_path = Path(path)
        self._set_document_modified(False)
        self._refresh_table_from_document()
        self.status.showMessage(f"Loaded {len(self.document.rows)} rows from {path}")

    def save_csv(self, save_as: bool = False) -> None:
        if self.document is None:
            QMessageBox.warning(self, "Nothing to save", "Load a CSV file first.")
            return
        target_path = None if save_as else self.current_csv_path
        if target_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save CSV",
                str(self.current_csv_path or ""),
                "CSV Files (*.csv);;All Files (*)",
            )
            if not path:
                return
            target_path = Path(path)
        try:
            self.csv_repository.save(target_path, self.document, self.config.csv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.current_csv_path = target_path
        self._set_document_modified(False)
        self.status.showMessage(f"Saved CSV to {target_path}")

    def _ensure_result_column(self) -> None:
        if self.document is None:
            return
        self.csv_repository.ensure_column(self.document, self.config.csv.result_description)

    def _validate_ready_for_generation(self) -> bool:
        if self.document is None:
            QMessageBox.warning(self, "No data", "Load a CSV file first.")
            return False
        original_column = self.config.csv.original_description
        if original_column not in self.document.headers:
            QMessageBox.warning(
                self,
                "Missing column",
                f"Original description column '{original_column}' was not found in the CSV.",
            )
            return False
        try:
            self.generation_service.validate_template(
                self.prompt_edit.toPlainText(),
                self.document.headers,
            )
        except PromptTemplateError as exc:
            QMessageBox.critical(
                self,
                "Invalid prompt template",
                "\n".join(["Unknown placeholders:"] + exc.missing_fields),
            )
            return False
        return True

    def _selected_source_row(self) -> int | None:
        index = self.table_view.currentIndex()
        if not index.isValid():
            return None
        return self.proxy_model.mapToSource(index).row()

    def preview_selected_row(self) -> None:
        if not self._validate_ready_for_generation():
            return
        row_index = self._selected_source_row()
        if row_index is None:
            QMessageBox.warning(self, "No selection", "Select a row to preview.")
            return
        self._start_worker(selected_row=row_index, show_progress=False)

    def process_all_rows(self) -> None:
        if not self._validate_ready_for_generation():
            return
        self._start_worker(selected_row=None, show_progress=True)

    def _start_worker(self, *, selected_row: int | None, show_progress: bool) -> None:
        if self.document is None:
            return
        self._set_busy(True)
        worker = GenerationWorker(
            service=self.generation_service,
            rows=self.document.rows,
            template=self.prompt_edit.toPlainText(),
            config=self.config,
            selected_row=selected_row,
        )
        thread = QThread(self)
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.row_generated.connect(self._handle_row_generated)
        worker.failed.connect(self._handle_worker_failed)
        worker.completed.connect(self._handle_worker_completed)
        worker.cancelled.connect(self._handle_worker_cancelled)
        worker.progress.connect(self._handle_progress)
        worker.completed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_state)
        self._worker_thread = thread
        thread.start()
        if selected_row is None:
            self.status.showMessage("Processing all rows...")
            if show_progress:
                self._show_progress_dialog(len(self.document.rows))
        else:
            self.status.showMessage(f"Previewing row {selected_row + 1}...")

    def _handle_row_generated(self, row_index: int, content: str) -> None:
        if self.document is None:
            return
        existing = self.document.rows[row_index].get(self.config.csv.result_description, "")
        self.document.rows[row_index][self.config.csv.result_description] = content
        self.table_model.refresh_row(row_index)
        if existing != content:
            self._set_document_modified(True)
        selected = self._selected_source_row()
        if selected == row_index:
            original = self.document.rows[row_index].get(self.config.csv.original_description, "")
            self._update_previews(original, content)

    def _handle_worker_failed(self, message: str) -> None:
        self._close_progress_dialog()
        self._set_busy(False)
        self.status.showMessage("Generation failed")
        QMessageBox.critical(self, "Generation failed", message)

    def _handle_worker_completed(self) -> None:
        self._close_progress_dialog()
        self._set_busy(False)
        self.status.showMessage("Generation finished")

    def _handle_worker_cancelled(self) -> None:
        self._close_progress_dialog()
        self._set_busy(False)
        self.status.showMessage("Processing cancelled")

    def _handle_progress(self, completed: int, total: int) -> None:
        dialog = self._progress_dialog
        if dialog is None:
            return
        dialog.setMaximum(total)
        dialog.setValue(completed)
        dialog.setLabelText(f"Processed {completed} of {total} rows")

    def _show_progress_dialog(self, total_rows: int) -> None:
        dialog = QProgressDialog("Processed 0 rows", "Cancel", 0, total_rows, self)
        dialog.setWindowTitle("Processing")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(self._cancel_processing)
        self._progress_dialog = dialog
        dialog.show()

    def _close_progress_dialog(self) -> None:
        if self._progress_dialog is None:
            return
        self._progress_dialog.close()
        self._progress_dialog.deleteLater()
        self._progress_dialog = None

    def _cancel_processing(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _clear_worker_state(self) -> None:
        self._worker = None
        self._worker_thread = None

    def _set_busy(self, busy: bool) -> None:
        for button in [
            self.filter_button,
            self.preview_button,
            self.process_button,
            self.edit_original_button,
            self.edit_result_button,
        ]:
            button.setEnabled(not busy)
        for action in [
            self.load_csv_action,
            self.store_csv_action,
            self.store_csv_as_action,
            self.load_prompt_action,
            self.store_prompt_action,
            self.store_prompt_as_action,
            self.settings_action,
            self.edit_original_action,
            self.edit_result_action,
            self.process_all_action,
            self.process_current_action,
        ]:
            action.setEnabled(not busy)

    def on_selection_changed(self) -> None:
        self._refresh_current_selection()

    def _refresh_current_selection(self) -> None:
        if self.document is None:
            self._update_previews("", "")
            return
        row_index = self._selected_source_row()
        if row_index is None:
            self._update_previews("", "")
            return
        row = self.document.rows[row_index]
        self._update_previews(
            row.get(self.config.csv.original_description, ""),
            row.get(self.config.csv.result_description, ""),
        )

    def _update_previews(self, original_html: str, result_html: str) -> None:
        self.last_original_preview_html = original_html
        self.last_result_preview_html = result_html
        self.original_preview.set_html(original_html)
        self.result_preview.set_html(result_html)

    def edit_selected_description(self, column_name: str) -> None:
        if self.document is None:
            QMessageBox.warning(self, "No data", "Load a CSV file first.")
            return
        row_index = self._selected_source_row()
        if row_index is None:
            QMessageBox.warning(self, "No selection", "Select a row first.")
            return
        self.csv_repository.ensure_column(self.document, column_name)
        row = self.document.rows[row_index]
        dialog = HtmlEditorDialog(
            title=f"Edit {column_name}",
            text=row.get(column_name, ""),
            parent=self,
        )
        if dialog.exec():
            new_text = dialog.text()
            if self.document.rows[row_index].get(column_name, "") != new_text:
                self._set_document_modified(True)
            self.document.rows[row_index][column_name] = new_text
            self.table_model.refresh_row(row_index)
            self._refresh_current_selection()

    def open_filter_dialog(self) -> None:
        column_labels = [
            (
                header,
                str(
                    self.table_model.headerData(
                        index,
                        Qt.Orientation.Horizontal,
                        Qt.ItemDataRole.DisplayRole,
                    )
                ),
            )
            for index, header in enumerate(self.table_model.visible_headers)
        ]
        dialog = FilterDialog(
            column_labels=column_labels,
            current_filters=self.filter_patterns,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.filter_patterns = dialog.filters()
            self._apply_filter_patterns()
            self._update_filter_button_text()

    def _update_filter_button_text(self) -> None:
        active_count = len(self.filter_patterns)
        if active_count:
            self.filter_button.setText(f"Filter ({active_count})")
        else:
            self.filter_button.setText("Filter")

    def _update_prompt_path_label(self) -> None:
        if self.current_prompt_path is None:
            self.prompt_path_label.setText("Prompt file: unsaved")
        else:
            self.prompt_path_label.setText(f"Prompt file: {self.current_prompt_path}")

    def _fit_table_columns_to_window(self) -> None:
        header = self.table_view.horizontalHeader()
        column_count = self.proxy_model.columnCount()
        if column_count == 0:
            return

        self.table_view.resizeColumnsToContents()
        available_width = max(self.table_view.viewport().width() - 2, 1)
        base_widths = [
            max(self.table_view.columnWidth(column), 60)
            for column in range(column_count)
        ]
        total_width = sum(base_widths)
        if total_width <= 0:
            return

        minimum_width = max(40, available_width // column_count)
        scaled_widths = []
        remaining_width = available_width
        for index, width in enumerate(base_widths):
            if index == column_count - 1:
                scaled = max(minimum_width, remaining_width)
            else:
                scaled = max(minimum_width, round(available_width * width / total_width))
                remaining_width -= scaled
                columns_left = column_count - index - 1
                minimum_reserved = columns_left * minimum_width
                if remaining_width < minimum_reserved:
                    overflow = minimum_reserved - remaining_width
                    scaled = max(minimum_width, scaled - overflow)
                    remaining_width += overflow
            scaled_widths.append(scaled)

        adjusted_total = sum(scaled_widths)
        if adjusted_total != available_width:
            scaled_widths[-1] = max(
                minimum_width,
                scaled_widths[-1] + (available_width - adjusted_total),
            )

        for column, width in enumerate(scaled_widths):
            self.table_view.setColumnWidth(column, width)
        header.setStretchLastSection(False)

    def _rebalance_panel_sizes(self, *_args) -> None:
        panels = [self.csv_panel, self.prompt_panel, self.description_panel]
        total_height = self.sections_splitter.size().height()
        if total_height <= 0:
            return
        handle_space = self.sections_splitter.handleWidth() * max(len(panels) - 1, 0)
        collapsed_space = sum(panel.header_height() for panel in panels if not panel.expanded)
        expanded_panels = [panel for panel in panels if panel.expanded]
        remaining_height = max(total_height - handle_space - collapsed_space, 0)

        sizes: list[int] = []
        for panel in panels:
            if not panel.expanded:
                sizes.append(panel.header_height())
                continue
            if not expanded_panels:
                sizes.append(panel.header_height())
                continue
            sizes.append(max(panel.header_height() * 2, remaining_height // len(expanded_panels)))
        self.sections_splitter.setSizes(sizes)

    def _restore_selected_source_row(self, row_index: int) -> None:
        source_index = self.table_model.index(row_index, 0)
        if not source_index.isValid():
            self._refresh_current_selection()
            return
        proxy_index = self.proxy_model.mapFromSource(source_index)
        if proxy_index.isValid():
            self.table_view.selectRow(proxy_index.row())
            self.table_view.scrollTo(proxy_index)
        else:
            self._refresh_current_selection()

    def _sync_filter_patterns_with_visible_columns(self) -> None:
        visible_headers = set(self.table_model.visible_headers)
        self.filter_patterns = {
            header: pattern
            for header, pattern in self.filter_patterns.items()
            if header in visible_headers
        }

    def _apply_filter_patterns(self) -> None:
        self.proxy_model.clear_filters()
        for index, header in enumerate(self.table_model.visible_headers):
            self.proxy_model.set_filter_pattern(index, self.filter_patterns.get(header, ""))

    def _set_document_modified(self, modified: bool) -> None:
        self._document_modified = modified
        self.setWindowModified(modified)
        self._update_window_title()

    def _update_window_title(self) -> None:
        if self.current_csv_path is None:
            self.setWindowTitle("Product Description Tool[*]")
            return
        self.setWindowTitle(f"{self.current_csv_path}[*] - Product Description Tool")
