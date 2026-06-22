# Configuration reference — Nutanix V4 API MCP Server

> **Scope:** Syntax, defaults, and runtime behavior of every configuration option.
> Authentication implications: [authentication and security guide](authentication.md). Deployment setup: [deployment guide](deployment.md).

---

## Complete annotated example config

A `.env` file containing every supported option. Copy, replace placeholder values, and place it in
the working directory where `nutanix-mcp` is launched (or pass a path with `--config-file`).

```dotenv
# ── Prism Central connection ─────────────────────────────────────────────────

# IP address or FQDN of the Prism Central instance.
# Required for live API execution; omit to run in latest-release (offline) mode.
PC_HOST=your-pc.example.com

# TCP port that Prism Central listens on for V4 API requests.
# Default: 9440. When set to 9440 the base URL scheme is https://; any other
# port forces http://.
PC_PORT=9440

# ── Authentication ────────────────────────────────────────────────────────────

# Basic-auth username for Prism Central.
# Required when using basic auth (must be paired with PC_PASSWORD).
PC_USERNAME=your-username

# Basic-auth password for Prism Central.
# Stored in memory as SecretStr; masked as ********** in all log output.
# WARNING: written in plaintext to .env by the init/refresh commands.
PC_PASSWORD=your-password

# API key for the X-ntnx-api-key header.
# Prefer over basic auth when both are set — PC_API_KEY takes priority.
# Stored in memory as SecretStr; masked as ********** in all log output.
PC_API_KEY=your-api-key

# ── TLS ───────────────────────────────────────────────────────────────────────

# Set to "false" to enable TLS certificate verification (default; recommended for production).
# Set to "true" to disable certificate verification — use only for dev/test with self-signed certs.
PC_INSECURE=false

# ── Artifact storage ──────────────────────────────────────────────────────────

# Directory where downloaded OpenAPI YAML artifacts are stored.
# Created automatically if absent. Paths starting with /app/ that raise
# PermissionError are silently remapped to <project_root>/artifacts.
# Default: <project_root>/artifacts
ARTIFACTS_DIR=/home/user/.nutanix-mcp/artifacts

# ── Logging ──────────────────────────────────────────────────────────────────

# Minimum log level emitted to both stderr and the per-restart log file.
# Allowed: DEBUG | INFO | WARNING | ERROR | CRITICAL
# Default: INFO
LOG_LEVEL=INFO

# Log output format.
# "text"  → %(asctime)s %(levelname)s %(name)s %(message)s
# "json"  → {"timestamp":"...","level":"...","logger":"...","message":"..."}
# Default: text
LOG_FORMAT=text

# Directory for per-restart log files.
# A new file is created on each startup with a microsecond-precision timestamp.
# Pattern: <LOG_DIR>/nutanix-mcp-<YYYYMMDD>-<HHMMSS>-<microseconds>.log
# Default: <project_root>/logs
LOG_DIR=/home/user/.nutanix-mcp/logs

# ── Namespace discovery ───────────────────────────────────────────────────────

# Endpoint that returns the list of available API namespaces.
# Override only if you mirror the Nutanix developer portal internally.
# Default: https://developers.nutanix.com/api/v1/namespaces
NAMESPACE_SOURCE_URL=https://developers.nutanix.com/api/v1/namespaces

# Comma-separated list of namespace names to load at startup.
# When set, only listed namespaces are fetched and registered as tools.
# Omit this variable to load all namespaces available on the PC instance.
# Example: NAMESPACE_OVERRIDE_LIST=aiops,vmm,prism
# NAMESPACE_OVERRIDE_LIST=

# ── Runtime controls ──────────────────────────────────────────────────────────

# Block all non-GET (write) operations server-side before they reach Prism Central.
# true  = read-only mode enforced (default; recommended)
# false = write operations allowed — set explicitly to opt in to create/update/delete
READ_ONLY_MODE=true

```

The same keys can be placed in a `.json`, `.yaml`/`.yml`, or `.toml` file and passed via
`--config-file <path>`:

```toml
# config.toml — equivalent to the .env above
pc_host                = "your-pc.example.com"
pc_port                = 9440
pc_username            = "your-username"
pc_password            = "your-password"
pc_api_key             = "your-api-key"
pc_insecure            = false
artifacts_dir          = "/home/user/.nutanix-mcp/artifacts"
log_level              = "INFO"
log_format             = "text"
log_dir                = "/home/user/.nutanix-mcp/logs"
namespace_source_url   = "https://developers.nutanix.com/api/v1/namespaces"
# namespace_override_list = "aiops,vmm,prism"  # uncomment to restrict namespaces
read_only_mode         = true
```

---

## Environment variables

All variables are read from the process environment, or from a `.env` file in the current working
directory (loaded automatically via `pydantic-settings`). Variable names are case-insensitive.

### Connection

| Variable | Description | Required | Default | Example |
|---|---|---|---|---|
| `PC_HOST` | Prism Central IP address or FQDN | Yes (for live execution) | *(none)* | `your-pc.example.com` |
| `PC_PORT` | Prism Central API port | No | `9440` | `9440` |

### Authentication

| Variable | Description | Required | Default | Example |
|---|---|---|---|---|
| `PC_USERNAME` | Basic-auth username — **mutually exclusive with `PC_API_KEY`** | One of `PC_USERNAME`/`PC_PASSWORD` **or** `PC_API_KEY` required when `PC_HOST` is set | *(none)* | `admin` |
| `PC_PASSWORD` | Basic-auth password | Required when `PC_USERNAME` is set | *(none)* | `your-password` |
| `PC_API_KEY` | API key sent as `X-ntnx-api-key` header — **mutually exclusive with `PC_USERNAME`** | One of `PC_USERNAME`/`PC_PASSWORD` **or** `PC_API_KEY` required when `PC_HOST` is set | *(none)* | `ntnx-abc123…` |

### TLS

| Variable | Description | Required | Default | Example |
|---|---|---|---|---|
| `PC_INSECURE` | `"true"` disables TLS certificate verification; `"false"` enables it | No | `"false"` | `"true"` |

### Behavior

| Variable | Description | Required | Default | Example |
|---|---|---|---|---|
| `ARTIFACTS_DIR` | Directory for downloaded OpenAPI YAML files; created on startup. **Use an absolute path** in AI client config files. | No | `<project_root>/artifacts` | `/opt/nutanix-mcp/artifacts` |
| `NAMESPACE_SOURCE_URL` | Namespace-list discovery endpoint | No | `https://developers.nutanix.com/api/v1/namespaces` | *(use default)* |
| `NAMESPACE_OVERRIDE_LIST` | Comma-separated list of namespace names to load. When set, only these namespaces are fetched and registered as tools — all others are skipped. Useful for air-gapped environments or when only a subset of namespaces is needed. | No | *(none — all available namespaces loaded)* | `aiops,vmm,prism` |
| `READ_ONLY_MODE` | When `"true"`, all non-GET operations are rejected server-side before reaching Prism Central | No | `"true"` | `"false"` |

### Logging

| Variable | Description | Required | Default | Example |
|---|---|---|---|---|
| `LOG_LEVEL` | Minimum log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`) | No | `INFO` | `DEBUG` |
| `LOG_FORMAT` | Log formatter: `text` or `json` | No | `text` | `json` |
| `LOG_DIR` | Directory for per-restart log files; created on startup | No | `<project_root>/logs` | `/var/log/nutanix-mcp` |

---

## Config file schema

All keys are optional. Keys map 1:1 to environment variable names (lowercased). When both a config
file key and an environment variable are set, see [Precedence rules](#precedence-rules) below.

**Supported formats:** `.json`, `.yaml`, `.yml`, `.toml`

| Key | Type | Default | Description |
|---|---|---|---|
| `pc_host` | string | *(none)* | Prism Central IP address or FQDN |
| `pc_port` | integer | `9440` | Prism Central API port |
| `pc_username` | string | *(none)* | Basic-auth username |
| `pc_password` | string | *(none)* | Basic-auth password; treated as `SecretStr` in memory |
| `pc_api_key` | string | *(none)* | API key sent as `X-ntnx-api-key`; treated as `SecretStr` in memory |
| `pc_insecure` | boolean | `false` | `true` = TLS verification disabled; `false` = TLS verification enabled (default; recommended for production) |
| `artifacts_dir` | path string | `<project_root>/artifacts` | Runtime artifact directory; created if absent |
| `log_level` | string | `"INFO"` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `log_format` | string | `"text"` | `"text"` or `"json"` |
| `log_dir` | path string | `<project_root>/logs` | Per-restart log file directory; created if absent |
| `namespace_source_url` | URL string | `https://developers.nutanix.com/api/v1/namespaces` | Namespace-list discovery endpoint |
| `namespace_override_list` | string | *(none)* | Comma-separated namespace names to load (e.g. `aiops,vmm,prism`). When set, only listed namespaces are fetched and registered. All others are skipped. |
| `read_only_mode` | boolean | `true` | `true` = block all non-GET operations server-side (default; recommended); `false` = allow write operations (opt-in) |

### Notes on specific keys

**`pc_port` and the URL scheme**

The base API URL is constructed as:

```
https://{pc_host}:{pc_port}/api   # when pc_port == 9440
http://{pc_host}:{pc_port}/api    # when pc_port != 9440
```

**`pc_insecure`**

In `.env` files, pass the string `"true"` or `"false"`. In `.toml`/`.json`/`.yaml` files, use the
native boolean `true` / `false`. Pydantic parses both forms.

---

## Precedence rules

When the same option is set in more than one source, the source with higher precedence wins.
Sources are applied in this order (highest to lowest):

```
1. CLI flags          (--pc-host, --pc-port, --log-level, …)
2. --config-file      (any .json/.yaml/.yml/.toml file passed explicitly)
3. Environment vars   (process environment or .env in the working directory)
4. Hardcoded defaults (defined in src/config/settings.py)
```

**Merge behavior:** this is a simple override, not a deep merge. A config-file key replaces the
env-var value for that same key entirely; there is no partial merge within a single key.

**`.env` file:** The `.env` file in the current working directory is treated as equivalent to
environment variables. It is loaded by `pydantic-settings` before CLI overrides are applied, so
CLI flags always win over `.env` values.

**Code path:** `src/config/settings.py` → `load_settings()`:

1. `_build_env_payload()` reads the 12 supported env vars from `os.environ` (which already
   includes values loaded from `.env` by pydantic-settings).
2. `_load_settings_file()` reads the `--config-file` and its keys overwrite the env payload.
3. `overrides` dict (built from CLI args) is applied last, overwriting everything.

---

## Startup validation

### What runs at startup

Validation runs in this sequence:

1. CLI args are parsed.
2. Settings are loaded (env → config-file → CLI overrides).
3. Directory paths (`artifacts_dir`, `log_dir`) are created if absent.
4. Logging is configured; a new per-restart log file is opened.
5. For `serve-stdio`: YAML artifacts are loaded from `artifacts_dir`; if none are found startup fails.
6. For `run` (without `--validate-only`) when `PC_HOST` is set: a connectivity/auth probe is
   issued against `https://{pc_host}:{pc_port}/api/prism/unversioned/info` (OPTIONS request,
   up to 3 attempts with exponential backoff: 1 s, then up to 8 s between retries).

### Missing required values

| Condition | Exact error message | Exit code |
|---|---|---|
| `PC_HOST` set but neither auth method configured | `"No Prism Central auth configured. Set either PC_API_KEY or PC_USERNAME + PC_PASSWORD (not both)."` | `1` (via `StartupAuthError`) |
| `PC_HOST` absent on `run` | Probe is skipped; warning printed: `"PC_HOST is not configured. Running with latest-release artifacts; API execution calls require a configured Prism Central host."` | `0` |
| `PC_HOST` absent on `serve-stdio` | Server starts; all `_execute` tool calls fail at runtime with `ValueError: PC_HOST is required to build Prism Central base URL.` | — |
| No YAML artifacts found | `"No YAML artifacts found in runtime or bundled directories."` (raised as `RuntimeError`) | `1` |
| `artifacts_dir` not writable | `"Artifacts directory is not writable: <path>"` | `1` |
| Config file path does not exist | `"Settings file does not exist: <path>"` | `1` |
| Config file path is not a file | `"Settings path is not a file: <path>"` | `1` |
| Unsupported config file extension | `"Unsupported settings file extension. Use .json, .yaml/.yml, or .toml."` | `1` |

### Malformed values

| Condition | Behavior |
|---|---|
| `PC_PORT` is not a valid integer | Pydantic raises a `ValidationError` at settings load time; process exits before startup probe |
| `PC_INSECURE` is not `"true"` or `"false"` | Pydantic raises a `ValidationError` at settings load time |
| `LOG_LEVEL` is not one of the five allowed values | Pydantic raises a `ValidationError` at settings load time |
| `LOG_FORMAT` is not `"text"` or `"json"` | Pydantic raises a `ValidationError` at settings load time |

### Connectivity probe error messages

These appear in the `"error"` field of the failed-startup JSON printed to stdout:

| Condition | Exact error message |
|---|---|
| TCP connection refused / unreachable | `"Unable to connect to Prism Central at <host>:<port>."` |
| Connection timeout | `"Startup connectivity probe timed out for <host>:<port>."` |
| Read timeout | `"Startup connectivity probe read timed out for <host>:<port>."` |
| TLS certificate error | `"TLS validation failed during startup probe. Check certificate trust or PC_INSECURE setting."` |
| HTTP 401 or 403 | `"Prism Central authentication failed during startup. Verify PC_API_KEY or PC_USERNAME/PC_PASSWORD permissions."` |
| HTTP 404 | `"Startup probe endpoint was not found on target Prism Central."` |
| Other HTTP error | `"Startup probe failed with HTTP <status_code>."` |
| Generic network error | `"Unexpected network error during startup probe."` |
| Generic transport error | `"Transport failure during startup probe."` |

Failed-startup JSON shape (printed to stdout, exit code `1`):

```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "<error message from above>"
}
```

---

## TLS options

| Key / Variable | Type | Default | What it does |
|---|---|---|---|
| `PC_INSECURE` / `pc_insecure` | boolean | `false` | When `true`, passes `verify=False` to the `httpx` client (TLS verification disabled). When `false` (default), the system certificate store is used to verify the server's TLS certificate. |

**Applicable to:**
- Startup connectivity probe (`src/auth/readiness.py`)
- Runtime API requests (`src/handlers/api_handler.py`)
- Artifact download from `NAMESPACE_SOURCE_URL` (`src/pull_from_developers_api.py`)

**Limitations:**
- Custom CA bundle path: not supported — no config key exists for this.
- Client certificates: not supported.
- Per-request TLS override: not supported — `PC_INSECURE` applies globally.

Security implications of each option: [authentication and security guide](authentication.md).
