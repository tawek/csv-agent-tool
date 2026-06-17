from pathlib import Path

from product_description_tool.config import CsvReadSettings, CsvWriteSettings, FieldConfig
from product_description_tool.csv_repository import CsvDocument, CsvDialectSettings, CsvRepository


def test_loads_and_preserves_headers(tmp_path: Path) -> None:
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("sku,description\nA-1,<p>Alpha</p>\n", encoding="utf-8")

    repository = CsvRepository()
    document = repository.load(csv_path, CsvReadSettings(encoding="utf-8", delimiter=","))

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
    config = CsvWriteSettings(
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
    document = repository.load(csv_path, CsvReadSettings(encoding="utf-8", delimiter=","))

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
    config = CsvWriteSettings(
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
    config = CsvWriteSettings(
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
    """CsvWriteSettings.export_order determines the column order in the output CSV."""
    repository = CsvRepository()
    document = CsvDocument(
        headers=["sku", "description", "generated"],
        rows=[{"sku": "A-1", "description": "<p>Alpha</p>", "generated": "<p>Beta</p>"}],
        dialect=CsvDialectSettings(delimiter=",", quotechar='"'),
    )
    config = CsvWriteSettings(
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
    config = CsvWriteSettings(
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
    config = CsvWriteSettings(delimiter=",", encoding="utf-8")

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
    config = CsvWriteSettings(
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
    """CsvConfig serializes and deserializes export_order correctly via export_settings."""
    from product_description_tool.config import CsvConfig

    original = CsvConfig()
    original.export_order = ["generated", "sku", "description"]
    serialized = original.to_dict()
    restored = CsvConfig.from_dict(serialized)
    assert restored.export_order == ["generated", "sku", "description"]


def test_csv_config_export_order_defaults_to_empty() -> None:
    """CsvConfig export_order defaults to empty list."""
    from product_description_tool.config import CsvConfig

    config = CsvConfig()
    assert config.export_order == []
    serialized = config.to_dict()
    assert serialized["export_settings"]["export-order"] == []
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
        config = CsvWriteSettings(
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
        config = CsvWriteSettings(
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
        config = CsvWriteSettings(
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
        config = CsvWriteSettings(
            delimiter=",",
            encoding="utf-8",
            export_order=["generated", "sku", "description"],
        )

        output_path = tmp_path / "out.csv"
        repository.save(output_path, document, config)

        header_line = output_path.read_text(encoding="utf-8").strip().split("\n")[0]
        assert header_line == "generated,sku,description"


# ---------------------------------------------------------------------------
# Import auto-detection tests (AR-6)
# ---------------------------------------------------------------------------


class TestDetectSettings:
    """Tests for CsvRepository.detect_settings()."""

    def test_detect_semicolon_delimited(self, tmp_path: Path) -> None:
        """Detect semicolon delimiter and double-quote char."""
        csv_path = tmp_path / "semicol.csv"
        csv_path.write_text(
            "sku;name;desc\n1;\"Alpha\";\"Long text\"\n2;\"Beta\";\"More\"\n",
            encoding="utf-8",
        )
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.delimiter == ";"
        assert settings.quotechar == '"'

    def test_detect_comma_delimited(self, tmp_path: Path) -> None:
        """Detect comma delimiter."""
        csv_path = tmp_path / "comma.csv"
        csv_path.write_text(
            "sku,name,desc\n1,\"Alpha\",\"Long\"\n2,\"Beta\",\"More\"\n",
            encoding="utf-8",
        )
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.delimiter == ","

    def test_detect_tab_delimited(self, tmp_path: Path) -> None:
        """Detect tab delimiter."""
        csv_path = tmp_path / "tabbed.csv"
        csv_path.write_text(
            "sku\tname\tdesc\n1\t\"Alpha\"\t\"Long\"\n2\t\"Beta\"\t\"More\"\n",
            encoding="utf-8",
        )
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.delimiter == "\t"

    def test_detect_utf8_encoding(self, tmp_path: Path) -> None:
        """Detect UTF-8 encoding without BOM."""
        csv_path = tmp_path / "utf8.csv"
        csv_path.write_text("a;b\n1;2\n", encoding="utf-8")
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.encoding in ("utf-8", "utf-8-sig")

    def test_detect_utf8_bom_encoding(self, tmp_path: Path) -> None:
        """Detect UTF-8 with BOM (utf-8-sig)."""
        csv_path = tmp_path / "bom.csv"
        csv_path.write_bytes(b"\xef\xbb\xbfa;b\r\n1;2\r\n")
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.encoding == "utf-8-sig"

    def test_detect_newline_lf(self, tmp_path: Path) -> None:
        """Detect LF line endings."""
        csv_path = tmp_path / "lf.csv"
        csv_path.write_text("a;b\n1;2\n", encoding="utf-8")
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.newline == "\n"

    def test_detect_newline_crlf(self, tmp_path: Path) -> None:
        """Detect CRLF line endings (returns universal '')."""
        csv_path = tmp_path / "crlf.csv"
        csv_path.write_bytes(b"a;b\r\n1;2\r\n")
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.newline == ""

    def test_detect_quotechar_single_quote(self, tmp_path: Path) -> None:
        """Detect single-quote quotechar when used consistently."""
        csv_path = tmp_path / "singleq.csv"
        csv_path.write_text(
            "sku;name;desc\n1;'Alpha';'Long text'\n2;'Beta';'More'\n",
            encoding="utf-8",
        )
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.delimiter == ";"
        assert settings.quotechar == "'"

    def test_detect_single_column_file_uses_defaults(self, tmp_path: Path) -> None:
        """Single-column CSV falls back to defaults."""
        csv_path = tmp_path / "single.csv"
        csv_path.write_text("sku\n1\n2\n", encoding="utf-8")
        settings = CsvRepository.detect_settings(csv_path)
        # Less than 2 data lines with >1 field → fallback defaults
        assert settings.delimiter == ";"
        assert settings.quotechar == '"'

    def test_detect_pipe_delimited(self, tmp_path: Path) -> None:
        """Detect pipe delimiter when consistent."""
        csv_path = tmp_path / "pipe.csv"
        csv_path.write_text(
            "sku|name|desc\n1|\"Alpha\"|\"Long\"\n2|\"Beta\"|\"More\"\n",
            encoding="utf-8",
        )
        settings = CsvRepository.detect_settings(csv_path)
        assert settings.delimiter == "|"

    def test_detect_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """Missing file returns default CsvReadSettings (no crash)."""
        missing = tmp_path / "nonexistent.csv"
        settings = CsvRepository.detect_settings(missing)
        assert settings.delimiter == ";"
        assert settings.encoding == "utf-8-sig"

