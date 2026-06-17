"""Tests for the prompt-attachments feature.

Covers:
- GenerationService.validate_attachments — validation of KB file and CSV column sources
- GenerationService.build_effective_prompt — attachment content assembly with provenance
- AttachmentManager internal mechanics — cost warning, insert ordering, status resolution
- AttachmentManager dialog as a unit (with sub-dialogs stubbed)
- Attachment metadata persistence round-trip through ProjectPrompt and ProjectRepository
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from product_description_tool.generation import GenerationService
from product_description_tool.project import (
    PromptAttachment,
    Project,
    ProjectPrompt,
    ProjectRepository,
)


# =========================================================================
# GenerationService.validate_attachments
# =========================================================================


class TestValidateAttachments:
    """Unit tests for GenerationService.validate_attachments()."""

    # ── CSV column attachments ────────────────────────────────────────

    def test_column_valid(self) -> None:
        """A CSV-column attachment for an existing header passes."""
        attachments = [PromptAttachment(source_type="csv_column", source="sku")]
        GenerationService.validate_attachments(attachments, headers=["sku", "name"])

    def test_column_missing(self) -> None:
        """A CSV-column attachment for a non-existent header raises ValueError."""
        attachments = [PromptAttachment(source_type="csv_column", source="nonexistent")]
        with pytest.raises(ValueError, match="column not found"):
            GenerationService.validate_attachments(attachments, headers=["sku", "name"])

    # ── KB file attachments ───────────────────────────────────────────

    def test_kb_file_valid(self, tmp_path: Path) -> None:
        """A KB-file attachment for an existing supported file passes."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "help.md").write_text("help", encoding="utf-8")
        attachments = [PromptAttachment(source_type="kb_file", source="help.md")]
        GenerationService.validate_attachments(
            attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
        )

    def test_kb_file_no_kb_dir(self) -> None:
        """A KB-file attachment without a configured KB directory raises ValueError."""
        attachments = [PromptAttachment(source_type="kb_file", source="help.md")]
        with pytest.raises(ValueError, match="knowledge-base directory"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=None,
            )

    def test_kb_file_escaping(self, tmp_path: Path) -> None:
        """A KB-file attachment whose path escapes the KB directory raises ValueError."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        attachments = [PromptAttachment(source_type="kb_file", source="../secret.md")]
        with pytest.raises(ValueError, match="path escapes"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
            )

    def test_kb_file_not_found(self, tmp_path: Path) -> None:
        """A KB-file attachment for a non-existent file raises ValueError."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        attachments = [PromptAttachment(source_type="kb_file", source="missing.md")]
        with pytest.raises(ValueError, match="file not found"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
            )

    def test_kb_file_not_a_file(self, tmp_path: Path) -> None:
        """A KB-file attachment pointing to a directory raises ValueError."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "subdir").mkdir()
        attachments = [PromptAttachment(source_type="kb_file", source="subdir")]
        with pytest.raises(ValueError, match="not a file"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
            )

    def test_kb_file_unsupported_type(self, tmp_path: Path) -> None:
        """A KB-file attachment with an unsupported extension raises ValueError."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "data.py").write_text("x = 1", encoding="utf-8")
        attachments = [PromptAttachment(source_type="kb_file", source="data.py")]
        with pytest.raises(ValueError, match="unsupported file type"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
            )

    # ── Unknown type ──────────────────────────────────────────────────

    def test_unknown_type(self) -> None:
        """An attachment with an unknown source_type raises ValueError."""
        attachments = [PromptAttachment(source_type="unknown_type", source="whatever")]
        with pytest.raises(ValueError, match="unknown source type"):
            GenerationService.validate_attachments(attachments, headers=["sku"])

    # ── Mixed / multi-attachment ──────────────────────────────────────

    def test_multiple_valid_mixed(self, tmp_path: Path) -> None:
        """Mixed valid KB-file and CSV-column attachments pass."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "guide.md").write_text("guide", encoding="utf-8")
        attachments = [
            PromptAttachment(source_type="kb_file", source="guide.md"),
            PromptAttachment(source_type="csv_column", source="sku"),
        ]
        GenerationService.validate_attachments(
            attachments, headers=["sku", "name"], knowledge_base_dir=str(kb_dir),
        )

    def test_first_invalid_fails_early(self, tmp_path: Path) -> None:
        """Validation stops at the first invalid attachment."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        attachments = [
            PromptAttachment(source_type="csv_column", source="missing_col"),
            PromptAttachment(source_type="kb_file", source="guide.md"),
        ]
        with pytest.raises(ValueError, match="column not found"):
            GenerationService.validate_attachments(
                attachments, headers=["sku"], knowledge_base_dir=str(kb_dir),
            )


# =========================================================================
# GenerationService.build_effective_prompt
# =========================================================================


class TestBuildEffectivePrompt:
    """Unit tests for GenerationService.build_effective_prompt()."""

    def test_no_attachments(self) -> None:
        """Without attachments, the rendered template is returned unchanged."""
        result = GenerationService.build_effective_prompt(
            rendered_template="Hello {{name}}",
            attachments=[],
            row={"name": "world"},
        )
        assert result == "Hello {{name}}"

    def test_column_attachment(self) -> None:
        """A CSV-column attachment appends the column value with provenance."""
        attachments = [PromptAttachment(source_type="csv_column", source="desc")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Rewrite:",
            attachments=attachments,
            row={"desc": "Great product text", "sku": "A-1"},
        )
        assert "Rewrite:" in result
        assert "column 'desc'" in result
        assert "Great product text" in result

    def test_kb_attachment(self, tmp_path: Path) -> None:
        """A KB-file attachment appends the file content with provenance."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "help.md").write_text("Helpful knowledge", encoding="utf-8")
        attachments = [PromptAttachment(source_type="kb_file", source="help.md")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Rewrite:",
            attachments=attachments,
            row={"sku": "A-1"},
            knowledge_base_dir=str(kb_dir),
        )
        assert "Rewrite:" in result
        assert "knowledge-base file 'help.md'" in result
        assert "Helpful knowledge" in result

    def test_mixed_attachments_kb_first(self, tmp_path: Path) -> None:
        """KB-file then CSV-column attachments are appended in attachment order."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "guide.md").write_text("Guide content", encoding="utf-8")
        attachments = [
            PromptAttachment(source_type="kb_file", source="guide.md"),
            PromptAttachment(source_type="csv_column", source="desc"),
        ]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"desc": "Desc value", "sku": "A-1"},
            knowledge_base_dir=str(kb_dir),
        )
        assert "Template:" in result
        kb_pos = result.index("knowledge-base file 'guide.md'")
        col_pos = result.index("column 'desc'")
        assert kb_pos < col_pos, (
            "KB attachment should appear before CSV column attachment"
        )
        assert "Guide content" in result
        assert "Desc value" in result

    def test_column_before_kb_order_respected(self, tmp_path: Path) -> None:
        """When CSV column is ordered before KB file, that user order is respected."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "guide.md").write_text("Guide", encoding="utf-8")
        attachments = [
            PromptAttachment(source_type="csv_column", source="desc"),
            PromptAttachment(source_type="kb_file", source="guide.md"),
        ]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"desc": "Desc"},
            knowledge_base_dir=str(kb_dir),
        )
        col_pos = result.index("column 'desc'")
        kb_pos = result.index("knowledge-base file 'guide.md'")
        assert col_pos < kb_pos, (
            "CSV column attachment should appear before KB file per user ordering"
        )

    def test_column_attachment_empty_value(self) -> None:
        """An empty CSV column value is still appended with provenance."""
        attachments = [PromptAttachment(source_type="csv_column", source="desc")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"desc": "", "sku": "A-1"},
        )
        assert "column 'desc'" in result
        assert "--- Attachment:" in result
        assert "--- End attachment ---" in result

    def test_kb_attachment_missing_file_graceful(self, tmp_path: Path) -> None:
        """A KB-file attachment with a missing file appends empty content."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        attachments = [PromptAttachment(source_type="kb_file", source="missing.md")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"sku": "A-1"},
            knowledge_base_dir=str(kb_dir),
        )
        assert "knowledge-base file 'missing.md'" in result
        assert "--- Attachment:" in result
        assert "--- End attachment ---" in result

    def test_kb_attachment_no_kb_dir_graceful(self) -> None:
        """A KB-file attachment without KB dir appends empty content without crash."""
        attachments = [PromptAttachment(source_type="kb_file", source="help.md")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"sku": "A-1"},
            knowledge_base_dir=None,
        )
        assert "knowledge-base file 'help.md'" in result

    def test_kb_attachment_escaping_path_graceful(self, tmp_path: Path) -> None:
        """A KB-file attachment with an escaping path appends empty content."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        attachments = [PromptAttachment(source_type="kb_file", source="../outside.md")]
        result = GenerationService.build_effective_prompt(
            rendered_template="Template:",
            attachments=attachments,
            row={"sku": "A-1"},
            knowledge_base_dir=str(kb_dir),
        )
        assert "knowledge-base file '../outside.md'" in result

    def test_multiple_attachments_all_types(self, tmp_path: Path) -> None:
        """Multiple KB and column attachments are all included in order."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "a.md").write_text("AAA", encoding="utf-8")
        (kb_dir / "b.md").write_text("BBB", encoding="utf-8")
        attachments = [
            PromptAttachment(source_type="kb_file", source="a.md"),
            PromptAttachment(source_type="csv_column", source="col1"),
            PromptAttachment(source_type="kb_file", source="b.md"),
            PromptAttachment(source_type="csv_column", source="col2"),
        ]
        result = GenerationService.build_effective_prompt(
            rendered_template="T:",
            attachments=attachments,
            row={"col1": "v1", "col2": "v2", "sku": "A-1"},
            knowledge_base_dir=str(kb_dir),
        )
        # Check ordering
        a_pos = result.index("a.md")
        col1_pos = result.index("column 'col1'")
        b_pos = result.index("b.md")
        col2_pos = result.index("column 'col2'")
        assert a_pos < col1_pos < b_pos < col2_pos
        assert "AAA" in result
        assert "BBB" in result
        assert "v1" in result
        assert "v2" in result


# =========================================================================
# AttachmentManager — cost-warning logic
# =========================================================================


class TestAttachmentManagerCostWarning:
    """Tests for the fine-print cost warning when CSV columns precede KB files."""

    @pytest.fixture
    def dialog(self, qtbot, request):
        """Create an AttachmentManager instance for cost-warning tests."""
        from product_description_tool.dialogs import AttachmentManager

        dm = AttachmentManager(
            prompt_output_field="desc",
            attachments=list(getattr(request, "param", [])),
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dm)
        return dm

    def test_no_warning_when_kb_before_csv(self, qtbot) -> None:
        """No cost warning when all KB files are before all CSV columns."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="kb_file", source="help.md"),
                PromptAttachment(source_type="csv_column", source="sku"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert dialog.cost_warning_label.text() == ""

    def test_no_warning_when_only_columns(self, qtbot) -> None:
        """No cost warning when there are only CSV-column attachments."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        dialog._insert_column_attachments(["sku"])
        dialog._refresh_table()
        assert dialog.cost_warning_label.text() == ""

    def test_no_warning_when_only_kb(self, qtbot) -> None:
        """No cost warning when there are only KB-file attachments."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        dialog._insert_kb_attachments(["help.md"])
        dialog._refresh_table()
        assert dialog.cost_warning_label.text() == ""

    def test_warning_when_csv_before_kb(self, qtbot) -> None:
        """Cost warning shown when a CSV-column attachment precedes a KB-file attachment."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="kb_file", source="help.md"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert "increase prompt cost" in dialog.cost_warning_label.text().lower()

    def test_warning_clears_when_reordered_to_fix(self, qtbot) -> None:
        """After moving KB file before CSV column, the warning disappears."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="kb_file", source="help.md"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert "increase prompt cost" in dialog.cost_warning_label.text().lower()

        # Simulate reorder: move KB before CSV
        dialog._attachments[0], dialog._attachments[1] = (
            dialog._attachments[1], dialog._attachments[0],
        )
        dialog._refresh_table()
        assert dialog.cost_warning_label.text() == ""

    def test_warning_with_multiple_csv_before_kb(self, qtbot) -> None:
        """Warning shown when multiple CSV columns appear before any KB file."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="csv_column", source="name"),
                PromptAttachment(source_type="kb_file", source="help.md"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)
        assert "increase prompt cost" in dialog.cost_warning_label.text().lower()

    def test_warning_not_shown_for_kb_before_csv_mixed(self, qtbot) -> None:
        """No warning when the first attachment is KB even if CSV appears later."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="kb_file", source="help.md"),
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="csv_column", source="name"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["help.md"],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)
        assert dialog.cost_warning_label.text() == ""


# =========================================================================
# AttachmentManager — insertion ordering (KB-first default)
# =========================================================================


class TestAttachmentManagerInsertion:
    """Tests for AttachmentManager insertion ordering rules.

    Spec: KB-file attachments are inserted before the first CSV column (or at
    end if no CSV columns exist). CSV-column attachments are appended after all
    existing attachments.
    """

    def test_insert_kb_before_existing_column(self, qtbot) -> None:
        """New KB-file attachments are inserted before the first existing CSV column."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="name"),
            ],
            csv_columns=["name", "sku"],
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["help.md", "guide.md"])

        atts = dialog._attachments
        assert len(atts) == 3
        assert atts[0].source_type == "kb_file"
        assert atts[0].source == "help.md"
        assert atts[1].source_type == "kb_file"
        assert atts[1].source == "guide.md"
        assert atts[2].source_type == "csv_column"
        assert atts[2].source == "name"

    def test_insert_kb_when_no_columns(self, qtbot) -> None:
        """When no CSV-column attachments exist, KB files are appended at end."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["help.md"])

        assert len(dialog._attachments) == 1
        assert dialog._attachments[0].source_type == "kb_file"
        assert dialog._attachments[0].source == "help.md"

    def test_insert_kb_with_existing_kb_keeps_kb_grouped(self, qtbot) -> None:
        """New KB files are inserted after existing KB files but before CSV columns."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="kb_file", source="existing.md"),
                PromptAttachment(source_type="csv_column", source="name"),
            ],
            csv_columns=["name", "sku"],
            kb_files=["help.md", "existing.md"],
            knowledge_base_dir="/some/dir",
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["help.md"])

        assert len(dialog._attachments) == 3
        assert dialog._attachments[0].source == "existing.md"
        assert dialog._attachments[1].source == "help.md"
        assert dialog._attachments[2].source == "name"

    def test_insert_column_appends_at_end(self, qtbot) -> None:
        """New CSV-column attachments are appended after all existing attachments."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="kb_file", source="guide.md"),
            ],
            csv_columns=["name", "sku"],
            kb_files=["guide.md"],
            knowledge_base_dir="/some/dir",
        )
        qtbot.addWidget(dialog)

        dialog._insert_column_attachments(["name", "sku"])

        assert len(dialog._attachments) == 3
        assert dialog._attachments[0].source_type == "kb_file"
        assert dialog._attachments[1].source_type == "csv_column"
        assert dialog._attachments[1].source == "name"
        assert dialog._attachments[2].source_type == "csv_column"
        assert dialog._attachments[2].source == "sku"

    def test_insert_column_into_empty_list(self, qtbot) -> None:
        """When no attachments exist, CSV columns are still appended."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)

        dialog._insert_column_attachments(["sku"])

        assert len(dialog._attachments) == 1
        assert dialog._attachments[0].source == "sku"

    def test_insert_multiple_kb_then_multiple_columns(self, qtbot) -> None:
        """Adding KB files then CSV columns produces KB-group then CSV-group order."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["col1", "col2"],
            kb_files=["k1.md", "k2.md"],
            knowledge_base_dir="/some/dir",
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["k1.md", "k2.md"])
        dialog._insert_column_attachments(["col1", "col2"])

        atts = dialog._attachments
        assert len(atts) == 4
        assert [a.source_type for a in atts] == [
            "kb_file", "kb_file", "csv_column", "csv_column",
        ]

    def test_insert_kb_after_column_preserves_column_positions(self, qtbot) -> None:
        """Inserting KB files when CSV columns already exist places KB before first CSV."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="col1"),
                PromptAttachment(source_type="csv_column", source="col2"),
            ],
            csv_columns=["col1", "col2", "col3"],
            kb_files=["k1.md", "k2.md"],
            knowledge_base_dir="/some/dir",
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["k1.md", "k2.md"])

        atts = dialog._attachments
        assert len(atts) == 4
        assert atts[0].source_type == "kb_file"
        assert atts[1].source_type == "kb_file"
        assert atts[2].source == "col1"
        assert atts[3].source == "col2"


# =========================================================================
# AttachmentManager — status resolution
# =========================================================================


class TestAttachmentManagerStatus:
    """Tests for AttachmentManager status resolution helpers."""

    def test_kb_status_available(self, tmp_path: Path, qtbot) -> None:
        """A KB file that exists under the KB directory shows 'Available'."""
        from product_description_tool.dialogs import AttachmentManager

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "help.md").write_text("help", encoding="utf-8")

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=str(kb_dir),
            kb_files=["help.md"],
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert dialog._resolve_kb_file_status("help.md") == "Available"

    def test_kb_status_missing_root(self, qtbot) -> None:
        """Without a configured KB directory, status reports 'Missing KB root'."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=None,
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert "Missing KB root" in dialog._resolve_kb_file_status("help.md")

    def test_kb_status_escapes(self, tmp_path: Path, qtbot) -> None:
        """A path that escapes the KB directory reports 'Path escapes'."""
        from product_description_tool.dialogs import AttachmentManager

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=str(kb_dir),
            kb_files=[],
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert "Path escapes" in dialog._resolve_kb_file_status("../secret.md")

    def test_kb_status_not_found(self, tmp_path: Path, qtbot) -> None:
        """A non-existent file reports 'File not found'."""
        from product_description_tool.dialogs import AttachmentManager

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=str(kb_dir),
            kb_files=[],
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert "File not found" in dialog._resolve_kb_file_status("missing.md")

    def test_kb_status_unsupported_type(self, tmp_path: Path, qtbot) -> None:
        """An unsupported file type reports 'Unsupported type'."""
        from product_description_tool.dialogs import AttachmentManager

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "data.txt").write_text("data", encoding="utf-8")
        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=str(kb_dir),
            kb_files=[],
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert "Unsupported type" in dialog._resolve_kb_file_status("data.txt")

    def test_column_status_available(self, qtbot) -> None:
        """An existing column reports 'Available'."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)
        assert dialog._resolve_column_status("sku") == "Available"

    def test_column_status_not_found(self, qtbot) -> None:
        """A non-existent column reports 'Column not found'."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert "Column not found" in dialog._resolve_column_status("nonexistent")


# =========================================================================
# AttachmentManager — dialog integration (sub-dialogs stubbed via insert
# methods)
# =========================================================================


class TestAttachmentManagerDialogIntegration:
    """Integration tests for AttachmentManager with sub-dialogs stubbed."""

    def test_add_kb_and_get_attachments(self, qtbot) -> None:
        """Adding KB files through the insert method updates get_attachments()."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir="/some/dir",
            kb_files=["guide.md", "help.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)

        dialog._insert_kb_attachments(["guide.md", "help.md"])
        dialog._refresh_table()
        result = dialog.get_attachments()

        assert len(result) == 2
        assert result[0].source == "guide.md"
        assert result[1].source == "help.md"

    def test_add_column_and_get_attachments(self, qtbot) -> None:
        """Adding CSV columns through the insert method updates get_attachments()."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)

        dialog._insert_column_attachments(["sku", "name"])
        dialog._refresh_table()
        result = dialog.get_attachments()

        assert len(result) == 2
        assert result[0].source == "sku"
        assert result[1].source == "name"

    def test_remove_attachment(self, qtbot) -> None:
        """Removing an attachment updates get_attachments()."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="csv_column", source="name"),
            ],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)

        # Remove second attachment (index 1)
        dialog.table.selectRow(1)
        dialog._on_remove()

        result = dialog.get_attachments()
        assert len(result) == 1
        assert result[0].source == "sku"

    def test_move_up(self, qtbot) -> None:
        """Moving an attachment up changes the order."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="name"),
                PromptAttachment(source_type="csv_column", source="sku"),
            ],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)

        dialog.table.selectRow(1)
        dialog._on_move_up()

        result = dialog.get_attachments()
        assert result[0].source == "sku"
        assert result[1].source == "name"

    def test_move_down(self, qtbot) -> None:
        """Moving an attachment down changes the order."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
                PromptAttachment(source_type="csv_column", source="name"),
            ],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)

        dialog.table.selectRow(0)
        dialog._on_move_down()

        result = dialog.get_attachments()
        assert result[0].source == "name"
        assert result[1].source == "sku"

    def test_remove_button_disabled_when_no_selection(self, qtbot) -> None:
        """The Remove button is disabled when no row is selected."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="csv_column", source="sku"),
            ],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert not dialog.remove_button.isEnabled()

    def test_table_reflects_attachment_data(self, qtbot) -> None:
        """The table shows correct type and source for each attachment."""
        from product_description_tool.dialogs import AttachmentManager
        from product_description_tool.project import PromptAttachment

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[
                PromptAttachment(source_type="kb_file", source="guide.md"),
                PromptAttachment(source_type="csv_column", source="sku"),
            ],
            knowledge_base_dir="/some/dir",
            kb_files=["guide.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)

        assert dialog.table.rowCount() == 2
        assert dialog.table.item(0, 1).text() == "KB file"
        assert dialog.table.item(0, 2).text() == "guide.md"
        assert dialog.table.item(1, 1).text() == "CSV column"
        assert dialog.table.item(1, 2).text() == "sku"

    def test_add_kb_button_enabled_with_kb_dir_and_files(self, qtbot) -> None:
        """Add KB Files button is enabled when a KB dir and files are available."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir="/some/dir",
            kb_files=["guide.md"],
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert dialog.add_kb_button.isEnabled()

    def test_add_kb_button_disabled_without_kb_dir(self, qtbot) -> None:
        """Add KB Files button is disabled without a configured KB directory."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            knowledge_base_dir=None,
            csv_columns=["sku"],
        )
        qtbot.addWidget(dialog)
        assert not dialog.add_kb_button.isEnabled()

    def test_add_column_button_enabled_with_columns(self, qtbot) -> None:
        """Add Columns button is enabled when CSV columns are available."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=["sku", "name"],
        )
        qtbot.addWidget(dialog)
        assert dialog.add_column_button.isEnabled()

    def test_add_column_button_disabled_without_columns(self, qtbot) -> None:
        """Add Columns button is disabled when no CSV columns are available."""
        from product_description_tool.dialogs import AttachmentManager

        dialog = AttachmentManager(
            prompt_output_field="desc",
            attachments=[],
            csv_columns=[],
        )
        qtbot.addWidget(dialog)
        assert not dialog.add_column_button.isEnabled()


# =========================================================================
# Attachment metadata persistence (PromptAttachment + ProjectPrompt)
# =========================================================================


class TestPromptAttachmentSerialization:
    """Tests for PromptAttachment and ProjectPrompt serialization."""

    def test_to_dict_from_dict_round_trip(self) -> None:
        """PromptAttachment survives to_dict/from_dict."""
        att = PromptAttachment(source_type="kb_file", source="help.md")
        data = att.to_dict()
        restored = PromptAttachment.from_dict(data)
        assert restored.source_type == "kb_file"
        assert restored.source == "help.md"

    def test_to_dict_from_dict_csv_column(self) -> None:
        """CSV column attachment round-trips correctly."""
        att = PromptAttachment(source_type="csv_column", source="sku")
        data = att.to_dict()
        restored = PromptAttachment.from_dict(data)
        assert restored.source_type == "csv_column"
        assert restored.source == "sku"

    def test_project_prompt_attachments_in_to_dict(self) -> None:
        """ProjectPrompt serialization includes attachments."""
        prompt = ProjectPrompt(
            output_field="desc",
            prompt="Write",
            attachments=[
                PromptAttachment(source_type="kb_file", source="guide.md"),
                PromptAttachment(source_type="csv_column", source="sku"),
            ],
        )
        data = prompt.to_dict()
        assert "attachments" in data
        assert len(data["attachments"]) == 2
        assert data["attachments"][0]["source-type"] == "kb_file"
        assert data["attachments"][0]["source"] == "guide.md"

    def test_project_prompt_from_dict_restores_attachments(self) -> None:
        """ProjectPrompt deserialization restores attachments."""
        data = {
            "output-field": "desc",
            "prompt": "Write",
            "attachments": [
                {"source-type": "kb_file", "source": "guide.md"},
                {"source-type": "csv_column", "source": "sku"},
            ],
        }
        prompt = ProjectPrompt.from_dict(data)
        assert len(prompt.attachments) == 2
        assert prompt.attachments[0].source == "guide.md"
        assert prompt.attachments[1].source == "sku"

    def test_project_prompt_no_attachments_key_absent(self) -> None:
        """When no attachments exist, the key may be absent."""
        prompt = ProjectPrompt(output_field="desc", prompt="Write")
        data = prompt.to_dict()
        assert "attachments" not in data

    def test_project_prompt_empty_attachments_not_serialized(self) -> None:
        """An empty attachments list is not serialized to keep JSON clean."""
        prompt = ProjectPrompt(
            output_field="desc", prompt="Write", attachments=[],
        )
        data = prompt.to_dict()
        assert "attachments" not in data

    def test_from_dict_missing_attachments_key(self) -> None:
        """Legacy data without attachments loads with an empty list."""
        data = {"output-field": "desc", "prompt": "Write"}
        prompt = ProjectPrompt.from_dict(data)
        assert prompt.attachments == []

    def test_from_dict_non_list_attachments_ignored(self) -> None:
        """If attachments is not a list (corrupt data), it loads as empty list."""
        data = {"output-field": "desc", "prompt": "Write", "attachments": "corrupt"}
        prompt = ProjectPrompt.from_dict(data)
        assert prompt.attachments == []


class TestProjectAttachmentPersistence:
    """Full save/load cycle tests for attachment metadata."""

    def test_repository_round_trips_single_attachment(self, tmp_path: Path) -> None:
        """Full save/load cycle preserves a single CSV-column attachment."""
        repo = ProjectRepository()
        project = Project(
            prompts=[
                ProjectPrompt(
                    output_field="desc",
                    prompt="Write {{sku}}",
                    attachments=[
                        PromptAttachment(source_type="csv_column", source="sku"),
                    ],
                ),
            ],
        )
        saved_path = repo.save(tmp_path / "test.project.json", project)
        loaded = repo.load(saved_path)

        assert len(loaded.prompts[0].attachments) == 1
        assert loaded.prompts[0].attachments[0].source_type == "csv_column"
        assert loaded.prompts[0].attachments[0].source == "sku"

    def test_repository_round_trips_multiple_attachments(self, tmp_path: Path) -> None:
        """Full save/load preserves multiple mixed attachments in order."""
        repo = ProjectRepository()
        project = Project(
            prompts=[
                ProjectPrompt(
                    output_field="desc",
                    prompt="Write {{sku}}",
                    attachments=[
                        PromptAttachment(source_type="kb_file", source="guide.md"),
                        PromptAttachment(source_type="csv_column", source="sku"),
                        PromptAttachment(source_type="csv_column", source="name"),
                    ],
                ),
            ],
        )
        saved_path = repo.save(tmp_path / "test.project.json", project)
        loaded = repo.load(saved_path)

        atts = loaded.prompts[0].attachments
        assert len(atts) == 3
        assert atts[0].source == "guide.md"
        assert atts[1].source == "sku"
        assert atts[2].source == "name"

    def test_attachments_in_json_manifest(self, tmp_path: Path) -> None:
        """Attachment metadata appears in the JSON manifest on save."""
        repo = ProjectRepository()
        project = Project(
            prompts=[
                ProjectPrompt(
                    output_field="desc",
                    prompt="Write {{sku}}",
                    attachments=[
                        PromptAttachment(source_type="kb_file", source="guide.md"),
                        PromptAttachment(source_type="csv_column", source="sku"),
                    ],
                ),
            ],
        )
        repo.save(tmp_path / "test.project.json", project)
        data = json.loads(
            (tmp_path / "test.project.json").read_text(encoding="utf-8"),
        )
        atts = data["prompts"][0].get("attachments", [])
        assert len(atts) == 2
        assert atts[0]["source-type"] == "kb_file"
        assert atts[0]["source"] == "guide.md"
        assert atts[1]["source-type"] == "csv_column"
        assert atts[1]["source"] == "sku"

    def test_legacy_project_without_attachments(self, tmp_path: Path) -> None:
        """A project file without any attachment metadata loads with empty attachments."""
        repo = ProjectRepository()
        manifest = {
            "prompts": [
                {"output-field": "desc", "prompt": "Write {{sku}}"},
            ],
            "csv": {"delimiter": ";"},
        }
        project_file = tmp_path / "legacy.project.json"
        project_file.write_text(json.dumps(manifest), encoding="utf-8")
        loaded = repo.load(project_file)
        assert loaded.prompts[0].attachments == []

    def test_empty_attachments_list_in_manifest(self, tmp_path: Path) -> None:
        """An empty attachments list in the manifest loads as an empty list."""
        repo = ProjectRepository()
        manifest = {
            "prompts": [
                {
                    "output-field": "desc",
                    "prompt": "Write",
                    "attachments": [],
                },
            ],
            "csv": {"delimiter": ";"},
        }
        project_file = tmp_path / "empty_atts.project.json"
        project_file.write_text(json.dumps(manifest), encoding="utf-8")
        loaded = repo.load(project_file)
        assert loaded.prompts[0].attachments == []

    def test_attachments_survive_knowledge_base_dir_round_trip(
        self, tmp_path: Path,
    ) -> None:
        """Attachments plus KB directory round-trip together."""
        repo = ProjectRepository()
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        project = Project(
            prompts=[
                ProjectPrompt(
                    output_field="desc",
                    prompt="Write {{sku}}",
                    attachments=[
                        PromptAttachment(source_type="kb_file", source="guide.md"),
                        PromptAttachment(source_type="csv_column", source="sku"),
                    ],
                ),
            ],
            knowledge_base_dir=str(kb_dir),
        )
        saved_path = repo.save(tmp_path / "test.project.json", project)
        loaded = repo.load(saved_path)

        assert loaded.knowledge_base_dir is not None
        assert Path(loaded.knowledge_base_dir) == kb_dir.resolve()
        assert len(loaded.prompts[0].attachments) == 2

    def test_prompt_text_sidecar_unaffected_by_attachments(
        self, tmp_path: Path,
    ) -> None:
        """Attachment metadata does not leak into the prompt sidecar file."""
        repo = ProjectRepository()
        project = Project(
            prompts=[
                ProjectPrompt(
                    output_field="desc",
                    prompt="Write {{sku}}",
                    attachments=[
                        PromptAttachment(source_type="csv_column", source="sku"),
                    ],
                ),
            ],
        )
        saved_path = repo.save(tmp_path / "test.project.json", project)

        sidecar = saved_path.parent / "desc.prompt.txt"
        content = sidecar.read_text(encoding="utf-8")
        assert content == "Write {{sku}}"
        assert "attachment" not in content.lower()
