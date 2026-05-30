import pytest

from product_description_tool.prompt_renderer import CycleError, PromptRenderer, PromptTemplateError
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
