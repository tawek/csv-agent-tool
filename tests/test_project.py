from pathlib import Path

from product_description_tool.project import (
    PROJECT_SUFFIX,
    Project,
    ProjectPrompt,
    ProjectRepository,
    normalize_project_path,
    project_csv_path,
)


def test_normalizes_project_path_and_matching_csv_path(tmp_path: Path) -> None:
    project_path = normalize_project_path(tmp_path / "catalog")

    assert project_path.name == f"catalog{PROJECT_SUFFIX}"
    assert project_csv_path(project_path) == tmp_path / "catalog.csv"


def test_project_repository_round_trips_prompts_and_csv_config(tmp_path: Path) -> None:
    repository = ProjectRepository()
    project = Project(
        prompts=[
            ProjectPrompt(output_field="summary", prompt="Summarize {{sku}}", enabled=True),
            ProjectPrompt(output_field="seo", prompt="SEO {{sku}}", enabled=False),
        ]
    )
    project.csv.delimiter = ";"

    saved_path = repository.save(tmp_path / "catalog.project.json", project)
    loaded = repository.load(saved_path)

    assert loaded.prompts[0].output_field == "summary"
    assert loaded.prompts[0].prompt == "Summarize {{sku}}"
    assert loaded.prompts[0].prompt_file == "summary.prompt.txt"
    assert loaded.prompts[1].enabled is False
    assert loaded.csv.delimiter == ";"
    assert (tmp_path / "summary.prompt.txt").read_text(encoding="utf-8") == "Summarize {{sku}}"


class TestKnowledgeBaseDir:
    def test_kb_dir_field_in_project_round_trip(self) -> None:
        """Knowledge-base directory is preserved in to_dict/from_dict."""
        project = Project(
            prompts=[ProjectPrompt(output_field="desc", prompt="Write about {{sku}}")],
            knowledge_base_dir="/some/kb/path",
        )
        data = project.to_dict()
        assert data.get("knowledge-base-dir") == "/some/kb/path"

        restored = Project.from_dict(data)
        assert restored.knowledge_base_dir == "/some/kb/path"

    def test_kb_dir_none_by_default(self) -> None:
        """New projects have no knowledge-base directory set."""
        project = Project()
        assert project.knowledge_base_dir is None

    def test_save_load_relative_kb_dir(self, tmp_path: Path) -> None:
        """KB dir inside the project directory is stored as relative."""
        repository = ProjectRepository()
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        project = Project(
            prompts=[ProjectPrompt(output_field="desc", prompt="Process {{@help.md}} with {{sku}}")],
            knowledge_base_dir=str(kb_dir),
        )

        saved_path = repository.save(tmp_path / "myproject.project.json", project)
        # The JSON should contain a relative path
        data = (tmp_path / "myproject.project.json").read_text(encoding="utf-8")
        import json
        parsed = json.loads(data)
        assert parsed.get("knowledge-base-dir") == "knowledge"  # relative

        loaded = repository.load(saved_path)
        # The loaded project should have the absolute path
        assert loaded.knowledge_base_dir is not None
        assert Path(loaded.knowledge_base_dir) == kb_dir.resolve()

    def test_save_load_absolute_kb_dir_outside_project(self, tmp_path: Path) -> None:
        """KB dir outside the project tree is stored as absolute."""
        repository = ProjectRepository()
        outside_dir = tmp_path.parent / "external_kb"
        outside_dir.mkdir()
        project = Project(
            prompts=[ProjectPrompt(output_field="desc", prompt="Process {{sku}}")],
            knowledge_base_dir=str(outside_dir),
        )

        saved_path = repository.save(tmp_path / "myproject.project.json", project)
        data = (tmp_path / "myproject.project.json").read_text(encoding="utf-8")
        import json
        parsed = json.loads(data)
        # Should be absolute since it's outside the project directory
        assert parsed.get("knowledge-base-dir") == str(outside_dir)

        loaded = repository.load(saved_path)
        assert loaded.knowledge_base_dir == str(outside_dir.resolve())

    def test_kb_dir_absent_in_manifest_round_trips_as_none(self, tmp_path: Path) -> None:
        """A project manifest without kb dir loads with knowledge_base_dir=None."""
        repository = ProjectRepository()
        project = Project(prompts=[ProjectPrompt(output_field="desc", prompt="Process {{sku}}")])
        saved_path = repository.save(tmp_path / "nokb.project.json", project)
        loaded = repository.load(saved_path)
        assert loaded.knowledge_base_dir is None


class TestCsvImportSettingsUsable:
    """Tests for ProjectRepository.csv_import_settings_usable().

    This method determines whether backward-compatibility fallback is
    needed during project reopen (Architecture:
    csv-reopen-import-settings-strategy.md).
    """

    def test_new_shape_with_import_settings_returns_true(self, tmp_path: Path) -> None:
        """Nested CSV shape with import_settings present → usable."""
        import json
        repo = ProjectRepository()
        project = Project()
        project.csv.import_settings.delimiter = ","
        project.csv.export_settings.delimiter = ";"
        saved_path = repo.save(tmp_path / "test.project.json", project)
        assert repo.csv_import_settings_usable(saved_path) is True

    def test_new_shape_without_import_settings_returns_false(self, tmp_path: Path) -> None:
        """Nested CSV shape without import_settings → not usable (fallback needed)."""
        import json
        repo = ProjectRepository()
        project = Project()
        project.csv.export_settings.delimiter = ";"
        saved_path = repo.save(tmp_path / "test.project.json", project)
        # Rewrite JSON to remove import_settings from nested shape
        raw = json.loads(saved_path.read_text(encoding="utf-8"))
        raw["csv"] = {"export_settings": raw["csv"]["export_settings"]}
        saved_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        assert repo.csv_import_settings_usable(saved_path) is False

    def test_legacy_flat_shape_returns_true(self, tmp_path: Path) -> None:
        """Legacy flat CSV config (no import/export keys) → usable (backward compat)."""
        import json
        repo = ProjectRepository()
        # Write a project JSON with flat CSV structure (old format)
        raw = {
            "prompts": [],
            "csv": {
                "delimiter": ";",
                "quotechar": '"',
                "encoding": "utf-8-sig",
                "newline": "",
                "write_header": True,
                "export-path": "",
                "export-only-visible": True,
                "export-order": [],
                "fields": {},
            },
        }
        path = tmp_path / "legacy.project.json"
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        assert repo.csv_import_settings_usable(path) is True

    def test_nested_with_all_settings_returns_true(self, tmp_path: Path) -> None:
        """Nested CSV shape with both import and export settings → usable."""
        import json
        repo = ProjectRepository()
        raw = {
            "prompts": [],
            "csv": {
                "import_settings": {"delimiter": ",", "quotechar": '"', "encoding": "utf-8", "newline": "\n"},
                "export_settings": {"delimiter": ";", "quotechar": "'", "encoding": "utf-8-sig", "newline": ""},
                "export_settings_initialized": True,
            },
        }
        path = tmp_path / "full.project.json"
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        assert repo.csv_import_settings_usable(path) is True

    def test_empty_csv_key_legacy_fallback(self, tmp_path: Path) -> None:
        """Project JSON with empty csv {} → treated as legacy flat → usable."""
        import json
        repo = ProjectRepository()
        raw = {
            "prompts": [],
            "csv": {},
        }
        path = tmp_path / "empty.project.json"
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        assert repo.csv_import_settings_usable(path) is True

    def test_no_csv_key_legacy_fallback(self, tmp_path: Path) -> None:
        """Project JSON without csv key → treated as legacy flat → usable."""
        import json
        repo = ProjectRepository()
        raw = {
            "prompts": [],
        }
        path = tmp_path / "nocsv.project.json"
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        assert repo.csv_import_settings_usable(path) is True
