"""Unit tests for artifact refresh backup/restore resilience."""

from __future__ import annotations

from pathlib import Path

from src import pull_from_developers_api as fetcher
from src.config import Settings
from src.config.constants import ARTIFACT_FILENAME_SUFFIX


def _settings(artifacts_dir: Path, default_dir: Path) -> Settings:
    return Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        artifacts_dir=artifacts_dir,
        default_artifacts_dir=default_dir,
    )


def test_refresh_rolls_back_when_no_namespace_succeeds(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "default_specs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    old_vmm = artifacts_dir / f"vmm-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_prism = artifacts_dir / f"prism-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_vmm.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")
    old_prism.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")

    monkeypatch.setattr(fetcher, "get_namespaces", lambda _settings: ["vmm"])
    monkeypatch.setattr(fetcher, "get_namespace_version", lambda _settings, _namespace: (_ for _ in ()).throw(RuntimeError("offline")))

    summary = fetcher.download_yamls(
        settings=_settings(artifacts_dir, default_dir),
        refresh=True,
        force=False,
    )

    assert summary.success == 0
    assert summary.failed >= 1
    assert summary.deleted_artifacts == 2
    assert summary.restored_artifacts == 2
    assert old_vmm.exists()
    assert old_prism.exists()


def test_refresh_restores_unprocessed_namespace_artifacts(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "default_specs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    old_vmm = artifacts_dir / f"vmm-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_networking = artifacts_dir / f"networking-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_vmm.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")
    old_networking.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")

    monkeypatch.setattr(fetcher, "get_namespaces", lambda _settings: ["vmm"])
    monkeypatch.setattr(fetcher, "get_namespace_version", lambda _settings, _namespace: "v4.2")
    monkeypatch.setattr(
        fetcher,
        "_download_yaml",
        lambda _settings, _namespace, _version: "openapi: 3.0.0\npaths: {}\n",
    )

    summary = fetcher.download_yamls(
        settings=_settings(artifacts_dir, default_dir),
        refresh=True,
        force=True,
    )

    assert summary.success == 1
    assert summary.failed == 0
    assert summary.deleted_artifacts == 2
    assert summary.restored_artifacts == 1
    assert (artifacts_dir / f"vmm-v4.2{ARTIFACT_FILENAME_SUFFIX}").exists()
    assert old_networking.exists()
