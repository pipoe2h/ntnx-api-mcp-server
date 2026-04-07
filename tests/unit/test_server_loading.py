"""Unit tests for startup YAML source selection."""

from __future__ import annotations

from pathlib import Path

from src.config import Settings
from src.server import infer_namespace, list_yaml_artifacts, select_artifact_source


def test_select_artifact_source_prefers_runtime(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "default_specs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    (runtime_dir / "prism-v4.3-all-documentation.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    (default_dir / "vmm-v4.2-all-documentation.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")

    settings = Settings(
        artifacts_dir=runtime_dir,
        default_artifacts_dir=default_dir,
    )
    source, selected_dir = select_artifact_source(settings)

    assert source == "runtime"
    assert selected_dir == runtime_dir
    assert len(list_yaml_artifacts(selected_dir)) == 1


def test_infer_namespace_from_filename() -> None:
    file_path = Path("networking-v4.3-all-documentation.yaml")
    assert infer_namespace(file_path) == "networking"
