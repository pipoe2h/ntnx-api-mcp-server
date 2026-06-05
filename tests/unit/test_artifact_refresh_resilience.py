"""Unit tests for artifact refresh behavior."""

from __future__ import annotations

from pathlib import Path

import src.pull_from_developers_api as fetcher
from src.config import Settings
from src.config.constants import ARTIFACT_FILENAME_SUFFIX


def _settings(artifacts_dir: Path, default_dir: Path) -> Settings:
    return Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        artifacts_dir=artifacts_dir,
        default_artifacts_dir=default_dir,
    )


def test_refresh_clears_existing_artifacts_before_download(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "default_specs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    old_vmm = artifacts_dir / f"vmm-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_vmm.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")

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
        force=False,
    )

    assert summary.success == 1
    assert summary.failed == 0
    assert not old_vmm.exists()
    assert (artifacts_dir / f"vmm-v4.2{ARTIFACT_FILENAME_SUFFIX}").exists()
    assert not (artifacts_dir / ".refresh_backup").exists()


def test_refresh_rolls_back_when_no_namespace_succeeds(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "default_specs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    old_vmm = artifacts_dir / f"vmm-v4.1{ARTIFACT_FILENAME_SUFFIX}"
    old_vmm.write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")

    monkeypatch.setattr(fetcher, "get_namespaces", lambda _settings: ["vmm"])
    monkeypatch.setattr(fetcher, "get_namespace_version", lambda _settings, _namespace: (_ for _ in ()).throw(RuntimeError("offline")))

    summary = fetcher.download_yamls(
        settings=_settings(artifacts_dir, default_dir),
        refresh=True,
        force=False,
    )

    assert summary.success == 0
    assert summary.failed >= 1
    assert not old_vmm.exists()
    assert not (artifacts_dir / ".refresh_backup").exists()
