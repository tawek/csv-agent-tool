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


def test_save_uses_export_order_when_configured(tmp_path: Path) -> None:
    """CsvConfig.export_order determines the column order in the output CSV."""
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated"],
        rows=[{"sku": "A-1", "description": "<p>Alpha</p>", "generated": "<p>Beta</p>"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(
        delimiter=",",
        encoding="utf-8",
        export_order=["generated", "sku", "description"],
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    content = output_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert lines[0] == "generated,sku,description"
    assert lines[1] == "<p>Beta</p>,A-1,<p>Alpha</p>"


def test_save_export_order_appends_headers_not_in_order(tmp_path: Path) -> None:
    """Columns missing from export_order are appended in document header order."""
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated", "tags"],
        rows=[{"sku": "A-1", "description": "d", "generated": "g", "tags": "t"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(
        delimiter=",",
        encoding="utf-8",
        export_order=["generated", "sku"],
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    content = output_path.read_text(encoding="utf-8")
    header_line = content.strip().split("\n")[0]
    assert header_line == "generated,sku,description,tags"


def test_save_empty_export_order_falls_back_to_document_headers(tmp_path: Path) -> None:
    """Empty export_order writes columns in document header order."""
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated"],
        rows=[{"sku": "A-1", "description": "<p>Alpha</p>", "generated": "<p>Beta</p>"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(delimiter=",", encoding="utf-8")

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    content = output_path.read_text(encoding="utf-8")
    header_line = content.strip().split("\n")[0]
    assert header_line == "sku,description,generated"


def test_save_export_order_includes_each_column_exactly_once(tmp_path: Path) -> None:
    """Every document column appears exactly once, even with a partial export_order."""
    repository = CsvRepository()
    document = CsvDocument(
        headers=["a", "b", "c", "d", "e"],
        rows=[{"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvConfig(
        delimiter=",",
        encoding="utf-8",
        export_order=["e", "a", "c"],
    )

    output_path = tmp_path / "out.csv"
    repository.save(output_path, document, config)

    content = output_path.read_text(encoding="utf-8")
    headers_out = content.strip().split("\n")[0].split(",")
    assert headers_out == ["e", "a", "c", "b", "d"]
    assert len(headers_out) == 5
    assert set(headers_out) == {"a", "b", "c", "d", "e"}


def test_csv_config_export_order_round_trip() -> None:
    """CsvConfig serializes and deserializes export_order correctly."""
    original = CsvConfig(
        export_order=["generated", "sku", "description"],
    )
    serialized = original.to_dict()
    restored = CsvConfig.from_dict(serialized)
    assert restored.export_order == ["generated", "sku", "description"]


def test_csv_config_export_order_defaults_to_empty() -> None:
    """CsvConfig export_order defaults to empty list."""
    config = CsvConfig()
    assert config.export_order == []
    serialized = config.to_dict()
    assert serialized["export-order"] == []
    restored = CsvConfig.from_dict(serialized)
    assert restored.export_order == []


# ---------------------------------------------------------------------------
# Regression tests for export-order normalization
# (_normalize_export_order + save integration)
# ---------------------------------------------------------------------------


class TestNormalizeExportOrder:
    """Direct unit tests for CsvRepository._normalize_export_order."""

    def test_duplicate_configured_keeps_first_only(self) -> None:
        """Duplicate names in configured order keep the first occurrence."""
        result = CsvRepository._normalize_export_order(
            configured=["sku", "sku", "description", "sku"],
            current_headers=["sku", "description", "generated"],
        )
        assert result == ["sku", "description", "generated"]

    def test_stale_configured_ignored(self) -> None:
        """Names not in current_headers are silently dropped."""
        result = CsvRepository._normalize_export_order(
            configured=["sku", "nonexistent", "description"],
            current_headers=["sku", "description", "generated"],
        )
        assert result == ["sku", "description", "generated"]

    def test_duplicates_and_stale_combined(self) -> None:
        """Duplicate + stale names are both handled correctly."""
        result = CsvRepository._normalize_export_order(
            configured=["stale1", "sku", "sku", "stale2", "description", "sku"],
            current_headers=["sku", "description", "generated"],
        )
        assert result == ["sku", "description", "generated"]

    def test_all_stale_falls_back_to_current_order(self) -> None:
        """When every configured name is stale, current header order is used."""
        result = CsvRepository._normalize_export_order(
            configured=["old", "gone", "missing"],
            current_headers=["a", "b", "c"],
        )
        assert result == ["a", "b", "c"]

    def test_empty_configured_returns_current_order(self) -> None:
        result = CsvRepository._normalize_export_order(
            configured=[], current_headers=["a", "b"]
        )
        assert result == ["a", "b"]

    def test_empty_both_returns_empty(self) -> None:
        result = CsvRepository._normalize_export_order(
            configured=[], current_headers=[]
        )
        assert result == []

    def test_each_current_header_appears_exactly_once(self) -> None:
        """After normalization every current header appears exactly once."""
        result = CsvRepository._normalize_export_order(
            configured=["x", "y", "x", "z"],
            current_headers=["a", "b", "c", "x", "y", "z", "d"],
        )
        assert result == ["x", "y", "z", "a", "b", "c", "d"]
        assert len(result) == 7
        assert set(result) == {"a", "b", "c", "x", "y", "z", "d"}


class TestSaveExportNormalization:
    """Integration tests — save() with duplicate/stale export_order."""

    def test_save_deduplicates_duplicate_export_order(self, tmp_path: Path) -> None:
        """Duplicate names in export_order appear only once in output."""
        repository = CsvRepository()
        document = CsvDocument(
            headers=["sku", "description", "generated"],
            rows=[{"sku": "A-1", "description": "desc", "generated": "gen"}],
            dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
        )
        config = CsvConfig(
            delimiter=",",
            encoding="utf-8",
            export_order=["sku", "sku", "description", "sku"],
        )

        output_path = tmp_path / "out.csv"
        repository.save(output_path, document, config)

        header_line = output_path.read_text(encoding="utf-8").strip().split("\n")[0]
        assert header_line == "sku,description,generated"

    def test_save_ignores_stale_export_order(self, tmp_path: Path) -> None:
        """Stale names in export_order are omitted from output."""
        repository = CsvRepository()
        document = CsvDocument(
            headers=["sku", "description", "generated"],
            rows=[{"sku": "A-1", "description": "desc", "generated": "gen"}],
            dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
        )
        config = CsvConfig(
            delimiter=",",
            encoding="utf-8",
            export_order=["sku", "nonexistent", "description", "missing"],
        )

        output_path = tmp_path / "out.csv"
        repository.save(output_path, document, config)

        header_line = output_path.read_text(encoding="utf-8").strip().split("\n")[0]
        assert header_line == "sku,description,generated"

    def test_save_duplicates_and_stale_includes_all_current_headers(
        self, tmp_path: Path
    ) -> None:
        """After dedup and stale removal, every current header appears once."""
        repository = CsvRepository()
        document = CsvDocument(
            headers=["a", "b", "c", "d", "e"],
            rows=[{"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}],
            dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
        )
        config = CsvConfig(
            delimiter=",",
            encoding="utf-8",
            export_order=["e", "stale", "a", "e", "b", "missing", "b"],
        )

        output_path = tmp_path / "out.csv"
        repository.save(output_path, document, config)

        headers_out = (
            output_path.read_text(encoding="utf-8").strip().split("\n")[0].split(",")
        )
        assert headers_out == ["e", "a", "b", "c", "d"]
        assert len(headers_out) == 5
        assert set(headers_out) == {"a", "b", "c", "d", "e"}

    def test_save_export_order_unchanged_when_no_duplicates_or_stale(
        self, tmp_path: Path
    ) -> None:
        """Clean export_order is not modified."""
        repository = CsvRepository()
        document = CsvDocument(
            headers=["sku", "description", "generated"],
            rows=[{"sku": "A-1", "description": "desc", "generated": "gen"}],
            dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
        )
        config = CsvConfig(
            delimiter=",",
            encoding="utf-8",
            export_order=["generated", "sku", "description"],
        )

        output_path = tmp_path / "out.csv"
        repository.save(output_path, document, config)

        header_line = output_path.read_text(encoding="utf-8").strip().split("\n")[0]
        assert header_line == "generated,sku,description"

