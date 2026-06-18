"""Startup readiness and authentication validation helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings
from src.config.constants import PC_NAMESPACE_VERSION_PROBE_TEMPLATE

LOGGER = logging.getLogger(__name__)


class StartupValidationError(RuntimeError):
    """Base startup readiness failure."""


class StartupAuthError(StartupValidationError):
    """Credential or permission failure during startup check."""


class StartupTlsError(StartupValidationError):
    """TLS handshake/certificate failure during startup check."""


class StartupConnectivityError(StartupValidationError):
    """Network reachability/timeout failure during startup check."""


@dataclass(slots=True)
class StartupReadinessResult:
    """Structured readiness check output."""

    ok: bool
    category: str
    detail: str


def build_basic_auth(settings: Settings) -> tuple[str, str] | None:
    """Build HTTP basic auth tuple when username/password are present."""
    if settings.pc_username and settings.pc_password:
        return (settings.pc_username, settings.pc_password.get_secret_value())
    return None


def build_auth_headers(settings: Settings) -> dict[str, str]:
    """Build API-key authorization headers when key is configured."""
    if settings.pc_api_key:
        return {"X-ntnx-api-key": settings.pc_api_key.get_secret_value()}
    return {}


def build_auth_context(settings: Settings) -> tuple[tuple[str, str] | None, dict[str, str]]:
    """Build outgoing auth context. API key takes priority over basic auth when both are set."""
    if settings.pc_api_key:
        if settings.pc_username or settings.pc_password:
            LOGGER.warning(
                "event=dual_auth_configured "
                "Both PC_API_KEY and PC_USERNAME/PC_PASSWORD are set. "
                "PC_API_KEY takes priority; basic auth credentials are ignored."
            )
        return (None, build_auth_headers(settings))
    return (build_basic_auth(settings), {})


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def _probe_pc(settings: Settings) -> httpx.Response:
    """Probe Prism Central via a stable unversioned endpoint."""
    url = PC_NAMESPACE_VERSION_PROBE_TEMPLATE.format(
        pc_host=settings.pc_host,
        pc_port=settings.pc_port,
        namespace="prism",
    )
    auth, headers = build_auth_context(settings)
    with httpx.Client(
        verify=not settings.pc_insecure,
        timeout=settings.startup_timeout_seconds,
        auth=auth,
    ) as client:
        return client.options(url, headers=headers)


def validate_startup_readiness(settings: Settings) -> StartupReadinessResult:
    """Validate startup readiness before serving tool operations."""
    if not settings.pc_host:
        raise StartupValidationError(
            "PC_HOST is not configured. Connected-mode startup readiness probe cannot run."
        )
    if not settings.pc_api_key and not (settings.pc_username and settings.pc_password):
        raise StartupAuthError(
            "No Prism Central auth configured. "
            "Set either PC_API_KEY or PC_USERNAME + PC_PASSWORD (not both)."
        )

    try:
        response = _probe_pc(settings)
    except httpx.ConnectTimeout as exc:
        raise StartupConnectivityError(
            f"Startup connectivity probe timed out for {settings.pc_host}:{settings.pc_port}."
        ) from exc
    except httpx.ReadTimeout as exc:
        raise StartupConnectivityError(
            f"Startup connectivity probe read timed out for {settings.pc_host}:{settings.pc_port}."
        ) from exc
    except httpx.ConnectError as exc:
        raise StartupConnectivityError(
            f"Unable to connect to Prism Central at {settings.pc_host}:{settings.pc_port}."
        ) from exc
    except httpx.NetworkError as exc:
        raise StartupConnectivityError("Unexpected network error during startup probe.") from exc
    except httpx.TransportError as exc:
        detail = str(exc).lower()
        if "certificate" in detail or "ssl" in detail or "tls" in detail:
            raise StartupTlsError(
                "TLS validation failed during startup probe. "
                "Check certificate trust or PC_INSECURE setting."
            ) from exc
        raise StartupConnectivityError("Transport failure during startup probe.") from exc

    if response.status_code in {401, 403}:
        raise StartupAuthError(
            "Prism Central authentication failed during startup. "
            "Verify PC_API_KEY or PC_USERNAME/PC_PASSWORD permissions."
        )
    if response.status_code == 404:
        raise StartupValidationError(
            "Startup probe endpoint was not found on target Prism Central."
        )
    if response.is_error:
        raise StartupValidationError(f"Startup probe failed with HTTP {response.status_code}.")

    return StartupReadinessResult(
        ok=True,
        category="ready",
        detail="Startup readiness checks passed.",
    )
