import pytest
from pathlib import Path

from product_description_tool.prompt_renderer import (
    CycleError,
    KnowledgeBaseRefError,
    PromptRenderer,
    PromptTemplateError,
    SUPPORTED_KB_EXTENSIONS,
)
from product_description_tool.project import ProjectPrompt


def test_extracts_unique_placeholders() -> None:
    renderer = PromptRenderer()

    placeholders = renderer.extract_placeholders(
        "Rewrite {{product name}} with {{sku-code}} and {{product name}} again."
    )

    assert placeholders == ["product name", "sku-code"]


def test_renders_placeholder_values_for_headers_with_spaces() -> None:
    renderer = PromptRenderer()

    output = renderer.render(
        "Title: {{product name}} / SKU: {{sku-code}}",
        {"product name": "Lamp", "sku-code": "A-123"},
    )

    assert output == "Title: Lamp / SKU: A-123"


def test_raises_for_unknown_placeholders() -> None:
    renderer = PromptRenderer()

    with pytest.raises(PromptTemplateError) as exc_info:
        renderer.validate("{{missing}}", ["name"])

    assert exc_info.value.missing_fields == ["missing"]


class TestComputePromptOrder:
    def test_single_prompt_with_no_dependencies(self) -> None:
        prompts = [ProjectPrompt(output_field="summary", prompt="Rewrite {{title}}")]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered == prompts

    def test_two_prompts_with_one_dependency(self) -> None:
        prompts = [
            ProjectPrompt(output_field="summary", prompt="Rewrite {{title}}"),
            ProjectPrompt(output_field="seo", prompt="Write {{summary}} and optimize for {{title}}"),
        ]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered[0].output_field == "summary"
        assert ordered[1].output_field == "seo"

    def test_chained_dependencies(self) -> None:
        prompts = [
            ProjectPrompt(output_field="title", prompt="Summarize {{sku}}"),
            ProjectPrompt(output_field="summary", prompt="Write {{title}}"),
            ProjectPrompt(output_field="seo", prompt="Write {{summary}} and {{title}}"),
        ]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered[0].output_field == "title"
        assert ordered[1].output_field == "summary"
        assert ordered[2].output_field == "seo"

    def test_no_dependencies_preserves_input_order(self) -> None:
        prompts = [
            ProjectPrompt(output_field="a", prompt="Process {{sku}}"),
            ProjectPrompt(output_field="b", prompt="Process {{sku}}"),
            ProjectPrompt(output_field="c", prompt="Process {{sku}}"),
        ]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered == prompts

    def test_cycle_detected(self) -> None:
        prompts = [
            ProjectPrompt(output_field="a", prompt="Use {{b}}"),
            ProjectPrompt(output_field="b", prompt="Use {{a}}"),
        ]
        with pytest.raises(CycleError) as exc_info:
            PromptRenderer.compute_prompt_order(prompts)
        assert set(exc_info.value.cycle_prompts) == {"a", "b"}
        assert len(exc_info.value.cycle_edges) == 2

    def test_cycle_among_subset(self) -> None:
        prompts = [
            ProjectPrompt(output_field="root", prompt="Process {{sku}}"),
            ProjectPrompt(output_field="a", prompt="Use {{b}}"),
            ProjectPrompt(output_field="b", prompt="Use {{a}}"),
        ]
        with pytest.raises(CycleError) as exc_info:
            PromptRenderer.compute_prompt_order(prompts)
        assert "root" not in exc_info.value.cycle_prompts
        assert set(exc_info.value.cycle_prompts) == {"a", "b"}

    def test_self_reference_ignored(self) -> None:
        prompts = [
            ProjectPrompt(output_field="summary", prompt="Rewrite {{summary}} and {{title}}"),
            ProjectPrompt(output_field="title", prompt="Process {{sku}}"),
        ]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered[0].output_field == "title"
        assert ordered[1].output_field == "summary"

    def test_cycle_error_message(self) -> None:
        prompts = [
            ProjectPrompt(output_field="x", prompt="Use {{y}}"),
            ProjectPrompt(output_field="y", prompt="Use {{z}}"),
            ProjectPrompt(output_field="z", prompt="Use {{x}}"),
        ]
        with pytest.raises(CycleError) as exc_info:
            PromptRenderer.compute_prompt_order(prompts)
        assert "x" in exc_info.value.cycle_prompts
        assert "y" in exc_info.value.cycle_prompts
        assert "z" in exc_info.value.cycle_prompts
        msg = str(exc_info.value)
        assert "Cyclic dependency detected" in msg

    def test_kb_refs_ignored_in_dependency_graph(self) -> None:
        """KB refs ({{@...}}) must not create prompt dependencies."""
        prompts = [
            ProjectPrompt(output_field="a", prompt="Use {{b}} and {{@kb/doc.md}}"),
            ProjectPrompt(output_field="b", prompt="Plain {{sku}}"),
        ]
        ordered = PromptRenderer.compute_prompt_order(prompts)
        assert ordered[0].output_field == "b"
        assert ordered[1].output_field == "a"


class TestKnowledgeBaseRefs:
    def test_is_kb_placeholder(self) -> None:
        assert PromptRenderer.is_kb_placeholder("@docs/help.md") is True
        assert PromptRenderer.is_kb_placeholder("column_name") is False

    def test_extract_kb_placeholders(self) -> None:
        result = PromptRenderer.extract_kb_placeholders(
            "Use {{@doc.md}} and {{@sub/other.csv}} with {{title}}"
        )
        assert result == ["@doc.md", "@sub/other.csv"]

    def test_extract_kb_references(self) -> None:
        """extract_kb_references returns paths without the @ prefix."""
        result = PromptRenderer.extract_kb_references(
            "Use {{@doc.md}} and {{@sub/other.csv}} with {{title}}"
        )
        assert result == ["doc.md", "sub/other.csv"]

    def test_extract_field_placeholders(self) -> None:
        result = PromptRenderer.extract_field_placeholders(
            "Use {{@doc.md}} and {{@sub/other.csv}} with {{title}}"
        )
        assert result == ["title"]

    def test_validate_with_kb_refs_succeeds(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "help.md").write_text("# Help", encoding="utf-8")
        (kb_dir / "data.csv").write_text("a,b\n1,2", encoding="utf-8")

        renderer = PromptRenderer()
        # Should not raise
        renderer.validate(
            "Use {{@help.md}} and {{@data.csv}} with {{title}}",
            ["title"],
            knowledge_base_dir=str(kb_dir),
        )

    def test_validate_raises_when_kb_dir_missing(self) -> None:
        renderer = PromptRenderer()
        with pytest.raises(KnowledgeBaseRefError) as exc_info:
            renderer.validate("Use {{@doc.md}}", ["title"])
        errors = exc_info.value.errors
        assert any("No knowledge-base directory configured" in e for e in errors)

    def test_validate_raises_for_file_not_found(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        renderer = PromptRenderer()
        with pytest.raises(KnowledgeBaseRefError) as exc_info:
            renderer.validate(
                "Use {{@missing.md}}",
                ["title"],
                knowledge_base_dir=str(kb_dir),
            )
        errors = exc_info.value.errors
        assert any("file not found" in e for e in errors)

    def test_validate_raises_for_unsupported_extension(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "notes.txt").write_text("hello", encoding="utf-8")

        renderer = PromptRenderer()
        with pytest.raises(KnowledgeBaseRefError) as exc_info:
            renderer.validate(
                "Use {{@notes.txt}}",
                ["title"],
                knowledge_base_dir=str(kb_dir),
            )
        errors = exc_info.value.errors
        assert any("unsupported" in e.lower() for e in errors)

    def test_validate_raises_for_path_escaping_kb_dir(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        # Create a file outside the KB dir
        outside = tmp_path / "secret.md"
        outside.write_text("secret", encoding="utf-8")

        renderer = PromptRenderer()
        with pytest.raises(KnowledgeBaseRefError) as exc_info:
            renderer.validate(
                "Use {{@../secret.md}}",
                ["title"],
                knowledge_base_dir=str(kb_dir),
            )
        errors = exc_info.value.errors
        assert any("escapes" in e.lower() for e in errors)

    def test_validate_mixed_field_and_kb_refs(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "style.md").write_text("CSS", encoding="utf-8")

        renderer = PromptRenderer()
        # Should raise for unknown field placeholder, not KB ref
        with pytest.raises(PromptTemplateError) as exc_info:
            renderer.validate(
                "{{@style.md}} and {{missing}}",
                ["title"],
                knowledge_base_dir=str(kb_dir),
            )
        assert exc_info.value.missing_fields == ["missing"]

    def test_render_substitutes_kb_refs(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "style.md").write_text("Bold text", encoding="utf-8")

        renderer = PromptRenderer()
        result = renderer.render(
            "Style: {{@style.md}} and title: {{title}}",
            {"title": "Product"},
            knowledge_base_dir=str(kb_dir),
        )
        assert "Bold text" in result
        assert "Product" in result

    def test_render_multiple_kb_refs(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "a.md").write_text("Alpha", encoding="utf-8")
        (kb_dir / "sub").mkdir()
        (kb_dir / "sub" / "b.csv").write_text("Beta", encoding="utf-8")

        renderer = PromptRenderer()
        result = renderer.render(
            "{{@a.md}} and {{@sub/b.csv}}",
            {},
            knowledge_base_dir=str(kb_dir),
        )
        assert "Alpha" in result
        assert "Beta" in result

    def test_render_preserves_field_placeholders_without_kb(self) -> None:
        """When no KB dir is given, field placeholders still work."""
        renderer = PromptRenderer()
        result = renderer.render("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"
