"""Regression tests for CsvConfig default/fallback consistency.

These tests verify that from_dict handles missing, None, and empty-string
values according to the spec defaults:
  - export_only_visible defaults to True
  - delimiter defaults to ";"
"""

from pathlib import Path

from product_description_tool.config import AppConfig, ConfigStore, CsvConfig, CsvReadSettings, CsvWriteSettings


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


class TestCsvConfigSplitSettings:
    """Tests for the separated import/export settings model."""

    def test_new_style_serialization(self) -> None:
        """New-style CsvConfig serializes to nested dict structure."""
        config = CsvConfig()
        config.import_settings.delimiter = "|"
        config.import_settings.encoding = "latin-1"
        config.export_settings.delimiter = ";"
        config.export_settings.export_path = "/some/path.csv"
        config.export_settings.export_only_visible = False
        config.export_settings_initialized = True

        data = config.to_dict()
        assert "import_settings" in data
        assert "export_settings" in data
        assert data["export_settings_initialized"] is True
        assert data["import_settings"]["delimiter"] == "|"
        assert data["import_settings"]["encoding"] == "latin-1"
        assert data["export_settings"]["delimiter"] == ";"
        assert data["export_settings"]["export-path"] == "/some/path.csv"
        assert data["export_settings"]["export-only-visible"] is False

        restored = CsvConfig.from_dict(data)
        assert restored.import_settings.delimiter == "|"
        assert restored.import_settings.encoding == "latin-1"
        assert restored.export_settings.delimiter == ";"
        assert restored.export_settings.export_path == "/some/path.csv"
        assert restored.export_settings.export_only_visible is False
        assert restored.export_settings_initialized is True

    def test_new_style_defaults(self) -> None:
        """Fresh CsvConfig has no export settings initialized and uses defaults."""
        config = CsvConfig()
        assert config.export_settings_initialized is False
        assert config.import_settings.delimiter == ";"
        assert config.export_settings.delimiter == ";"
        assert config.export_settings.fields == {}

    def test_import_and_export_can_diverge(self) -> None:
        """Import and export settings can have different delimiter values."""
        config = CsvConfig()
        config.import_settings.delimiter = ","
        config.export_settings.delimiter = ";"
        config.export_settings_initialized = True

        assert config.import_settings.delimiter == ","
        assert config.export_settings.delimiter == ";"
        assert config.import_settings.delimiter != config.export_settings.delimiter

    def test_backward_compat_properties_delegate_to_export(self) -> None:
        """CsvConfig.delimiter etc delegate to export_settings."""
        config = CsvConfig()
        config.export_settings.delimiter = "|"
        config.export_settings.quotechar = "'"
        config.export_settings.encoding = "utf-16"
        config.export_settings.newline = "\r\n"
        config.export_settings.write_header = False
        config.export_settings.export_path = "/out.csv"
        config.export_settings.export_only_visible = False
        config.export_settings.fields = {}

        assert config.delimiter == "|"
        assert config.quotechar == "'"
        assert config.encoding == "utf-16"
        assert config.newline == "\r\n"
        assert config.write_header is False
        assert config.export_path == "/out.csv"
        assert config.export_only_visible is False

        # Also test setters
        config.delimiter = ";"
        assert config.export_settings.delimiter == ";"

    def test_legacy_flat_dict_populates_both_settings(self) -> None:
        """Legacy flat dict (without import/export keys) populates both settings
        and marks export as initialized."""
        data = {
            "delimiter": "|",
            "quotechar": "'",
            "encoding": "iso-8859-1",
            "newline": "\r\n",
            "write_header": True,
            "export-only-visible": False,
            "export-path": "/legacy.csv",
            "export-order": ["a", "b"],
            "fields": {
                "a": {"label": "A", "show": True},
            },
        }
        config = CsvConfig.from_dict(data)
        assert config.import_settings.delimiter == "|"
        assert config.export_settings.delimiter == "|"
        assert config.import_settings.quotechar == "'"
        assert config.export_settings.quotechar == "'"
        assert config.export_settings.export_path == "/legacy.csv"
        assert config.export_settings.export_only_visible is False
        assert config.export_settings.export_order == ["a", "b"]
        assert "a" in config.export_settings.fields
        assert config.export_settings_initialized is True

    def test_legacy_empty_dict_populates_defaults_and_marks_initialized(self) -> None:
        """Legacy from_dict({}) populates both settings with defaults and
        marks export initialized."""
        config = CsvConfig.from_dict({})
        assert config.import_settings.delimiter == ";"
        assert config.export_settings.delimiter == ";"
        assert config.export_settings_initialized is True


class TestCsvReadSettings:
    """Tests for CsvReadSettings serialization."""

    def test_round_trip(self) -> None:
        settings = CsvReadSettings(delimiter=",", encoding="utf-16")
        data = settings.to_dict()
        restored = CsvReadSettings.from_dict(data)
        assert restored.delimiter == ","
        assert restored.encoding == "utf-16"

    def test_defaults(self) -> None:
        settings = CsvReadSettings()
        assert settings.delimiter == ";"
        assert settings.quotechar == '"'
        assert settings.encoding == "utf-8-sig"
        assert settings.newline == ""

    def test_from_dict_missing_keys(self) -> None:
        settings = CsvReadSettings.from_dict({})
        assert settings.delimiter == ";"


class TestCsvWriteSettings:
    """Tests for CsvWriteSettings serialization."""

    def test_round_trip(self) -> None:
        settings = CsvWriteSettings(
            delimiter=",",
            encoding="utf-8",
            export_path="/out.csv",
            export_only_visible=False,
        )
        data = settings.to_dict()
        restored = CsvWriteSettings.from_dict(data)
        assert restored.delimiter == ","
        assert restored.export_path == "/out.csv"
        assert restored.export_only_visible is False

    def test_defaults(self) -> None:
        settings = CsvWriteSettings()
        assert settings.delimiter == ";"
        assert settings.export_only_visible is True
        assert settings.export_path == ""
        assert settings.export_order == []
        assert settings.fields == {}

    def test_export_order_preserved(self) -> None:
        settings = CsvWriteSettings(export_order=["c", "b", "a"])
        data = settings.to_dict()
        assert data["export-order"] == ["c", "b", "a"]
        restored = CsvWriteSettings.from_dict(data)
        assert restored.export_order == ["c", "b", "a"]


class TestConfigStoreRoundTrip:
    """ConfigStore save/load round-trip must preserve all app config sections
    including CSV settings (AR-9)."""

    def test_save_load_preserves_csv_settings(self, tmp_path: Path) -> None:
        """Custom CSV settings survive ConfigStore save/load round-trip."""
        store = ConfigStore(tmp_path / "config.json")
        config = AppConfig()
        config.csv.export_settings.delimiter = "|"
        config.csv.export_settings.encoding = "utf-16"
        config.csv.export_settings.export_only_visible = False
        config.csv.export_settings_initialized = True
        store.save(config)
        loaded = store.load()
        assert loaded.csv.export_settings.delimiter == "|"
        assert loaded.csv.export_settings.encoding == "utf-16"
        assert loaded.csv.export_settings.export_only_visible is False
        assert loaded.csv.export_settings_initialized is True
        # Provider and generation sections should also survive
        assert loaded.provider.active == "ollama"
        assert loaded.generation.temperature == 0.2

    def test_save_load_preserves_fresh_defaults(self, tmp_path: Path) -> None:
        """Fresh default AppConfig round-trips with export_settings_initialized=False."""
        store = ConfigStore(tmp_path / "config.json")
        config = AppConfig()
        store.save(config)
        loaded = store.load()
        assert loaded.csv.export_settings_initialized is False
        assert loaded.csv.export_settings.delimiter == ";"
        assert loaded.csv.import_settings.delimiter == ";"
        assert loaded.csv.import_settings.encoding == "utf-8-sig"

    def test_save_load_preserves_import_export_divergence(self, tmp_path: Path) -> None:
        """When import and export settings have diverged, both survive round-trip."""
        store = ConfigStore(tmp_path / "config.json")
        config = AppConfig()
        config.csv.import_settings.delimiter = ","
        config.csv.export_settings.delimiter = ";"
        config.csv.export_settings_initialized = True
        store.save(config)
        loaded = store.load()
        assert loaded.csv.import_settings.delimiter == ","
        assert loaded.csv.export_settings.delimiter == ";"
        assert loaded.csv.export_settings_initialized is True

    def test_load_nonexistent_returns_default_config(self, tmp_path: Path) -> None:
        """Loading from a nonexistent path returns a fresh default AppConfig."""
        store = ConfigStore(tmp_path / "nonexistent" / "config.json")
        config = store.load()
        assert isinstance(config, AppConfig)
        assert config.csv.export_settings_initialized is False
        assert config.csv.export_settings.delimiter == ";"

    def test_legacy_config_without_csv_key_still_loads(self, tmp_path: Path) -> None:
        """A saved config file without a 'csv' key (pre-AR-9 format) still loads
        and legacy fallback marks export_settings_initialized=True."""
        import json
        store = ConfigStore(tmp_path / "old_config.json")
        store.path.write_text(
            json.dumps({
                "provider": {"active": "ollama", "ollama": {}, "openai": {}},
                "generation": {},
            }),
            encoding="utf-8",
        )
        loaded = store.load()
        # Legacy fallback: no csv key → {} → CsvConfig.from_dict({}) → legacy path
        assert loaded.csv.export_settings_initialized is True
        assert loaded.csv.export_settings.delimiter == ";"
