# ntnx-api-mcp-server

Nutanix V4 API MCP server for local stdio clients such as Cursor, Claude, and MCP Inspector.

## Requirements

- Python 3.11+
- Prism Central access for live API execution (`PC_HOST`, credentials)

## Runtime Model

This server is distributed as a local Python package and used through stdio.

- `init` / `refresh` download API YAML artifacts into `artifacts/`
- `serve-stdio` starts the MCP runtime for agent clients
- `run` provides startup validation and artifact summary checks

### Artifact Modes

- `pc_compatible`: `PC_HOST` is configured; namespace versions are probed from Prism Central.
- `latest_release`: `PC_HOST` is not configured; latest namespace versions are pulled from developers endpoints.

## Configuration

Settings are loaded in this precedence order:

1. Environment / `.env`
2. Config file via `--config-file` (`.json`, `.yaml/.yml`, `.toml`)
3. CLI flags

Common keys:

- `PC_HOST`, `PC_PORT`, `PC_USERNAME`, `PC_PASSWORD`, `PC_INSECURE`
- `ARTIFACTS_DIR`
- `LOG_LEVEL`, `LOG_FORMAT`
- `NAMESPACE_SOURCE_URL`, `NAMESPACE_OVERRIDE_LIST`

## Commands

### `nutanix-mcp init`

Downloads artifacts for discovered namespaces and writes a summary JSON payload.

### `nutanix-mcp refresh --force`

Refreshes artifacts with backup/restore behavior to avoid breaking existing local discovery.

### `nutanix-mcp run [--validate-only]`

Performs startup checks and reports artifact loading state.

### `nutanix-mcp serve-stdio`

Runs the long-lived MCP stdio server. Use this command in MCP client configuration.

## Local Quick Start

1. Create and activate a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install package in editable mode:
   - `pip install -e .`
3. Prepare `.env` (with or without `PC_HOST`).
4. Download artifacts:
   - `nutanix-mcp init`
5. Optionally verify startup mode:
   - `nutanix-mcp run --validate-only`
6. Start server:
   - `nutanix-mcp serve-stdio`

## MCP Client Example

Use your local virtual environment command and pass `serve-stdio`:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/to/repo/.venv/bin/nutanix-mcp",
      "args": [
        "serve-stdio"
      ],
      "env": {
        "PC_HOST": "10.10.10.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "********",
        "PC_INSECURE": "true",
        "ARTIFACTS_DIR": "/absolute/path/to/repo/artifacts"
      }
    }
  }
}
```

## Discovery and Execution Tools

- Namespace executor tools: `<namespace>_execute`
- Discovery helpers:
  - `listOperations`
  - `getOperationSchema`
  - `getCodeSample`

## License

Apache 2.0

## Additional Docs

- `docs/USAGE_GUIDE.md` for local setup, inspector testing, and troubleshooting.
