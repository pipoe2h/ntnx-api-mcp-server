# Quickstart — Nutanix V4 API MCP Server

---

## Prerequisites

| Requirement | Value |
|---|---|
| Nutanix Prism Central version | Valid Prism Central version which supports any v4 APIs |
| Credentials | PC username + password **or** a PC API key |
| Python | `>= 3.11` |
| AI client | Claude Desktop **or** Cursor |
| Network | Machine running the server must reach `<PC_HOST>:9440` |

---

## Step 1: Install the server

```bash
git clone https://github.com/nutanix-core/ntnx-api-mcp-server.git
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Windows:** replace `source .venv/bin/activate` with `.venv\Scripts\activate`

Confirm the CLI is on your PATH:

```bash
nutanix-mcp --help
```

---

## Step 2: Configure credentials

Create a `.env` file in the project root. Copy the block below and fill in your values:

```bash
# Required
PC_HOST=your-pc.example.com
PC_PORT=9440

# Choose one auth method:
PC_USERNAME=your-username
PC_PASSWORD=your-password

# — OR —
PC_API_KEY=your-api-key

# TLS (set to false if your PC has a trusted certificate)
PC_INSECURE=true
```

Required variables summary:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `PC_HOST` | Yes | — | Prism Central IP or FQDN |
| `PC_PORT` | No | `9440` | |
| `PC_USERNAME` | One of `PC_USERNAME` or `PC_API_KEY` | — | |
| `PC_PASSWORD` | Required when `PC_USERNAME` set | — | |
| `PC_API_KEY` | One of `PC_USERNAME` or `PC_API_KEY` | — | Sent as `X-ntnx-api-key` header |
| `PC_INSECURE` | No | `true` | Set `false` to enable TLS verification |

For all configuration options: [configuration reference](configuration.md).

---

## Step 3: Download API artifacts and validate

Download OpenAPI specs from your Prism Central:

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
  "success": 4,
  "skipped": 15,
  "failed": 0,
  "duration_ms": 1234
}
```

Validate your configuration:

```bash
nutanix-mcp run --validate-only
```

Expected output (successful):

```json
{
  "pc_host": "your-pc.example.com",
  "pc_port": 9440,
  "pc_username": "your-username",
  "pc_api_key": null,
  "pc_insecure": true,
  "log_level": "INFO",
  "log_format": "text",
  "artifact_mode": "pc_compatible"
}
```

If you see `"startup_ready": false` with an `"error"` key, fix the reported issue before proceeding. For error details: [troubleshooting guide](troubleshooting.md).

> The MCP server (`nutanix-mcp serve-stdio`) is launched automatically by your AI client in steps 4 and 5 — do not run it manually here.

---

## Step 4: Connect Claude Desktop

Config file location:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Open the file (create it if absent) and paste this JSON:

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

Replace `/absolute/path/` with the real path. To find it:

```bash
pwd               # prints the project root
which nutanix-mcp # prints the full path to the binary
```

Verify it worked:

1. Exit completely and relaunch Claude Desktop.
2. Open a new conversation.
3. Look for a hammer icon or "Tools" indicator in the input area — this confirms MCP is connected.
4. Type: `List available Nutanix tools` — Claude should respond by calling `listOperations` and returning a list of operations.

If tools do not appear, see the [AI client integration section in the troubleshooting guide](troubleshooting.md#ai-client-integration).

---

## Step 5: Connect Cursor

Config file location:

| Scope | Path |
|---|---|
| Global (macOS / Linux) | `~/.cursor/mcp.json` |
| Workspace-only | `<your-project>/.cursor/mcp.json` |
| Windows (global) | `%APPDATA%\Cursor\mcp.json` |

Paste the same JSON block as step 4:

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

Verify it worked:

1. Open Cursor Settings → MCP (or reload the window with `Cmd+Shift+P` → `Reload Window`).
2. The `nutanix-v4-mcp` server should appear with a green status dot.
3. Open a Composer/Agent chat and type: `List available Nutanix tools` — Cursor should invoke `listOperations` and return a list of operations.

If the server does not appear, see the [AI client integration section in the troubleshooting guide](troubleshooting.md#ai-client-integration).

---

## Step 6: Run your first prompts

Type these prompts into your AI client. The AI resolves which tool to call.

---

### Prompt 1 — VM namespace

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

> `extId` is the Nutanix V4 API unique identifier for each resource — a UUID string used to reference specific objects in subsequent operations.

> If the AI reports `unknown_namespace: vmm`, your PC did not serve vmm artifacts during `init`. Re-run `nutanix-mcp init` while connected to PC, or check that vmm operations were downloaded.

---

### Prompt 2 — Data protection namespace

```
Show me the 5 most recent recovery points available in Nutanix.
```

The AI calls `dataprotection_execute` with operation `listRecoveryPoints` and `_limit: 5`.

Expected response shape:

```json
{
  "ok": true,
  "tool": "dataprotection_execute",
  "payload": {
    "data": [
      {
        "extId": "...",
        "creationTime": "...",
        "expirationTime": "..."
      }
    ]
  },
  "error": null
}
```

---

### Prompt 3 — Prism namespace

```
List the 5 most recent tasks running on Prism Central.
```

The AI calls `prism_execute` with operation `listTasks` and `_limit: 5`.

Expected response shape:

```json
{
  "ok": true,
  "tool": "prism_execute",
  "payload": {
    "data": [
      {
        "extId": "...",
        "operationType": "...",
        "status": "SUCCEEDED"
      }
    ]
  },
  "error": null
}
```

---

## What next

| Topic | Link |
|---|---|
| All supported AI clients | [integration guide](integration.md) |
| All configuration options | [configuration reference](configuration.md) |
| Something not working | [troubleshooting guide](troubleshooting.md) |
