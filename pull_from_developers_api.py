"""PC-version-driven YAML fetcher from developers endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from src.auth import build_basic_auth
from src.config import Settings
from src.config.constants import (
    ARTIFACT_FILENAME_SUFFIX,
    DEVELOPERS_YAML_DOWNLOAD_TEMPLATE,
    PC_NAMESPACE_VERSION_PROBE_TEMPLATE,
)


@dataclass(slots=True)
class DownloadSummary:
    """Fetch summary for init/refresh workflows."""

    success: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_reasons: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.skipped_reasons is None:
            self.skipped_reasons = {}

    def add_skipped(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


def get_namespaces(settings: Settings) -> list[str]:
    """Fetch namespace names from discovery endpoint unless overridden."""
    if settings.namespace_overrides:
        return settings.namespace_overrides

    with httpx.Client(timeout=settings.startup_timeout_seconds) as client:
        response = client.get(settings.namespace_source_url)
    response.raise_for_status()

    payload = response.json()
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        values = payload["data"]
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
    with httpx.Client(
        timeout=settings.startup_timeout_seconds,
        verify=not settings.pc_insecure,
        auth=build_basic_auth(settings),
    ) as client:
        response = client.options(url)

    if response.status_code == 404:
        return None
    if response.is_error:
        response.raise_for_status()
    return _extract_version(response)


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
    artifacts_dir = settings.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if refresh:
        _clear_previous_artifacts(artifacts_dir)

    summary = DownloadSummary()
    for namespace in get_namespaces(settings):
        try:
            version = get_namespace_version(settings, namespace)
            if not version:
                summary.add_skipped("missing_version_or_namespace")
                continue

            output_path = artifacts_dir / f"{namespace}-{version}{ARTIFACT_FILENAME_SUFFIX}"
            if output_path.exists() and not force:
                summary.add_skipped("already_exists")
                continue

            content = _download_yaml(settings, namespace, version)
            if not _validate_and_save_yaml(content, output_path):
                summary.failed += 1
                continue
            summary.success += 1
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                summary.add_skipped("not_found")
            else:
                summary.failed += 1
        except Exception:
            summary.failed += 1

    return summary
