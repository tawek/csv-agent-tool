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
    project.csv.original_description = "description"
    project.csv.result_description = "summary"
    project.csv.delimiter = ";"

    saved_path = repository.save(tmp_path / "catalog.project.json", project)
    loaded = repository.load(saved_path)

    assert loaded.prompts[0].output_field == "summary"
    assert loaded.prompts[0].prompt == "Summarize {{sku}}"
    assert loaded.prompts[0].prompt_file == "summary.prompt.txt"
    assert loaded.prompts[1].enabled is False
    assert loaded.csv.result_description == "summary"
    assert loaded.csv.delimiter == ";"
    assert (tmp_path / "summary.prompt.txt").read_text(encoding="utf-8") == "Summarize {{sku}}"
