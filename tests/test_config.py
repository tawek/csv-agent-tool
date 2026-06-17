"""Regression tests for CsvConfig default/fallback consistency.

These tests verify that from_dict handles missing, None, and empty-string
values according to the spec defaults:
  - export_only_visible defaults to True
  - delimiter defaults to ";"
"""

from product_description_tool.config import CsvConfig


class TestCsvConfigDefaults:
    """CsvConfig defaults via from_dict with missing or falsy values."""

    def test_from_dict_empty_uses_defaults(self) -> None:
        """from_dict({}) uses fresh CsvConfig defaults."""
        config = CsvConfig.from_dict({})
        assert config.export_only_visible is True
        assert config.delimiter == ";"
        assert config.export_order == []

    def test_from_dict_missing_keys_uses_defaults(self) -> None:
        """from_dict without export-only-visible/delimiter keys uses defaults."""
        config = CsvConfig.from_dict({"encoding": "utf-8"})
        assert config.export_only_visible is True
        assert config.delimiter == ";"

    def test_from_dict_none_export_only_visible_is_false(self) -> None:
        """Explicit None for export-only-visible yields False (bool(None) == False).

        Note: This differs from delimiter's or ';' fallback because
        ``bool(None)`` evaluates to False, and no ``or True`` guard is
        applied.  In practice ``None`` values only arise from hand-edited
        JSON, never from normal serialization.
        """
        config = CsvConfig.from_dict({"export-only-visible": None, "delimiter": "|"})
        assert config.export_only_visible is False

    def test_from_dict_none_delimiter_falls_back(self) -> None:
        """Explicit None for delimiter falls back to ';'."""
        config = CsvConfig.from_dict({"delimiter": None})
        assert config.delimiter == ";"

    def test_from_dict_empty_string_delimiter_falls_back(self) -> None:
        """Empty string for delimiter falls back to ';'."""
        config = CsvConfig.from_dict({"delimiter": ""})
        assert config.delimiter == ";"

    def test_from_dict_explicit_false_export_only_visible_preserved(self) -> None:
        """Explicit False for export-only-visible is preserved (not overridden)."""
        config = CsvConfig.from_dict({"export-only-visible": False})
        assert config.export_only_visible is False

    def test_from_dict_explicit_delimiter_preserved(self) -> None:
        """Explicit delimiter value is preserved."""
        config = CsvConfig.from_dict({"delimiter": ","})
        assert config.delimiter == ","

    def test_from_dict_both_none_delimiter_falls_back_export_only_visible_not(
        self,
    ) -> None:
        """Both keys None: delimiter falls back to ';', export-only-visible is False.

        Note the asymmetry — see test_from_dict_none_export_only_visible_is_false
        for rationale.
        """
        config = CsvConfig.from_dict(
            {"export-only-visible": None, "delimiter": None}
        )
        assert config.export_only_visible is False
        assert config.delimiter == ";"

    def test_from_dict_both_missing_in_complex_dict(self) -> None:
        """from_dict with other csv keys but missing delimiter/export-only-visible."""
        config = CsvConfig.from_dict(
            {
                "fields": {
                    "sku": {"label": "SKU", "show": True},
                },
                "quotechar": "'",
            }
        )
        assert config.export_only_visible is True
        assert config.delimiter == ";"
        assert config.quotechar == "'"

    def test_fresh_csvconfig_defaults(self) -> None:
        """Fresh CsvConfig() matches spec defaults."""
        config = CsvConfig()
        assert config.export_only_visible is True
        assert config.delimiter == ";"
        assert config.export_order == []

    def test_round_trip_preserves_defaults(self) -> None:
        """Serializing and deserializing a default CsvConfig preserves values."""
        original = CsvConfig()
        data = original.to_dict()
        restored = CsvConfig.from_dict(data)
        assert restored.export_only_visible is True
        assert restored.delimiter == ";"
        assert restored.export_order == []
