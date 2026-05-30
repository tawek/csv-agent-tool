from pathlib import Path

from product_description_tool.config import CsvConfig, FieldConfig
from product_description_tool.csv_repository import CsvDocument, CsvDialectSettings, CsvRepository


def test_loads_and_preserves_headers(tmp_path: Path) -> None:
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("sku,description\nA-1,<p>Alpha</p>\n", encoding="utf-8")

    repository = CsvRepository()
    document = repository.load(csv_path, CsvConfig(encoding="utf-8", delimiter=","))

    assert document.headers == ["sku", "description"]
    assert document.rows == [{"sku": "A-1", "description": "<p>Alpha</p>"}]
    assert document.dialect.delimiter == ","
    assert document.dialect.quotechar == '"'


def test_save_preserves_existing_headers_and_honors_delimiter(tmp_path: Path) -> None:
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated"],
        rows=[{"sku": "A-1", "description": "<p>Alpha</p>", "generated": "<p>Beta</p>"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(
        delimiter=";",
        encoding="utf-8",
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    assert output_path.read_text(encoding="utf-8") == (
        'sku;description;generated\nA-1;<p>Alpha</p>;<p>Beta</p>\n'
    )


def test_ensure_column_creates_empty_cells() -> None:
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku"],
        rows=[{"sku": "A-1"}, {"sku": "A-2"}],
    )

    repository.ensure_column(document, "generated")

    assert document.headers == ["sku", "generated"]
    assert document.rows == [
        {"sku": "A-1", "generated": ""},
        {"sku": "A-2", "generated": ""},
    ]


def test_load_uses_configured_delimiter_instead_of_sniffing(tmp_path: Path) -> None:
    csv_path = tmp_path / "products.csv"
    csv_path.write_text('sku_description,"long_value"\nA-1,"<p>Alpha</p>"\n', encoding="utf-8")

    repository = CsvRepository()
    document = repository.load(csv_path, CsvConfig(encoding="utf-8", delimiter=","))

    assert document.headers == ["sku_description", "long_value"]
    assert document.rows == [{"sku_description": "A-1", "long_value": "<p>Alpha</p>"}]


def test_save_strips_whitespace_when_field_configured(tmp_path: Path) -> None:
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated"],
        rows=[
            {"sku": "A-1", "description": "<p>Alpha\n\nBeta</p>", "generated": "<p>  Gamma  "},
            {"sku": "A-2", "description": "<p>Delta\n\n\nEpsilon</p>", "generated": "Zeta"},
        ],
    )
    config = CsvConfig(
        delimiter=";",
        encoding="utf-8",
        fields={
            "description": FieldConfig(label="Product Description", show=True, strip_html_whitespace=True),
            "generated": FieldConfig(label="Generated", show=True, strip_html_whitespace=True),
            "sku": FieldConfig(label="SKU", show=True, strip_html_whitespace=False),
        },
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    lines = output_path.read_text(encoding="utf-8").strip().split("\n")
    assert lines[0] == "sku;description;generated"
    assert lines[1] == "A-1;<p>Alpha Beta</p>;<p> Gamma"
    assert lines[2] == "A-2;<p>Delta Epsilon</p>;Zeta"


def test_save_preserves_whitespace_when_not_configured(tmp_path: Path) -> None:
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description"],
        rows=[{"sku": "A-1", "description": "<p>Alpha\n\nBeta</p>"}],
    )
    config = CsvConfig(
        delimiter=";",
        encoding="utf-8",
        fields={
            "description": FieldConfig(label="Product Description", show=True, strip_html_whitespace=False),
            "sku": FieldConfig(label="SKU", show=True, strip_html_whitespace=False),
        },
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    content = output_path.read_text(encoding="utf-8")
    assert "Alpha" in content
    assert "Beta" in content
    assert "\n" in content or "\r" in content

