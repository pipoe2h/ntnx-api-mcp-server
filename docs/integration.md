# Integration — Nutanix V4 API MCP Server

Connect your AI client to the Nutanix V4 API MCP Server. Each section below is self-contained. Read only the section for your client.

> New to MCP? See the [README](../README.md) for an overview of what this server does and how it works.

---

## Cursor

**Config file location:**
- macOS: `~/.cursor/mcp.json` (global) or `<workspace>/.cursor/mcp.json` (project-scoped)
- Windows: `%APPDATA%\Cursor\mcp.json`
- Linux: `~/.cursor/mcp.json`

Open the config file and add the `nutanix-v4-mcp` entry inside `"mcpServers"`. Create the file if it does not exist.

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "true",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

Replace `/absolute/path/.venv/bin/nutanix-mcp` with the absolute path to the `nutanix-mcp` binary inside your virtual environment. Use `which nutanix-mcp` (with the venv activated) to find it.

To authenticate with an API key instead of username/password, replace `PC_USERNAME` and `PC_PASSWORD` with a single `PC_API_KEY` key:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_API_KEY": "your-api-key",
        "PC_INSECURE": "true",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

**Verification:**

1. Save the config file.
2. Open Cursor → **Settings** → **MCP** (or press `Cmd+Shift+P` and search "MCP").
3. The server list should show `nutanix-v4-mcp` with a green status indicator.
4. In any Composer or Chat session, the server name appears as **`nutanix-v4-mcp-server`** in the tool list. You should see tools including `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and one `*_execute` tool per downloaded namespace (e.g. `prism_execute`, `lifecycle_execute`).
5. Ask the agent: _"List available Nutanix operations"_ — it should call `listOperations` and return results.

**Client-specific notes:**

- Cursor requires an **absolute path** for `command`. A relative path or bare `nutanix-mcp` will fail silently if the binary is not on Cursor's `PATH`.
- The project-scoped config (`<workspace>/.cursor/mcp.json`) takes precedence over the global config for that workspace. If the server appears twice, check both locations.
- After editing the config file, reload MCP servers from **Settings → MCP → Reload** rather than restarting Cursor entirely.
- Artifacts must be downloaded before Cursor launches the server. Run `nutanix-mcp init` in your terminal once before adding the config. If `ARTIFACTS_DIR` is empty, the server process starts but immediately exits with `RuntimeError: No YAML artifacts found`, and Cursor will show the server as disconnected.

---

## Claude Desktop

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: not applicable — Claude Desktop does not have a supported Linux release

Open the config file and add the `nutanix-v4-mcp` entry inside `"mcpServers"`. Create the file if it does not exist.

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "true",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

To authenticate with an API key instead of username/password, replace `PC_USERNAME` and `PC_PASSWORD` with a single `PC_API_KEY` key:

```json
{
  "mcpServers": {
    "nutanix-v4-mcp": {
      "command": "/absolute/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": {
        "PC_HOST": "10.1.1.10",
        "PC_PORT": "9440",
        "PC_API_KEY": "your-api-key",
        "PC_INSECURE": "true",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

**Verification:**

1. Save the config file.
2. **Exit completely and relaunch** Claude Desktop — it only reads the config on startup.
3. Open a new conversation. Click the **hammer icon** (tools) in the message composer.
4. The tool list should include `nutanix-v4-mcp-server` as a connected server with tools `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and namespace executor tools (e.g. `prism_execute`).
5. Ask: _"List available Nutanix operations"_ — Claude should invoke `listOperations`.

**Client-specific notes:**

- Claude Desktop requires a **full restart** (exit completely, not just close the window) to pick up config changes. Reload is not available.
- On macOS, `~/Library/Application Support/` is hidden in Finder. Use `Cmd+Shift+G` in Finder or `open ~/Library/Application\ Support/Claude/` in Terminal.
- The `command` path must be absolute. If you installed into a system Python or pyenv environment, confirm the exact path with `which nutanix-mcp` while that environment is active.

---

## MCP Inspector

MCP Inspector is a browser-based debugging tool for MCP servers. It does not require a config file — the server is launched directly from the command line.

Run this command from the project root with your virtual environment activated:

```bash
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

Pass credentials as environment variables before the command:

```bash
PC_HOST=10.1.1.10 \
PC_USERNAME=admin \
PC_PASSWORD=your_password \
PC_INSECURE=true \
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

**Verification:**

1. Inspector opens at `http://localhost:5173`.
2. The **Server** panel shows connection status. A green indicator means the stdio handshake completed.
3. Click **Tools** — you should see all registered tools: `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and namespace executor tools.
4. Select `listOperations`, click **Run** with no arguments — results appear in the response panel.

---

## Custom API clients

The server communicates exclusively over **stdio** (standard input / standard output). There is no HTTP port, no SSE endpoint, and no REST API surface exposed by the server process itself. All MCP communication happens through JSON-RPC messages on stdin/stdout per the [MCP specification](https://spec.modelcontextprotocol.io).

To call the server programmatically, launch it as a subprocess and communicate using the MCP stdio transport. The example below uses the Python `mcp` SDK:

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="/absolute/path/.venv/bin/nutanix-mcp",
    args=["serve-stdio"],
    env={
        "PC_HOST": "10.1.1.10",
        "PC_USERNAME": "admin",
        "PC_PASSWORD": "your_password",
        "PC_INSECURE": "true",
    },
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List all available operations
            result = await session.call_tool("listOperations", {})
            print(json.dumps(result.content[0].text, indent=2))

asyncio.run(main())
```

Install the SDK with `pip install mcp`. The `mcp` package is already a dependency of this server and will be present in the same virtual environment.

---

## Multi-cluster setup

Connecting to multiple Prism Central clusters simultaneously is not yet supported. Each server process is bound to a single `PC_HOST` value for its lifetime. Hot-reload of connection settings without restart is also not implemented.

Multi-cluster support is planned for a future release.

---

## Connection troubleshooting

### Server process exits immediately on client startup

**Symptom:** The AI client shows the server as disconnected immediately after attempting to connect; no tools appear.

**Cause:** No artifacts are present in `ARTIFACTS_DIR`. The server exits with `RuntimeError: No YAML artifacts found in runtime or bundled directories.`

**Fix:** Run `nutanix-mcp init` once before configuring the client. Confirm `ARTIFACTS_DIR` in the client config matches the directory where `init` wrote files.

---

### Tool calls return `execution_error` with a connection message

**Symptom:** Discovery tools (`listOperations`, etc.) work, but namespace executor tools return `{"ok": false, "error": {"code": "execution_error", "detail": "..."}}` mentioning a connection refused or timeout.

**Cause:** `PC_HOST` is unreachable from the machine running the server — firewall, VPN, or wrong IP.

**Fix:** Verify connectivity with `curl -k https://10.1.1.10:9440/api` from the same machine. Correct `PC_HOST` in the client config and restart the server.

---

### Tool calls return `execution_error` with HTTP 401 or 403

**Symptom:** The server starts and tools appear, but all `_execute` calls fail with an HTTP 401 or 403 error in the detail field.

**Cause:** Credentials in `PC_USERNAME`/`PC_PASSWORD` or `PC_API_KEY` are wrong or the account lacks permission.

**Fix:** Validate credentials by running `nutanix-mcp run --validate-only` in a terminal with the same environment variables set. If validation fails, update the credentials in the client config and restart the server. For permission requirements: [authentication and security guide](authentication.md).

---

### TLS handshake error on startup

**Symptom:** The startup probe fails with `TLS validation failed during startup probe. Check certificate trust or PC_INSECURE setting.`

**Cause:** `PC_INSECURE` is set to `false` and the Prism Central certificate is self-signed or issued by a CA not trusted by the system.

**Fix:** Set `PC_INSECURE=true` in the client config `env` block to disable certificate verification. For production environments, install the Prism Central CA certificate into the system trust store and keep `PC_INSECURE=false`. Custom CA bundle paths are not supported. Support for a configurable CA bundle path is planned for a future release.

---

### Server binary not found — client reports spawn error

**Symptom:** The client logs show a spawn or file-not-found error; the server never starts.

**Cause:** The `command` path in the config points to a non-existent location, or a relative path was used.

**Fix:** Use the absolute path to the `nutanix-mcp` binary. With your virtual environment activated, run `which nutanix-mcp` to get the exact path and paste it as the `command` value. On Windows, use `where nutanix-mcp` and ensure backslashes are escaped (`\\`) or use forward slashes in JSON.

---

More issues: [troubleshooting guide](troubleshooting.md).
