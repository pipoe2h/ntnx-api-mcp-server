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

### Required keys

Provide the following values through one of the supported sources:

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

- Clears existing `*-all-documentation.yaml` files from artifacts directory
- Re-runs the same namespace/version download flow

### `nutanix-mcp run`

- Loads YAMLs from runtime `artifacts/` first
- Falls back to bundled `src/artifacts/default_specs/`
- Parses GET operations and builds namespace execute tool schemas

## License

Apache 2.0
