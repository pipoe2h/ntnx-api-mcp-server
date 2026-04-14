# ntnx-api-mcp-server

Nutanix API MCP server that exposes Nutanix v4 APIs as Model Context Protocol tools.

## Scope

This repository contains the production implementation of a read-first MCP server
for Nutanix APIs. Delivery is split into incremental pull requests merged into
`main`.

## Requirements

- Python 3.11+
- Access to Nutanix Prism Central for connected mode

## Runtime configuration

Configuration inputs are supported in both Python executable and Docker workflows.

### Source options

1. Environment / `.env`
2. Config file (`.json`, `.yaml`/`.yml`, `.toml`) via `--config-file`
3. CLI flags (highest precedence)

### Required keys (connected mode)

Provide the following values when running connected-mode (`init`, `refresh`, or live API execution):

- `PC_HOST`
- `PC_PORT`
- `PC_USERNAME`
- `PC_PASSWORD`
- `PC_INSECURE` (optional, default: `true`)
- `ARTIFACTS_DIR` (optional, default: `./artifacts`)
- `LOG_LEVEL` (optional, default: `INFO`)
- `LOG_FORMAT` (optional: `text` or `json`)
- `NAMESPACE_SOURCE_URL` (optional, default: Nutanix developers namespaces API)
- `NAMESPACE_OVERRIDE_LIST` (optional comma-separated list)

### Precedence

When multiple sources are used together:

1. `.env` and process environment
2. Config file (`--config-file`)
3. CLI flags

## Commands

### `nutanix-mcp init`

- Discovers namespaces from developers API (or override list)
- Probes namespace version from target Prism Central
- Downloads YAML artifacts as `<namespace>-<version>-all-documentation.yaml`

### `nutanix-mcp refresh`

- Runs refresh with backup/restore safety:
  - stages existing `*-all-documentation.yaml` artifacts into a temporary backup
  - downloads refreshed artifacts per namespace/version
  - restores previous artifacts for namespaces that could not be refreshed
  - restores all previous artifacts if refresh has zero successful downloads
- Emits refresh metrics (discovered/processed/success/skipped/failed, deleted/restored counts, duration)

### `nutanix-mcp run`

- Performs startup readiness validation against Prism Central before loading tools
- Fails fast on auth, TLS, connectivity, or endpoint probe failures
- Loads YAMLs from runtime `artifacts/` first
- Falls back to bundled `src/artifacts/default_specs/`
- Parses GET operations, registers namespace execute tools, and wires progressive discovery dispatch
- If `PC_HOST` is not set, runs in artifact-only offline mode (discovery still works; live API execution requires `PC_HOST`)

## Tool contract

- Runtime exposes namespace execution tools in the form `<namespace>_execute`
- Each namespace tool uses a compact description and an explicit `operation` selector
- Operation and request field validation is deterministic (no fuzzy server-side matching)

## Progressive discovery helpers

- `listOperations`: lightweight operation catalog with namespace/search filters
- `getOperationSchema`: on-demand full schema payload for a selected operation
- `getCodeSample`: language-specific sample retrieval when provided in OpenAPI extensions

## Validation coverage

- Integration tests validate dispatcher tool registration and `listOperations` discovery roundtrips from loaded YAML artifacts.

## License

Apache 2.0
