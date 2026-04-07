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
- `LOG_LEVEL` (optional, default: `INFO`)
- `LOG_FORMAT` (optional: `text` or `json`)

### Precedence

When multiple sources are used together:

1. `.env` and process environment
2. Config file (`--config-file`)
3. CLI flags

## License

Apache 2.0
