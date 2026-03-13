from pathlib import Path

from product_description_tool.config import CsvConfig
from product_description_tool.csv_repository import CsvDocument, CsvDialectSettings, CsvRepository


def test_loads_and_preserves_headers(tmp_path: Path) -> None:
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("sku,description\nA-1,<p>Alpha</p>\n", encoding="utf-8")

    repository = CsvRepository()
    document = repository.load(csv_path, CsvConfig(encoding="utf-8"))

    assert document.headers == ["sku", "description"]
    assert document.rows == [{"sku": "A-1", "description": "<p>Alpha</p>"}]


def test_save_adds_missing_result_column_and_honors_delimiter(tmp_path: Path) -> None:
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description"],
        rows=[{"sku": "A-1", "description": "<p>Alpha</p>", "generated": "<p>Beta</p>"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(
        original_description="description",
        result_description="generated",
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
