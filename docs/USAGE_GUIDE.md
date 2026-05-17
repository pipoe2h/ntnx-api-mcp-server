# Usage Guide

This guide covers local setup, artifact fetch workflow, and stdio integration for the Nutanix V4 MCP server.

## 1) Install Locally

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2) Configure Environment

Create `.env` with the keys you need:

- Required for live API execution: `PC_HOST`, `PC_PORT`, `PC_USERNAME`, `PC_PASSWORD`
- Optional: `PC_INSECURE`, `ARTIFACTS_DIR`, `LOG_LEVEL`, `LOG_FORMAT`
- Optional discovery overrides: `NAMESPACE_SOURCE_URL`, `NAMESPACE_OVERRIDE_LIST`

## 3) Choose Artifact Mode

The server supports two fetch modes:

- `pc_compatible`: set `PC_HOST`; versions are probed from your Prism Central.
- `latest_release`: leave `PC_HOST` unset; versions come from developers namespace releases.

Run:

```bash
nutanix-mcp init
```

You should see `artifact_mode` in output and downloaded files under `artifacts/`.

## 4) Refresh Safely

```bash
nutanix-mcp refresh --force
```

Refresh uses backup/restore logic to keep previous artifacts if a namespace refresh fails.

## 5) Start MCP Stdio Server

```bash
nutanix-mcp serve-stdio
```

- stdout: MCP protocol frames
- stderr: operational logs

Stop server with `Ctrl+C`.

## 6) Verify in MCP Inspector (Browser)

In the inspector UI, configure server command as:

- Command: `/absolute/path/to/repo/.venv/bin/nutanix-mcp`
- Args: `serve-stdio`

Then connect and validate:

1. Run `List Tools`
2. Call `listOperations` with:

```json
{"namespace":"prism"}
```

3. Pick an operation and call `getOperationSchema`:

```json
{"operation":"<operationId>"}
```

## 7) Cursor/Claude MCP Config Example

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/to/repo/.venv/bin/nutanix-mcp",
      "args": [
        "serve-stdio"
      ],
      "env": {
        "ARTIFACTS_DIR": "/absolute/path/to/repo/artifacts",
        "PC_HOST": "10.10.10.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "********",
        "PC_INSECURE": "true"
      }
    }
  }
}
```

## 8) Troubleshooting

- `No YAML artifacts found...`: run `nutanix-mcp init`.
- `discovered: 0`: set `NAMESPACE_OVERRIDE_LIST` explicitly.
- Startup auth/connectivity errors: verify `PC_HOST`, credentials, and `PC_INSECURE`.
- Inspector parse errors: make sure command is exactly `serve-stdio` and no wrapper command prints extra stdout.

## 9) Manual End-to-End Checklist

Run this checklist before pushing PR branches:

1. `nutanix-mcp init` completes and reports `artifact_mode`.
2. `nutanix-mcp run --validate-only` shows expected mode:
   - with `PC_HOST`: `pc_compatible`
   - without `PC_HOST`: `latest_release`
3. `nutanix-mcp serve-stdio` starts and stays active.
4. MCP Inspector can:
   - list tools
   - call `listOperations`
   - call `getOperationSchema`
5. For connected mode, execute at least one safe read operation (for example a list/get API) via `<namespace>_execute`.
