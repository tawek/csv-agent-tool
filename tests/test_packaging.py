from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_uses_markitdown_local_conversion_extras() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"markitdown[docx,outlook,pdf,pptx,xls,xlsx]>=0.1.6"' in pyproject


def test_pyinstaller_spec_collects_markitdown_runtime_assets() -> None:
    spec = (PROJECT_ROOT / "packaging/product_description_tool.spec").read_text(
        encoding="utf-8"
    )

    assert 'collect_submodules("markitdown")' in spec
    assert 'collect_data_files("markitdown")' in spec
    assert 'collect_data_files("magika")' in spec
