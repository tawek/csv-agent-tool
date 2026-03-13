import pytest

from product_description_tool.prompt_renderer import PromptRenderer, PromptTemplateError


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
