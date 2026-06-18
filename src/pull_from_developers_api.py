"""Artifact fetcher for PC-compatible and latest-release modes."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import time
from typing import Any

import httpx
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from src.auth import build_auth_context
from src.config import Settings
from src.config.constants import (
    ARTIFACT_FILENAME_SUFFIX,
    DEVELOPERS_NAMESPACE_VERSIONS_TEMPLATE,
    DEVELOPERS_YAML_DOWNLOAD_TEMPLATE,
    PC_NAMESPACE_VERSION_PROBE_TEMPLATE,
)


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DownloadSummary:
    """Fetch summary for init/refresh workflows."""

    discovered: int = 0
    processed: int = 0
    success: int = 0
    skipped: int = 0
    # Namespace endpoint returned an HTTP error response (non-404): service not deployed on this PC.
    # Expected during normal init when optional Nutanix services are absent.
    not_available: int = 0
    # Genuine failures: network errors, parse errors, unexpected exceptions.
    failed: int = 0
    deleted_artifacts: int = 0
    restored_artifacts: int = 0
    duration_ms: int = 0
    artifact_mode: str = "pc_compatible"
    skipped_reasons: dict[str, int] | None = None
    not_available_reasons: dict[str, int] | None = None
    failed_reasons: dict[str, int] | None = None
    namespace_results: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.skipped_reasons is None:
            self.skipped_reasons = {}
        if self.not_available_reasons is None:
            self.not_available_reasons = {}
        if self.failed_reasons is None:
            self.failed_reasons = {}
        if self.namespace_results is None:
            self.namespace_results = []

    def add_skipped(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def add_not_available(self, reason: str) -> None:
        self.not_available += 1
        self.not_available_reasons[reason] = self.not_available_reasons.get(reason, 0) + 1

    def add_failed(self, reason: str) -> None:
        self.failed += 1
        self.failed_reasons[reason] = self.failed_reasons.get(reason, 0) + 1

    def add_namespace_result(
        self,
        namespace: str,
        status: str,
        reason: str | None = None,
        version: str | None = None,
        artifact: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        self.namespace_results.append(
            {
                "namespace": namespace,
                "status": status,
                "reason": reason,
                "version": version,
                "artifact": artifact,
                "duration_ms": duration_ms,
            }
        )


def get_namespaces(settings: Settings) -> list[str]:
    """Fetch namespace names from discovery endpoint unless overridden."""
    if settings.namespace_overrides:
        return settings.namespace_overrides

    with httpx.Client(timeout=settings.startup_timeout_seconds, follow_redirects=True) as client:
        response = client.get(settings.namespace_source_url)
    response.raise_for_status()

    payload = response.json()
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            values = payload["data"]
        elif isinstance(payload.get("namespaces"), list):
            values = payload["namespaces"]
        else:
            values = []
    else:
        values = []

    namespaces: list[str] = []
    for item in values:
        if isinstance(item, str):
            namespaces.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("namespace")
            if isinstance(name, str):
                namespaces.append(name)
    return sorted(set(namespaces))


def _extract_version(response: httpx.Response) -> str | None:
    """Extract namespace version from headers/body fallback order."""
    header_version = response.headers.get("API-Version") or response.headers.get("X-API-Version")
    if isinstance(header_version, str) and header_version.strip():
        return header_version.strip()

    try:
        payload = response.json()
    except ValueError:
        return None

    if isinstance(payload, dict):
        for key in ("version", "apiVersion"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data_value = payload.get("data")
        if isinstance(data_value, str) and data_value.strip():
            return data_value.strip()
        if isinstance(data_value, dict):
            for key in ("version", "apiVersion"):
                value = data_value.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def get_namespace_version(settings: Settings, namespace: str) -> str | None:
    """Probe namespace version via OPTIONS on PC unversioned info endpoint."""
    url = PC_NAMESPACE_VERSION_PROBE_TEMPLATE.format(
        pc_host=settings.pc_host,
        pc_port=settings.pc_port,
        namespace=namespace,
    )
    auth, headers = build_auth_context(settings)
    with httpx.Client(
        timeout=settings.startup_timeout_seconds,
        verify=not settings.pc_insecure,
        auth=auth,
    ) as client:
        response = client.options(url, headers=headers)

    if response.status_code == 404:
        return None
    if response.is_error:
        response.raise_for_status()
    return _extract_version(response)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def get_latest_release_version(settings: Settings, namespace: str) -> str | None:
    """Fetch latest available namespace release version from developers endpoint."""
    url = DEVELOPERS_NAMESPACE_VERSIONS_TEMPLATE.format(namespace=namespace)
    with httpx.Client(timeout=settings.startup_timeout_seconds, follow_redirects=True) as client:
        response = client.get(url)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    versions = payload.get("versions")
    if not isinstance(versions, list):
        return None
    candidates: list[str] = []
    for item in versions:
        if not isinstance(item, dict):
            continue
        value = item.get("version")
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    if not candidates:
        return None
    return _pick_latest_version(candidates)


def _pick_latest_version(versions: list[str]) -> str:
    """Pick latest version using numeric sort with stable fallback."""
    def sort_key(version: str) -> tuple[int, ...]:
        clean = version.lstrip("vV")
        parts = clean.split(".")
        values: list[int] = []
        for part in parts:
            digits = "".join(ch for ch in part if ch.isdigit())
            values.append(int(digits) if digits else 0)
        return tuple(values)

    return sorted(versions, key=sort_key, reverse=True)[0]


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def _download_yaml(settings: Settings, namespace: str, version: str) -> str:
    """Download namespace YAML for exact discovered version."""
    url = DEVELOPERS_YAML_DOWNLOAD_TEMPLATE.format(namespace=namespace, version=version)
    with httpx.Client(timeout=settings.startup_timeout_seconds) as client:
        response = client.get(url)
    response.raise_for_status()
    return response.text


def _validate_and_save_yaml(content: str, output_path: Path) -> bool:
    """Validate YAML before keeping file on disk."""
    output_path.write_text(content, encoding="utf-8")
    try:
        with output_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError:
        output_path.unlink(missing_ok=True)
        return False
    if loaded is None:
        output_path.unlink(missing_ok=True)
        return False
    return True


def _clear_previous_artifacts(artifacts_dir: Path) -> None:
    for file_path in artifacts_dir.glob(f"*{ARTIFACT_FILENAME_SUFFIX}"):
        file_path.unlink(missing_ok=True)


def _namespace_from_artifact_filename(file_name: str) -> str:
    dash_index = file_name.find("-")
    if dash_index <= 0:
        return "unknown"
    return file_name[:dash_index]


def _prepare_refresh_backup(artifacts_dir: Path) -> tuple[Path, list[Path]]:
    existing_files = sorted(artifacts_dir.glob(f"*{ARTIFACT_FILENAME_SUFFIX}"))
    backup_dir = artifacts_dir / ".refresh_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for file_path in existing_files:
        shutil.move(str(file_path), str(backup_dir / file_path.name))
    return backup_dir, existing_files


def _restore_backup_artifacts(
    artifacts_dir: Path,
    backup_dir: Path,
    processed_namespaces: set[str],
) -> int:
    restored = 0
    for backup_file in backup_dir.glob(f"*{ARTIFACT_FILENAME_SUFFIX}"):
        namespace = _namespace_from_artifact_filename(backup_file.name)
        # If a namespace was not refreshed successfully this cycle, keep last-known-good artifact.
        if namespace not in processed_namespaces:
            shutil.move(str(backup_file), str(artifacts_dir / backup_file.name))
            restored += 1
    return restored


def download_yamls(
    settings: Settings,
    refresh: bool = False,
    force: bool = False,
) -> DownloadSummary:
    """
    Fetch YAML files based on namespace versions detected from target PC.

    File naming contract:
    `<namespace>-<version>-all-documentation.yaml`
    """
    artifact_mode = "pc_compatible" if settings.pc_host else "latest_release"

    LOGGER.info(
        "event=artifact_download_started mode=%s artifact_mode=%s force=%s",
        "refresh" if refresh else "init",
        artifact_mode,
        force,
    )

    artifacts_dir = settings.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    backup_dir: Path | None = None
    backup_files: list[Path] = []
    if refresh:
        backup_dir, backup_files = _prepare_refresh_backup(artifacts_dir)

    summary = DownloadSummary()
    summary.artifact_mode = artifact_mode
    namespaces = get_namespaces(settings)
    summary.discovered = len(namespaces)
    processed_namespaces: set[str] = set()
    for namespace in namespaces:
        namespace_started = time.perf_counter()
        summary.processed += 1
        try:
            if settings.pc_host:
                version = get_namespace_version(settings, namespace)
            else:
                version = get_latest_release_version(settings, namespace)
            if not version:
                summary.add_skipped("missing_version_or_namespace")
                summary.add_namespace_result(
                    namespace=namespace,
                    status="skipped",
                    reason="missing_version_or_namespace",
                    duration_ms=int((time.perf_counter() - namespace_started) * 1000),
                )
                continue

            output_path = artifacts_dir / f"{namespace}-{version}{ARTIFACT_FILENAME_SUFFIX}"
            if output_path.exists() and not force:
                summary.add_skipped("already_exists")
                summary.add_namespace_result(
                    namespace=namespace,
                    status="skipped",
                    reason="already_exists",
                    version=version,
                    artifact=str(output_path),
                    duration_ms=int((time.perf_counter() - namespace_started) * 1000),
                )
                continue

            content = _download_yaml(settings, namespace, version)
            if not _validate_and_save_yaml(content, output_path):
                summary.add_failed("yaml_validation_failed")
                summary.add_namespace_result(
                    namespace=namespace,
                    status="failed",
                    reason="yaml_validation_failed",
                    version=version,
                    artifact=str(output_path),
                    duration_ms=int((time.perf_counter() - namespace_started) * 1000),
                )
                continue
            processed_namespaces.add(namespace)
            summary.success += 1
            summary.add_namespace_result(
                namespace=namespace,
                status="success",
                version=version,
                artifact=str(output_path),
                duration_ms=int((time.perf_counter() - namespace_started) * 1000),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                summary.add_skipped("not_found")
                summary.add_namespace_result(
                    namespace=namespace,
                    status="skipped",
                    reason="not_found",
                    duration_ms=int((time.perf_counter() - namespace_started) * 1000),
                )
            else:
                # Non-404 HTTP response means the namespace endpoint exists but the service
                # is not deployed or accessible on this PC — expected for optional namespaces.
                http_reason = f"http_{exc.response.status_code}"
                summary.add_not_available(http_reason)
                summary.add_namespace_result(
                    namespace=namespace,
                    status="not_available",
                    reason=http_reason,
                    duration_ms=int((time.perf_counter() - namespace_started) * 1000),
                )
        except Exception as exc:
            summary.add_failed("unexpected_error")
            summary.add_namespace_result(
                namespace=namespace,
                status="failed",
                reason=f"unexpected_error:{type(exc).__name__}",
                duration_ms=int((time.perf_counter() - namespace_started) * 1000),
            )

    if refresh and backup_dir is not None:
        summary.deleted_artifacts = len(backup_files)
        # If refresh had no successful downloads, restore everything for offline resilience.
        if summary.success == 0:
            for backup_file in backup_dir.glob(f"*{ARTIFACT_FILENAME_SUFFIX}"):
                shutil.move(str(backup_file), str(artifacts_dir / backup_file.name))
                summary.restored_artifacts += 1
        else:
            # Keep prior artifacts for namespaces not refreshed successfully.
            summary.restored_artifacts += _restore_backup_artifacts(
                artifacts_dir=artifacts_dir,
                backup_dir=backup_dir,
                processed_namespaces=processed_namespaces,
            )
        shutil.rmtree(backup_dir, ignore_errors=True)

    summary.duration_ms = int((time.perf_counter() - started) * 1000)
    LOGGER.info(
        "event=artifact_download_completed mode=%s artifact_mode=%s discovered=%s processed=%s success=%s skipped=%s not_available=%s failed=%s deleted_artifacts=%s restored_artifacts=%s duration_ms=%s",
        "refresh" if refresh else "init",
        artifact_mode,
        summary.discovered,
        summary.processed,
        summary.success,
        summary.skipped,
        summary.not_available,
        summary.failed,
        summary.deleted_artifacts,
        summary.restored_artifacts,
        summary.duration_ms,
    )
    return summary
