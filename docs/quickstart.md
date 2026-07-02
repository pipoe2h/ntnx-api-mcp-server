# Quickstart — Nutanix V4 API MCP Server

The server runs in two modes depending on how you intend to use it. Read the section that matches your use case — steps are repeated in each so you do not need to cross-reference.

- **Standalone** — you start the server process yourself. Used for MCP Inspector, custom scripts, or programmatic clients.
- **AI client (Cursor / Claude Desktop)** — the AI client starts the server automatically using a config file. Used for interactive natural-language workflows.

---

## Prerequisites

| Requirement | Value |
|---|---|
| Nutanix Prism Central | Any version that exposes V4 APIs |
| Credentials | PC username + password **or** a PC API key |
| Python | `>= 3.11` |
| Network | Machine running the server must reach `<PC_HOST>:9440` |

---

## Part 1 — Standalone mode

Use this path if you want to run the server as a background process and connect to it with MCP Inspector, a custom Python client, or any other stdio-based MCP consumer.

### 1.1 Install

```bash
git clone https://github.com/nutanix/ntnx-api-mcp-server.git
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
```

> **pip version:** pip 24 or later is required. Upgrade if needed: `pip install --upgrade pip`

Confirm the CLI is available:

```bash
nutanix-mcp --help
```

---

### 1.2 Configure credentials

Move the example config to `.env` and fill in your values:

```bash
mv .env.example .env
```

Or create `.env` manually:

```bash
# Required
PC_HOST=your-pc.example.com
PC_PORT=9440

# Choose EXACTLY ONE auth method — do not set both:
PC_USERNAME=your-username
PC_PASSWORD=your-password

# — OR —
PC_API_KEY=your-api-key

# TLS — set to true only for dev/lab with self-signed certificates (default: false)
PC_INSECURE=false
```

> **Auth rule:** Set `PC_USERNAME` + `PC_PASSWORD` **or** `PC_API_KEY`. Setting both is allowed but `PC_API_KEY` takes priority and basic auth is ignored.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `PC_HOST` | Yes | — | Prism Central IP or FQDN |
| `PC_PORT` | No | `9440` | |
| `PC_USERNAME` | One auth method only | — | |
| `PC_PASSWORD` | Required when `PC_USERNAME` set | — | |
| `PC_API_KEY` | One auth method only | — | Sent as `X-ntnx-api-key` header |
| `PC_INSECURE` | No | `false` | Set `true` only for dev/lab with self-signed certificates |
| `READ_ONLY_MODE` | No | `true` | Blocks all non-GET operations server-side by default; set `false` to opt in to write operations |

---

### 1.3 Download API artifacts

Download OpenAPI specs from your Prism Central. Artifacts are stored locally and loaded on server start.

```bash
nutanix-mcp init
```

Expected output:

```json
{
  "mode": "init",
  "artifact_mode": "pc_compatible",
  "discovered": 19,
  "processed": 19,
  "success": 15,
  "skipped": 1,
  "not_available": 3,
  "failed": 0,
  "skipped_reasons": { "not_found": 1 },
  "not_available_reasons": { "http_503": 3 },
  "failed_reasons": {},
  "duration_ms": 1234
}
```

`not_available` counts namespaces whose services are not deployed on this Prism Central instance — this is expected and varies by PC configuration. Only `failed > 0` indicates a genuine problem (network error, parse failure).

Optionally, validate connectivity before starting the server:

```bash
nutanix-mcp run --validate-only
```

---

### 1.4 Start the server

With the virtual environment active and `.env` present in the project root:

```bash
nutanix-mcp serve-stdio
```

The server reads `stdin` and writes `stdout` using the MCP stdio transport. It does not open a TCP port. Connect your client to this process over stdio.

To pass credentials inline instead of via `.env`:

```bash
PC_HOST=10.1.1.10 PC_USERNAME=admin PC_PASSWORD=Admin1234! PC_INSECURE=false nutanix-mcp serve-stdio
```

**MCP Inspector (browser-based debugging tool):**

```bash
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

Or with inline credentials:

```bash
PC_HOST=10.1.1.10 PC_USERNAME=admin PC_PASSWORD=Admin1234! PC_INSECURE=false \
npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

Inspector opens at `http://localhost:5173`. Click **Tools** — you should see `listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`, and namespace executor tools.

---

## Part 2 — AI client mode (Cursor / Claude Desktop)

Use this path to connect Cursor or Claude Desktop. The AI client spawns the server process automatically when it reads the config file — you never run `serve-stdio` yourself.

> **Do not run `nutanix-mcp serve-stdio` manually.** The client launches the server via the config in steps 2.4 and 2.5. Running it separately creates a duplicate process and causes a handshake failure.

### 2.1 Install

```bash
git clone https://github.com/nutanix/ntnx-api-mcp-server.git
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
```

> **pip version:** pip 24 or later is required. Upgrade if needed: `pip install --upgrade pip`

Confirm the CLI is available:

```bash
nutanix-mcp --help
```

---

### 2.2 Configure credentials for init

Create `.env` in the project root — this is used by `nutanix-mcp init` (run manually, next step). At runtime the AI client config supplies credentials directly; see step 2.4.

```bash
mv .env.example .env
```

Minimum required content:

```bash
PC_HOST=your-pc.example.com
PC_PORT=9440
PC_USERNAME=your-username   # or PC_API_KEY=your-api-key
PC_PASSWORD=your-password
PC_INSECURE=false
```

> If your Prism Central uses a self-signed certificate (common in lab deployments), set `PC_INSECURE=true`. Keep it `false` for production.

---

### 2.3 Download API artifacts

```bash
nutanix-mcp init
```

This contacts Prism Central once to download OpenAPI specs into the `artifacts/` directory. The AI client reads these artifacts when it starts the server. Run this command whenever you switch to a different Prism Central instance — see [Refreshing artifacts](#refreshing-artifacts-when-pc-changes).

---

### 2.4 Connect Claude Desktop

Config file location:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Open the file (create it if absent) and add the `nutanix-v4-mcp` entry inside `"mcpServers"`:

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
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

Both `command` and `ARTIFACTS_DIR` **must be absolute paths** — Claude Desktop does not resolve relative paths. Run these to get the values:

```bash
which nutanix-mcp   # use this for "command"
pwd                  # append /artifacts for ARTIFACTS_DIR
```

Verify it worked:

1. Exit and relaunch Claude Desktop.
2. Open a new conversation.
3. Look for a hammer icon or "Tools" indicator — this confirms MCP is connected.
4. Type: `List available Nutanix tools` — Claude should call `listOperations` and return a list.

If tools do not appear: [troubleshooting guide](troubleshooting.md#ai-client-integration).

---

### 2.5 Connect Cursor

Config file location:

| Scope | Path |
|---|---|
| Global (macOS / Linux) | `~/.cursor/mcp.json` |
| Workspace-only | `<your-project>/.cursor/mcp.json` |
| Windows (global) | `%APPDATA%\Cursor\mcp.json` |

Add the same entry:

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
        "PC_INSECURE": "false",
        "ARTIFACTS_DIR": "/absolute/path/artifacts"
      }
    }
  }
}
```

Verify it worked:

1. Open Cursor Settings → MCP (or `Cmd+Shift+P` → `Reload Window`).
2. The `nutanix-v4-mcp` server should show a green status dot.
3. Open an Agent chat and type: `List available Nutanix tools` — Cursor should invoke `listOperations`.

If the server does not appear: [troubleshooting guide](troubleshooting.md#ai-client-integration).

---

## Refreshing artifacts when PC changes

Artifacts are tied to the Prism Central instance they were downloaded from. If you change `PC_HOST` (different cluster IP, migrated instance, or lab environment swap), the existing artifacts may be incompatible. Refresh them before restarting the server.

1. Update `PC_HOST` in `.env` to the new IP or FQDN.
2. If using an AI client, also update `PC_HOST` in the client config (`mcp.json` or `claude_desktop_config.json`).
3. Run:
   ```bash
   nutanix-mcp refresh
   ```
   This clears the existing artifacts directory and re-downloads from the new PC. It is equivalent to deleting the `artifacts/` folder and running `init` again.
4. Restart the AI client (if in AI client mode) to pick up the new artifacts.

> **Do not reuse artifacts across different Prism Central instances.** API versions and available namespaces vary by PC version. Mismatched artifacts cause `unknown_operation` errors or silently missing namespaces.

---

## First prompts

Type these into your AI client (Part 2 mode). The AI resolves which tool to call automatically.

### VM list

```
List the first 5 virtual machines in my Nutanix cluster.
```

The AI calls `vmm_execute` with operation `listVms` and `_limit: 5`.

Expected response shape:

```json
{
  "ok": true,
  "tool": "vmm_execute",
  "payload": {
    "data": [
      {
        "extId": "...",
        "name": "...",
        "powerState": "ON"
      }
    ]
  },
  "error": null
}
```

### Recovery points

```
Show me the 5 most recent recovery points available in Nutanix.
```

The AI calls `dataprotection_execute` with operation `listRecoveryPoints` and `_limit: 5`.

### Recent tasks

```
List the 5 most recent tasks running on Prism Central.
```

The AI calls `prism_execute` with operation `listTasks` and `_limit: 5`.

---

## What next

| Topic | Link |
|---|---|
| All supported AI clients and custom clients | [integration guide](integration.md) |
| All configuration options | [configuration reference](configuration.md) |
| Something not working | [troubleshooting guide](troubleshooting.md) |
