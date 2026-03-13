from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from product_description_tool.collapsible_panel import CollapsiblePanel
from product_description_tool.config import AppConfig, ConfigStore, CsvConfig, FieldConfig
from product_description_tool.csv_repository import CsvDocument, CsvRepository
from product_description_tool.dialogs import (
    ActivityDialog,
    FilterDialog,
    HtmlEditorDialog,
    SettingsDialog,
)
from product_description_tool.filter_proxy import WildcardFilterProxyModel
from product_description_tool.generation import GenerationService
from product_description_tool.preview import HtmlPreview
from product_description_tool.project import Project, ProjectPrompt, ProjectRepository
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
        self.project_repository = ProjectRepository()
        self.generation_service = GenerationService()

        self.project = Project(csv=CsvConfig.from_dict(self.config.csv.to_dict()))
        self.document = CsvDocument(headers=[], rows=[])
        self.project_path: Path | None = None
        self.current_external_csv_path: Path | None = None

        self.last_original_preview_html = ""
        self.last_result_preview_html = ""
        self._worker_thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._activity_dialog: ActivityDialog | None = None
        self._activity_output_chars = 0
        self._activity_row_output_chars: dict[tuple[int, str], int] = {}
        self._busy = False
        self._project_modified = False
        self._updating_prompt_ui = False
        self.filter_patterns: dict[str, str] = {}

        self.table_model = CsvTableModel()
        self.proxy_model = WildcardFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self._build_ui()
        self._sync_project_with_document()
        self._refresh_prompt_controls()
        self._refresh_table_from_document()
        self._update_preview_field_selectors(preserve_selection=False)
        self._update_interactive_state()
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
        self.prompt_panel = CollapsiblePanel("Prompts")
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

        prompt_header = QHBoxLayout()
        self.prompt_selector = QComboBox()
        self.prompt_selector.currentIndexChanged.connect(self._on_prompt_selection_changed)
        prompt_header.addWidget(self.prompt_selector, 1)

        self.add_prompt_button = QPushButton("Add")
        self.add_prompt_button.clicked.connect(self.add_prompt)
        prompt_header.addWidget(self.add_prompt_button)

        self.delete_prompt_button = QPushButton("Delete")
        self.delete_prompt_button.clicked.connect(self.delete_prompt)
        prompt_header.addWidget(self.delete_prompt_button)

        self.toggle_prompt_button = QPushButton("Enabled")
        self.toggle_prompt_button.setCheckable(True)
        self.toggle_prompt_button.clicked.connect(self.toggle_current_prompt_enabled)
        prompt_header.addWidget(self.toggle_prompt_button)

        prompt_header.addStretch(1)

        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.preview_selected_row)
        prompt_header.addWidget(self.preview_button)

        prompt_layout.addLayout(prompt_header)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Use placeholders like {{product_name}}")
        self.prompt_edit.textChanged.connect(self._on_prompt_text_changed)
        prompt_layout.addWidget(self.prompt_edit)

        process_row = QHBoxLayout()
        process_row.addStretch(1)
        self.process_button = QPushButton("Process All")
        self.process_button.clicked.connect(self.process_all_rows)
        process_row.addWidget(self.process_button)
        prompt_layout.addLayout(process_row)

        description_layout = QVBoxLayout(self.description_panel.content)
        description_layout.setContentsMargins(0, 0, 0, 0)
        description_layout.setSpacing(8)

        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.left_field_combo = QComboBox()
        self.left_field_combo.currentIndexChanged.connect(self._refresh_current_selection)
        left_layout.addWidget(self.left_field_combo)
        self.original_preview = HtmlPreview()
        left_layout.addWidget(self.original_preview)
        left_button_row = QHBoxLayout()
        left_button_row.addStretch(1)
        self.edit_original_button = QPushButton("Edit")
        self.edit_original_button.clicked.connect(
            lambda checked=False: self.edit_selected_description(self.left_field_combo.currentText())
        )
        left_button_row.addWidget(self.edit_original_button)
        left_layout.addLayout(left_button_row)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.right_field_combo = QComboBox()
        self.right_field_combo.currentIndexChanged.connect(self._refresh_current_selection)
        right_layout.addWidget(self.right_field_combo)
        self.result_preview = HtmlPreview()
        right_layout.addWidget(self.result_preview)
        right_button_row = QHBoxLayout()
        right_button_row.addStretch(1)
        self.edit_result_button = QPushButton("Edit")
        self.edit_result_button.clicked.connect(
            lambda checked=False: self.edit_selected_description(self.right_field_combo.currentText())
        )
        right_button_row.addWidget(self.edit_result_button)
        right_layout.addLayout(right_button_row)

        preview_splitter.addWidget(left_container)
        preview_splitter.addWidget(right_container)
        preview_splitter.setSizes([1, 1])
        description_layout.addWidget(preview_splitter, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        self.new_project_action = QAction("New", self)
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action = QAction("Open", self)
        self.open_project_action.triggered.connect(self.open_project)
        self.save_project_action = QAction("Save", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.save_project_as_action = QAction("Save As", self)
        self.save_project_as_action.triggered.connect(
            lambda checked=False: self.save_project(save_as=True)
        )
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addActions(
            [
                self.new_project_action,
                self.open_project_action,
                self.save_project_action,
                self.save_project_as_action,
                exit_action,
            ]
        )

        csv_menu = menu_bar.addMenu("CSV")
        self.load_csv_action = QAction("Import", self)
        self.load_csv_action.triggered.connect(self.load_csv)
        self.store_csv_action = QAction("Export", self)
        self.store_csv_action.triggered.connect(self.save_csv)
        self.store_csv_as_action = QAction("Export As", self)
        self.store_csv_as_action.triggered.connect(lambda checked=False: self.save_csv(save_as=True))
        csv_menu.addActions([self.load_csv_action, self.store_csv_action, self.store_csv_as_action])

        edit_menu = menu_bar.addMenu("Edit")
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.edit_original_action = QAction("Original", self)
        self.edit_original_action.setShortcut(QKeySequence("Ctrl+O"))
        self.edit_original_action.triggered.connect(
            lambda checked=False: self.edit_selected_description(self.project.csv.original_description)
        )
        self.edit_result_action = QAction("Result", self)
        self.edit_result_action.setShortcut(QKeySequence("Ctrl+R"))
        self.edit_result_action.triggered.connect(
            lambda checked=False: self.edit_selected_description(self.project.csv.result_description)
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

    def _default_project(self) -> Project:
        return Project(csv=CsvConfig.from_dict(self.config.csv.to_dict()))

    def new_project(self) -> None:
        if not self._maybe_save_project():
            return
        self.project = self._default_project()
        self.document = CsvDocument(headers=[], rows=[])
        self.project_path = None
        self.current_external_csv_path = None
        self.filter_patterns = {}
        self._sync_project_with_document()
        self._refresh_prompt_controls()
        self._refresh_table_from_document()
        self._update_preview_field_selectors(preserve_selection=False)
        self._update_interactive_state()
        self._set_project_modified(False)
        self.status.showMessage("New project")

    def open_project(self) -> None:
        if not self._maybe_save_project():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(self.project_path.parent if self.project_path else ""),
            "Project Files (*.project.json);;All Files (*)",
        )
        if not path:
            return
        try:
            project_path = Path(path)
            project = self.project_repository.load(project_path)
            csv_path = self.project_repository.csv_path_for(project_path)
            if csv_path.exists():
                document = self.csv_repository.load(csv_path, project.csv)
            else:
                document = self._empty_document_for_project(project)
            self.project = project
            self.document = document
            self.project_path = project_path
            self.current_external_csv_path = None
            self.filter_patterns = {}
            self._sync_project_with_document()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._refresh_prompt_controls()
        self._refresh_table_from_document()
        self._update_preview_field_selectors(preserve_selection=False)
        self._update_interactive_state()
        self._set_project_modified(False)
        self.status.showMessage(f"Opened project {self.project_path}")

    def save_project(self, save_as: bool = False) -> bool:
        target_path = None if save_as else self.project_path
        if target_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                str(self.project_path or ""),
                "Project Files (*.project.json);;All Files (*)",
            )
            if not path:
                return False
            target_path = Path(path)
        target_path = self.project_repository.save(target_path, self.project)
        csv_path = self.project_repository.csv_path_for(target_path)
        try:
            self.csv_repository.save(csv_path, self.document, self.project.csv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        self.project_path = target_path
        self.config.csv = CsvConfig.from_dict(self.project.csv.to_dict())
        self._set_project_modified(False)
        self.status.showMessage(f"Saved project to {target_path}")
        return True

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            str(self.current_external_csv_path.parent if self.current_external_csv_path else ""),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        try:
            self.document = self.csv_repository.load(path, self.project.csv)
            self.current_external_csv_path = Path(path)
            self._sync_project_with_document()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self._refresh_table_from_document()
        self._update_preview_field_selectors(preserve_selection=False)
        self._set_project_modified(True)
        self.status.showMessage(f"Imported {len(self.document.rows)} rows from {path}")

    def save_csv(self, save_as: bool = False) -> None:
        target_path = None if save_as else self.current_external_csv_path
        if target_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export CSV",
                str(self.current_external_csv_path or ""),
                "CSV Files (*.csv);;All Files (*)",
            )
            if not path:
                return
            target_path = Path(path)
        try:
            self.csv_repository.save(target_path, self.document, self.project.csv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.current_external_csv_path = Path(target_path)
        self.status.showMessage(f"Exported CSV to {target_path}")

    def open_settings(self) -> None:
        selected_source_row = self._selected_source_row()
        dialog = SettingsDialog(
            self._dialog_config(),
            current_headers=self.document.headers,
            parent=self,
        )
        if dialog.exec():
            updated = dialog.get_config()
            self.config.provider = updated.provider
            self.config.generation = updated.generation
            self.project.csv = updated.csv
            self.config.csv = CsvConfig.from_dict(updated.csv.to_dict())
            self.config_store.save(self.config)
            self._sync_project_with_document()
            self.table_model.update_config(self.project.csv)
            self._sync_filter_patterns_with_visible_columns()
            self._apply_filter_patterns()
            self._fit_table_columns_to_window()
            self._update_filter_button_text()
            self._update_preview_field_selectors(preserve_selection=True)
            if selected_source_row is not None:
                self._restore_selected_source_row(selected_source_row)
            else:
                self._refresh_current_selection()
            self._set_project_modified(True)

    def add_prompt(self) -> None:
        output_field, accepted = QInputDialog.getText(
            self,
            "Add Prompt",
            "CSV output field:",
        )
        if not accepted:
            return
        output_field = output_field.strip()
        if not output_field:
            return
        existing = self._prompt_by_output_field(output_field)
        if existing is not None:
            QMessageBox.information(
                self,
                "Prompt exists",
                f"A prompt for '{output_field}' already exists.",
            )
            self._select_prompt_by_output_field(output_field)
            return
        self.project.prompts.append(ProjectPrompt(output_field=output_field))
        self._ensure_column(output_field)
        self._refresh_prompt_controls(preserve_field=output_field)
        self._refresh_table_from_document()
        self._update_preview_field_selectors(preserve_selection=True)
        self._update_interactive_state()
        self._set_project_modified(True)

    def delete_prompt(self) -> None:
        prompt = self._current_prompt()
        if prompt is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Prompt",
            f"Delete the prompt for '{prompt.output_field}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.prompts.remove(prompt)
        self._refresh_prompt_controls()
        self._update_preview_field_selectors(preserve_selection=True)
        self._update_interactive_state()
        self._set_project_modified(True)

    def toggle_current_prompt_enabled(self) -> None:
        prompt = self._current_prompt()
        if prompt is None:
            return
        enabled = self.toggle_prompt_button.isChecked()
        if prompt.enabled != enabled:
            prompt.enabled = enabled
            self._set_project_modified(True)
        self._update_prompt_toggle_text(prompt)
        self._update_interactive_state()

    def _on_prompt_text_changed(self) -> None:
        if self._updating_prompt_ui:
            return
        prompt = self._current_prompt()
        if prompt is None:
            return
        new_text = self.prompt_edit.toPlainText()
        if prompt.prompt != new_text:
            prompt.prompt = new_text
            self._set_project_modified(True)

    def _on_prompt_selection_changed(self) -> None:
        self._load_current_prompt_into_editor()

    def _load_current_prompt_into_editor(self) -> None:
        prompt = self._current_prompt()
        self._updating_prompt_ui = True
        self.prompt_edit.setPlainText("" if prompt is None else prompt.prompt)
        self._updating_prompt_ui = False
        if prompt is None:
            self.toggle_prompt_button.setChecked(False)
            self.toggle_prompt_button.setText("Enabled")
            self._update_interactive_state()
            return
        self.toggle_prompt_button.setChecked(prompt.enabled)
        self._update_prompt_toggle_text(prompt)
        self._update_interactive_state()

    def _refresh_prompt_controls(self, preserve_field: str | None = None) -> None:
        current_field = preserve_field or self.prompt_selector.currentText()
        self.prompt_selector.blockSignals(True)
        self.prompt_selector.clear()
        self.prompt_selector.addItems([prompt.output_field for prompt in self.project.prompts])
        if current_field:
            index = self.prompt_selector.findText(current_field)
            if index >= 0:
                self.prompt_selector.setCurrentIndex(index)
        if self.prompt_selector.currentIndex() < 0 and self.project.prompts:
            self.prompt_selector.setCurrentIndex(0)
        self.prompt_selector.blockSignals(False)
        self._load_current_prompt_into_editor()

    def _update_prompt_toggle_text(self, prompt: ProjectPrompt) -> None:
        self.toggle_prompt_button.setText("Enabled" if prompt.enabled else "Disabled")

    def preview_selected_row(self) -> None:
        prompt = self._current_prompt()
        if prompt is None:
            QMessageBox.warning(self, "No prompt", "Add or select a prompt first.")
            return
        if not self._validate_ready_for_generation([prompt]):
            return
        row_index = self._selected_source_row()
        if row_index is None:
            QMessageBox.warning(self, "No selection", "Select a row to preview.")
            return
        self._start_worker(prompts=[prompt], selected_row=row_index)

    def process_all_rows(self) -> None:
        prompts = self._enabled_prompts()
        if not prompts:
            QMessageBox.warning(self, "No enabled prompts", "Enable at least one prompt first.")
            return
        if not self._validate_ready_for_generation(prompts):
            return
        self._start_worker(prompts=prompts, selected_row=None)

    def _validate_ready_for_generation(self, prompts: list[ProjectPrompt]) -> bool:
        if not self.document.rows:
            QMessageBox.warning(self, "No data", "Import or open a project CSV first.")
            return False
        original_column = self.project.csv.original_description
        if original_column not in self.document.headers:
            QMessageBox.warning(
                self,
                "Missing column",
                f"Original description column '{original_column}' was not found in the CSV.",
            )
            return False
        for prompt in prompts:
            try:
                self.generation_service.validate_template(prompt.prompt, self.document.headers)
            except PromptTemplateError as exc:
                QMessageBox.critical(
                    self,
                    "Invalid prompt template",
                    "\n".join(
                        [
                            f"Prompt '{prompt.output_field}' has unknown placeholders:",
                            *exc.missing_fields,
                        ]
                    ),
                )
                return False
        return True

    def _start_worker(self, *, prompts: list[ProjectPrompt], selected_row: int | None) -> None:
        total_records, input_chars = self._build_activity_summary(
            prompts=prompts,
            selected_row=selected_row,
        )
        title = "Preview" if selected_row is not None else "Processing"
        if selected_row is not None:
            status = f"Previewing '{prompts[0].output_field}' for row {selected_row + 1}..."
        else:
            status = f"Processing {len(prompts)} prompt(s) across {len(self.document.rows)} row(s)..."
        self._activity_output_chars = 0
        self._activity_row_output_chars = {}
        self._show_activity_dialog(
            title=title,
            status=status,
            total_records=total_records,
            input_chars=input_chars,
        )
        self._set_busy(True)
        worker = GenerationWorker(
            service=self.generation_service,
            rows=self.document.rows,
            prompts=prompts,
            config=self._dialog_config(),
            selected_row=selected_row,
        )
        thread = QThread(self)
        self._worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.row_generated.connect(self._handle_row_generated)
        worker.chunk_generated.connect(self._handle_chunk_generated)
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
        self.status.showMessage(status)

    def _build_activity_summary(
        self,
        *,
        prompts: list[ProjectPrompt],
        selected_row: int | None,
    ) -> tuple[int, int]:
        rows = [self.document.rows[selected_row]] if selected_row is not None else self.document.rows
        prepare_prompt = getattr(self.generation_service, "prepare_prompt", None)
        if prepare_prompt is None:
            prepare_prompt = GenerationService().prepare_prompt
        input_chars = sum(
            prepare_prompt(template=prompt.prompt, row=row).input_char_count
            for prompt in prompts
            for row in rows
        )
        return (len(prompts) * len(rows), input_chars)

    def _handle_row_generated(self, row_index: int, output_field: str, content: str) -> None:
        streamed_chars = self._activity_row_output_chars.get((row_index, output_field), 0)
        actual_chars = len(content)
        if streamed_chars != actual_chars:
            self._activity_output_chars += actual_chars - streamed_chars
            self._activity_row_output_chars[(row_index, output_field)] = actual_chars
            self._update_activity_output_stats()
        existing = self.document.rows[row_index].get(output_field, "")
        self.document.rows[row_index][output_field] = content
        self.table_model.refresh_row(row_index)
        if existing != content:
            self._set_project_modified(True)
        if self._selected_source_row() == row_index:
            self._refresh_current_selection()

    def _handle_chunk_generated(self, row_index: int, output_field: str, chunk: str) -> None:
        key = (row_index, output_field)
        self._activity_row_output_chars[key] = self._activity_row_output_chars.get(key, 0) + len(chunk)
        self._activity_output_chars += len(chunk)
        dialog = self._activity_dialog
        if dialog is not None:
            dialog.set_status("Receiving output...")
        self._update_activity_output_stats()

    def _handle_worker_failed(self, message: str) -> None:
        self._close_activity_dialog()
        self._set_busy(False)
        self.status.showMessage("Generation failed")
        QMessageBox.critical(self, "Generation failed", message)

    def _handle_worker_completed(self) -> None:
        self._close_activity_dialog()
        self._set_busy(False)
        self.status.showMessage("Generation finished")

    def _handle_worker_cancelled(self) -> None:
        self._close_activity_dialog()
        self._set_busy(False)
        self.status.showMessage("Processing cancelled")

    def _handle_progress(self, completed: int, total: int) -> None:
        dialog = self._activity_dialog
        if dialog is None:
            return
        dialog.set_record_progress(completed, total)
        if total == 1:
            dialog.set_status("Waiting for model response..." if completed == 0 else "Finalizing preview...")
            return
        dialog.set_status(f"Processed {completed} of {total} prompt runs")

    def _show_activity_dialog(
        self,
        *,
        title: str,
        status: str,
        total_records: int,
        input_chars: int,
    ) -> None:
        dialog = ActivityDialog(self)
        dialog.cancel_requested.connect(self._cancel_processing)
        dialog.start_activity(
            title=title,
            status=status,
            total_records=total_records,
            input_chars=input_chars,
        )
        self._activity_dialog = dialog

    def _close_activity_dialog(self) -> None:
        if self._activity_dialog is None:
            return
        self._activity_dialog.close_activity()
        self._activity_dialog = None
        self._activity_output_chars = 0
        self._activity_row_output_chars = {}

    def _cancel_processing(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _clear_worker_state(self) -> None:
        self._worker = None
        self._worker_thread = None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_interactive_state()
        for action in [
            self.new_project_action,
            self.open_project_action,
            self.save_project_action,
            self.save_project_as_action,
            self.load_csv_action,
            self.store_csv_action,
            self.store_csv_as_action,
            self.settings_action,
            self.edit_original_action,
            self.edit_result_action,
            self.process_all_action,
            self.process_current_action,
        ]:
            action.setEnabled(not busy)

    def _update_interactive_state(self) -> None:
        prompt = self._current_prompt()
        has_left_field = self.left_field_combo.count() > 0
        has_right_field = self.right_field_combo.count() > 0

        self.filter_button.setEnabled(not self._busy)
        self.add_prompt_button.setEnabled(not self._busy)
        self.prompt_selector.setEnabled(not self._busy and bool(self.project.prompts))
        self.prompt_edit.setEnabled(not self._busy and prompt is not None)
        self.delete_prompt_button.setEnabled(not self._busy and prompt is not None)
        self.toggle_prompt_button.setEnabled(not self._busy and prompt is not None)
        self.preview_button.setEnabled(not self._busy and prompt is not None)
        self.process_button.setEnabled(not self._busy and bool(self._enabled_prompts()))
        self.left_field_combo.setEnabled(not self._busy and has_left_field)
        self.right_field_combo.setEnabled(not self._busy and has_right_field)
        self.edit_original_button.setEnabled(not self._busy and has_left_field)
        self.edit_result_button.setEnabled(not self._busy and has_right_field)

    def on_selection_changed(self) -> None:
        self._refresh_current_selection()

    def _refresh_current_selection(self) -> None:
        row_index = self._selected_source_row()
        if row_index is None:
            self._update_previews("", "")
            return
        row = self.document.rows[row_index]
        self._update_previews(
            row.get(self.left_field_combo.currentText(), ""),
            row.get(self.right_field_combo.currentText(), ""),
        )

    def _update_previews(self, original_html: str, result_html: str) -> None:
        self.last_original_preview_html = original_html
        self.last_result_preview_html = result_html
        self.original_preview.set_html(original_html)
        self.result_preview.set_html(result_html)

    def edit_selected_description(self, column_name: str) -> None:
        if not column_name:
            QMessageBox.warning(self, "No field", "Select a field first.")
            return
        row_index = self._selected_source_row()
        if row_index is None:
            QMessageBox.warning(self, "No selection", "Select a row first.")
            return
        self._ensure_column(column_name)
        row = self.document.rows[row_index]
        dialog = HtmlEditorDialog(
            title=f"Edit {column_name}",
            text=row.get(column_name, ""),
            parent=self,
        )
        if dialog.exec():
            new_text = dialog.text()
            if self.document.rows[row_index].get(column_name, "") != new_text:
                self._set_project_modified(True)
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

    def _refresh_table_from_document(self) -> None:
        selected_source_row = self._selected_source_row()
        self.table_model.set_document(self.document, self.project.csv)
        self.proxy_model.clear_filters()
        self._sync_filter_patterns_with_visible_columns()
        self._apply_filter_patterns()
        self._fit_table_columns_to_window()
        if selected_source_row is not None:
            self._restore_selected_source_row(selected_source_row)
        elif self.proxy_model.rowCount() > 0:
            self.table_view.selectRow(0)
        else:
            self._update_previews("", "")
        self._update_filter_button_text()

    def _selected_source_row(self) -> int | None:
        index = self.table_view.currentIndex()
        if not index.isValid():
            return None
        return self.proxy_model.mapToSource(index).row()

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

    def _update_filter_button_text(self) -> None:
        active_count = len(self.filter_patterns)
        self.filter_button.setText(f"Filter ({active_count})" if active_count else "Filter")

    def _update_preview_field_selectors(self, *, preserve_selection: bool) -> None:
        headers = list(self.document.headers)
        left_current = self.left_field_combo.currentText() if preserve_selection else ""
        right_current = self.right_field_combo.currentText() if preserve_selection else ""
        left_target = self._preferred_left_field(left_current, headers)
        right_target = self._preferred_right_field(right_current, headers, left_target)

        for combo, target in [
            (self.left_field_combo, left_target),
            (self.right_field_combo, right_target),
        ]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(headers)
            if target:
                index = combo.findText(target)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
            combo.setEnabled(bool(headers))

        self._update_interactive_state()
        self._refresh_current_selection()

    def _preferred_left_field(self, current_field: str, headers: list[str]) -> str:
        for candidate in [current_field, self.project.csv.original_description]:
            if candidate and candidate in headers:
                return candidate
        return headers[0] if headers else ""

    def _preferred_right_field(
        self,
        current_field: str,
        headers: list[str],
        left_field: str,
    ) -> str:
        default_prompt_field = self.project.prompts[0].output_field if self.project.prompts else ""
        candidates = [current_field, default_prompt_field, self.project.csv.result_description]
        for candidate in candidates:
            if candidate and candidate in headers:
                return candidate
        for header in headers:
            if header != left_field:
                return header
        return headers[0] if headers else ""

    def _sync_project_with_document(self) -> None:
        self.config.csv = CsvConfig.from_dict(self.project.csv.to_dict())
        for header in list(self.document.headers):
            self._ensure_field_config(header)
        for required in [
            self.project.csv.original_description,
            self.project.csv.result_description,
            *[prompt.output_field for prompt in self.project.prompts],
        ]:
            self._ensure_column(required)

    def _ensure_column(self, column_name: str) -> None:
        if not column_name:
            return
        self.csv_repository.ensure_column(self.document, column_name)
        self._ensure_field_config(column_name)

    def _ensure_field_config(self, header: str) -> None:
        if not header:
            return
        self.project.csv.fields.setdefault(header, FieldConfig(label=header, show=True))

    def _empty_document_for_project(self, project: Project) -> CsvDocument:
        headers: list[str] = []
        for header in [
            project.csv.original_description,
            project.csv.result_description,
            *project.csv.fields.keys(),
            *[prompt.output_field for prompt in project.prompts],
        ]:
            if header and header not in headers:
                headers.append(header)
        return CsvDocument(headers=headers, rows=[])

    def _dialog_config(self) -> AppConfig:
        return AppConfig.from_dict(
            {
                "provider": {
                    "active": self.config.provider.active,
                    "ollama": {
                        "base_url": self.config.provider.ollama.base_url,
                        "model": self.config.provider.ollama.model,
                        "options": dict(self.config.provider.ollama.options),
                    },
                    "openai": {
                        "base_url": self.config.provider.openai.base_url,
                        "api_key": self.config.provider.openai.api_key,
                        "model": self.config.provider.openai.model,
                        "options": dict(self.config.provider.openai.options),
                    },
                },
                "generation": {
                    "temperature": self.config.generation.temperature,
                    "top_p": self.config.generation.top_p,
                    "max_output_tokens": self.config.generation.max_output_tokens,
                },
                "csv": self.project.csv.to_dict(),
            }
        )

    def _prompt_by_output_field(self, output_field: str) -> ProjectPrompt | None:
        for prompt in self.project.prompts:
            if prompt.output_field == output_field:
                return prompt
        return None

    def _current_prompt(self) -> ProjectPrompt | None:
        index = self.prompt_selector.currentIndex()
        if index < 0 or index >= len(self.project.prompts):
            return None
        return self.project.prompts[index]

    def _enabled_prompts(self) -> list[ProjectPrompt]:
        return [prompt for prompt in self.project.prompts if prompt.enabled]

    def _select_prompt_by_output_field(self, output_field: str) -> None:
        index = self.prompt_selector.findText(output_field)
        if index >= 0:
            self.prompt_selector.setCurrentIndex(index)

    def _fit_table_columns_to_window(self) -> None:
        header = self.table_view.horizontalHeader()
        column_count = self.proxy_model.columnCount()
        if column_count == 0:
            return

        self.table_view.resizeColumnsToContents()
        available_width = max(self.table_view.viewport().width() - 2, 1)
        base_widths = [max(self.table_view.columnWidth(column), 60) for column in range(column_count)]
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

    def _update_activity_output_stats(self) -> None:
        if self._activity_dialog is not None:
            self._activity_dialog.set_output_stats(self._activity_output_chars)

    def _set_project_modified(self, modified: bool) -> None:
        self._project_modified = modified
        self.setWindowModified(modified)
        self._update_window_title()

    def _update_window_title(self) -> None:
        if self.project_path is None:
            self.setWindowTitle("Untitled Project[*] - Product Description Tool")
            return
        self.setWindowTitle(f"{self.project_path}[*] - Product Description Tool")

    def _maybe_save_project(self) -> bool:
        if not self._project_modified:
            return True
        answer = QMessageBox.warning(
            self,
            "Unsaved changes",
            "The current project has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return self.save_project()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker_thread is not None:
            QMessageBox.warning(
                self,
                "Processing in progress",
                "Cancel the current processing run before closing the application.",
            )
            event.ignore()
            return
        if not self._maybe_save_project():
            event.ignore()
            return
        super().closeEvent(event)
