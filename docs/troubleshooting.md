# Troubleshooting — Nutanix V4 API MCP Server

Every common failure mode, with exact error strings, root causes, and step-by-step fixes. Each section heading is written to be surfaced by search.

---

## Table of contents

- [Connection and network](#connection-and-network)
- [Authentication](#authentication)
- [Tool execution errors](#tool-execution-errors)
  - [The `unknown_operation` error](#the-unknown_operation-error)
  - [Other tool execution errors](#other-tool-execution-errors)
- [AI client integration](#ai-client-integration)
  - [Tools show as loading or "no MCP resources found"](#tools-show-as-loading-or-agent-reports-no-mcp-resources-found)
- [Configuration](#configuration)
- [Performance](#performance)
- [FAQ](#faq)

---

## Connection and network

---

### `Unable to connect to Prism Central at <host>:<port>`

**Symptom:** The `nutanix-mcp run` command prints:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Unable to connect to Prism Central at 10.1.1.10:9440."
}
```

**Cause:** The server cannot establish a TCP connection to `PC_HOST:PC_PORT`. The host is either unreachable (wrong IP, firewall, VPN not active) or the port is wrong.

**Fix:**
1. Confirm you can reach the host from your machine:
   ```bash
   ping 10.1.1.10
   curl -k https://10.1.1.10:9440/api/prism/v4.0/config/cluster -u admin:password
   ```
2. Verify `PC_HOST` contains only the IP or FQDN — no `https://` prefix and no trailing slash.
3. Verify `PC_PORT` (default `9440`). If your cluster uses a different port, set it explicitly:
   ```bash
   export PC_PORT=9440
   ```
4. Check that your VPN or network route to the cluster is active.
5. Confirm no firewall blocks outbound connections to port `9440`.

---

### `Startup connectivity probe timed out for <host>:<port>`

**Symptom:** The `nutanix-mcp run` command prints:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Startup connectivity probe timed out for 10.1.1.10:9440."
}
```

**Cause:** A TCP connection was opened but Prism Central did not respond within 30 seconds (the hardcoded timeout). Common causes: very high cluster load, a middlebox intercepting the connection, or a long NAT traversal path.

**Fix:**
1. Check whether Prism Central is under heavy load (UI slow, other API calls slow).
2. Try the probe manually to see if it times out consistently:
   ```bash
   curl -k --max-time 30 -X OPTIONS https://10.1.1.10:9440/api/prism/v4.0 -u admin:password
   ```
3. The 30-second timeout is hardcoded in version `0.8` and cannot be changed via environment variable. Ensure Prism Central is reachable before starting the server.
4. When using `serve-stdio` (not `run`), the startup probe is skipped — the timeout only surfaces at the first tool call. The error detail will be `"execution_error"` containing `str(httpx.ConnectTimeout(...))`.

---

### `Startup connectivity probe read timed out for <host>:<port>`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Startup connectivity probe read timed out for 10.1.1.10:9440."
}
```

**Cause:** The TCP connection succeeded but Prism Central sent no data before the 30-second read deadline. Often caused by a proxy or load balancer that accepts the connection but delays forwarding.

**Fix:**
1. Check for any HTTP proxy or load balancer between your machine and Prism Central.
2. Test direct connectivity bypassing any proxy:
   ```bash
   curl -k --noproxy '*' --max-time 30 -X OPTIONS https://10.1.1.10:9440/api/prism/v4.0 -u admin:password
   ```
3. If a proxy is required, set `HTTP_PROXY` / `HTTPS_PROXY` environment variables before starting the server.

---

### `TLS validation failed during startup probe. Check certificate trust or PC_INSECURE setting.`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "TLS validation failed during startup probe. Check certificate trust or PC_INSECURE setting."
}
```

**Cause:** `PC_INSECURE` is set to `false` (TLS verification enabled) but the Prism Central TLS certificate cannot be verified — it is self-signed, expired, or issued by a CA not trusted by the system.

**Fix (development / trusted environment):**

Set `PC_INSECURE=true` to disable certificate verification:
```bash
export PC_INSECURE=true
nutanix-mcp run
```
Or in your `.env`:
```
PC_INSECURE=true
```

**Fix (production / verified environment):**

Do not disable TLS verification. Add the Prism Central CA certificate to your system trust store or to the Python `certifi` bundle:
```bash
# macOS
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /path/to/pc-ca.crt

# Linux
sudo cp /path/to/pc-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

`PC_INSECURE` defaults to `false`. For production clusters, keep the default and install the CA certificate into the system trust store. Custom CA bundle paths are not configurable; the server uses the system trust store via the `httpx` default.

---

### `Transport failure during startup probe.`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Transport failure during startup probe."
}
```

**Cause:** An unclassified transport-layer error occurred that did not match a TLS, connect, or timeout pattern.

**Fix:**
1. Enable debug logging to capture the underlying exception:
   ```bash
   nutanix-mcp --log-level DEBUG run
   ```
2. Inspect the log file at `logs/nutanix-mcp-<timestamp>.log` for the full exception chain.
3. Common underlying causes: SOCKS proxy misconfiguration, incorrect TLS protocol version, or `PC_HOST` resolving to a non-Prism-Central address.

---

### `Startup probe endpoint was not found on target Prism Central.`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Startup probe endpoint was not found on target Prism Central."
}
```

**Cause:** Prism Central responded with HTTP 404 on the probe endpoint. This usually means `PC_HOST` points to a non-PC host (e.g., Prism Element, a web server, or an old PC version that does not expose the V4 API path).

**Fix:**
1. Confirm `PC_HOST` is the Prism **Central** IP, not a node/Prism Element IP.
2. Confirm your Prism Central version supports the V4 API (PC 2023.1 or later required for most V4 namespaces).
3. Confirm the port is correct. Prism Central V4 APIs are served on port `9440`.

---

### `Unexpected network error during startup probe.`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Unexpected network error during startup probe."
}
```

**Cause:** An `httpx.NetworkError` was raised that is not a connect error, timeout, or transport error.

**Fix:**
1. Run with `--log-level DEBUG` to capture the full exception.
2. Check OS-level network configuration (DNS resolution, routing table).

---

## Authentication

Full role and permission table: [authentication and security guide](authentication.md)

---

### `No Prism Central auth configured. Provide PC_API_KEY or PC_USERNAME/PC_PASSWORD.`

**Symptom:** `nutanix-mcp run` exits immediately with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "No Prism Central auth configured. Provide PC_API_KEY or PC_USERNAME/PC_PASSWORD."
}
```

**Cause:** `PC_HOST` is set (so the server attempts to probe Prism Central) but neither `PC_USERNAME`/`PC_PASSWORD` nor `PC_API_KEY` is configured.

**Fix:**

Option A — Basic auth:
```bash
export PC_USERNAME=admin
export PC_PASSWORD=your_password
```

Option B — API key:
```bash
export PC_API_KEY=your-api-key
```

Or in `.env`:
```
PC_USERNAME=admin
PC_PASSWORD=your_password
```

If both `PC_USERNAME`/`PC_PASSWORD` and `PC_API_KEY` are set, `PC_API_KEY` takes priority — no error is raised.

---

### `Prism Central authentication failed during startup. Verify PC_API_KEY or PC_USERNAME/PC_PASSWORD permissions.`

**Symptom:** `nutanix-mcp run` exits with:
```json
{
  "mode": "run",
  "startup_ready": false,
  "error": "Prism Central authentication failed during startup. Verify PC_API_KEY or PC_USERNAME/PC_PASSWORD permissions."
}
```

**Cause:** Prism Central returned HTTP 401 (unauthenticated) or HTTP 403 (authorized but insufficient permissions) during the startup probe. Credentials are wrong, the account is locked, or the role lacks access to the probe endpoint.

**Fix:**
1. Verify your credentials work directly:
   ```bash
   curl -k -u admin:your_password -X OPTIONS https://10.1.1.10:9440/api/prism/v4.0
   ```
2. For API key: confirm the key is active in Prism Central → **Settings → API Keys**.
3. For basic auth: confirm the account exists, is not locked, and the password is correct.
4. The startup probe uses an OPTIONS request to `/api/prism/v4.0`. The minimum required role is any role that can authenticate to Prism Central — the probe does not require data-access permissions.
5. If credentials are correct but you still get 403, verify the account has at least the `Viewer` role in Prism Central.

---

### HTTP 401 / 403 from a tool call — authentication error

**Symptom:** An `_execute` tool call returns a sanitized auth error:
```json
{
  "ok": true,
  "tool": "vmm_execute",
  "payload": {
    "error": "Authentication failed. Verify PC_API_KEY or PC_USERNAME/PC_PASSWORD.",
    "hint": "Check credentials and Prism Central user permissions."
  },
  "error": null
}
```

The server sanitizes raw 401/403 responses from Prism Central — credential details are never returned to the AI client.

**Possible causes:** Credentials are wrong, the account is locked, or the account lacks permission for this specific API endpoint or namespace.

**Fix:**
1. Verify credentials work directly against Prism Central:
   ```bash
   # API key auth
   curl -k -H "X-ntnx-api-key: abc123def456" https://10.1.1.10:9440/api/prism/v4.0/config/cluster
   # Basic auth
   curl -k -u admin:Admin1234! https://10.1.1.10:9440/api/prism/v4.0/config/cluster
   ```
2. Use `getOperationPermissions` to check which roles the operation requires:
   ```
   getOperationPermissions(operation="listVms")
   ```
3. Compare the `required_roles` field against your account's roles in Prism Central.
4. For API key: confirm the key is active in Prism Central → **Settings → API Keys**.
5. Full role requirements per namespace: [authentication and security guide](authentication.md)

---


---

### Wrong credential format — API key sent as Basic auth or vice versa

**Symptom:** Authentication fails despite credentials appearing correct.

**Cause:** Setting both `PC_USERNAME` and `PC_API_KEY` to the same value, or confusing which variable to use.

**Fix:**
- `PC_API_KEY` is sent as the `X-ntnx-api-key` HTTP header.
- `PC_USERNAME` + `PC_PASSWORD` are sent as standard HTTP Basic auth (`Authorization: Basic <base64>`).
- Verify which method your Prism Central deployment supports. If unsure, use basic auth with the admin account.

```bash
# API key only
export PC_API_KEY=your-api-key
unset PC_USERNAME
unset PC_PASSWORD

# Basic auth only
export PC_USERNAME=admin
export PC_PASSWORD=your_password
unset PC_API_KEY
```

---

## Tool execution errors

---

## The `unknown_operation` error

> This is the single most common error when using the Nutanix V4 API MCP Server. Read this section before submitting a bug report.

**Symptom:** Any `_execute` tool call returns:
```json
{
  "ok": false,
  "tool": "vmm_execute",
  "payload": null,
  "error": {
    "code": "unknown_operation",
    "detail": "Unknown operation 'listVirtualMachines'."
  }
}
```

**Cause:** The AI client (or you, manually) passed an operation ID that does not exist in the loaded artifacts for that namespace. The most common cause is an AI model **guessing** an operation name instead of discovering it first.

The operation enum for each `_execute` tool is built at startup from the downloaded OpenAPI YAML files. If the name passed does not exactly match one of those IDs (case-sensitive), the call fails.

**Recovery steps — always resolve `unknown_operation` this way:**

**Step 1.** Call `listOperations` with a keyword to find the correct ID:
```
listOperations(search="virtual machine", namespace="vmm")
```
or without a namespace filter:
```
listOperations(search="vm")
```

**Step 2.** Identify the exact `operation` value from the results. For example:
```json
[
  {
    "namespace": "vmm",
    "operation": "listVms",
    "method": "GET",
    "path": "/vmm/v4.0/ahv/config/vms",
    "summary": "List VMs"
  }
]
```

**Step 3.** Call `getOperationSchema` to confirm the exact parameters:
```
getOperationSchema(operation="listVms")
```

**Step 4.** Re-invoke the `_execute` tool with the exact operation ID:
```
vmm_execute(operation="listVms", _limit=10)
```

The discovery-first pattern above is the only reliable way to resolve `unknown_operation` — always call `listOperations` before assuming an operation ID.

---

**Why does the AI guess instead of discover?**

The MCP server instructions field explicitly tells AI clients:

> *"Use listOperations/getOperationSchema/getCodeSample before executing operations."*

Some AI models attempt to infer operation names from their training data or from the tool's enum hint. The enum is the authoritative list — any name not in it will return `unknown_operation`. There is no fuzzy matching or suggestion system; the operation ID must be an exact string match.

---

**Preventing `unknown_operation` in automated workflows:**

Always call `listOperations` as the first step when writing agentic workflows that invoke Nutanix APIs. Do not hard-code operation IDs unless you have verified them against the current artifact set — operation IDs can change between PC versions when the artifact mode is `pc_compatible`.

---

### Other tool execution errors

### `unknown_namespace`

**Symptom:**
```json
{
  "ok": false,
  "tool": "files_execute",
  "error": {
    "code": "unknown_namespace",
    "detail": "Unknown namespace: files"
  }
}
```

**Cause:** The namespace `files` does not appear in the loaded artifacts. The `_execute` tool for a namespace is only registered if the corresponding YAML artifact was downloaded during `init`/`refresh`. The current server may have fewer than all 19 possible namespaces depending on your PC version and artifact download results.

**Fix:**
1. Check which namespaces are loaded:
   ```
   listOperations(limit=1)
   ```
   The response will list all operations with their namespaces.
2. If the namespace is missing, re-run artifact download. If `PC_HOST` is configured, the download picks version-compatible YAMLs:
   ```bash
   nutanix-mcp refresh --force
   ```
3. If the YAML download still skips the namespace, check the `init` output for `skipped_reasons`. A `not_found` reason means the Nutanix developer portal did not list a YAML for that namespace/version combination.

---

### `invalid_parameters` — unsupported request fields

**Symptom:**
```json
{
  "ok": false,
  "tool": "vmm_execute",
  "error": {
    "code": "invalid_parameters",
    "detail": "Unsupported request fields: clusterExtId, vmName"
  }
}
```

**Cause:** The AI client passed parameters that are not in the allowed set for this operation. Allowed parameters are: `operation`, `_page`, `_limit`, `_filter`, `_orderby`, `_select`, `_expand`, `request_body`, and any path/query/header parameters defined in the OpenAPI spec for that operation.

**Fix:**
1. Call `getOperationSchema` to inspect the exact parameters for the operation:
   ```
   getOperationSchema(operation="listVms")
   ```
2. Check the `parameters` array in the response — each entry has `name`, `location` (`path`, `query`, or `header`), and `required`.
3. Fields that go into the URL path or query string are passed as **top-level arguments** to the tool (e.g., `extId` for path operations).
4. The request body goes in the `request_body` object, not as top-level fields.

---

### `invalid_parameters` — `request_body must be an object when provided.`

**Symptom:**
```json
{
  "ok": false,
  "tool": "vmm_execute",
  "error": {
    "code": "invalid_parameters",
    "detail": "request_body must be an object when provided."
  }
}
```

**Cause:** `request_body` was passed as a string, array, or `null` instead of a JSON object.

**Fix:** Ensure `request_body` is always a JSON object (`{}`):
```json
{
  "operation": "createVm",
  "request_body": {
    "name": "my-vm",
    "numSockets": 2
  }
}
```

---

### Missing required path parameters: `<param>`

**Symptom:** Tool returns `execution_error` with detail:
```
Missing required path parameters: extId
```

**Cause:** The operation URL contains a path placeholder (e.g., `/vmm/v4.0/ahv/config/vms/{extId}`) but the corresponding parameter was not supplied in the tool call.

**Fix:**
1. Call `getOperationSchema` and inspect the `parameters` list for entries with `"location": "path"` and `"required": true`.
2. Pass the value as a top-level argument:
   ```json
   {
     "operation": "getVmById",
     "extId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   }
   ```

---

### `execution_error` — Nutanix API returned an error response

**Symptom:**
```json
{
  "ok": false,
  "tool": "vmm_execute",
  "error": {
    "code": "execution_error",
    "detail": "Client error '404 Not Found' for url 'https://10.1.1.10:9440/api/vmm/v4.0/ahv/config/vms/bad-uuid'"
  }
}
```

**Cause:** The Nutanix API returned an HTTP error (4xx/5xx). The `detail` field contains the raw `httpx` exception message. HTTP error responses that do not raise an httpx exception are returned as `payload` (not as `execution_error`); only network-level exceptions or connection failures produce `execution_error`.

**Fix:**
1. Inspect the `detail` field for the HTTP status and URL.
2. 404: the resource UUID does not exist or has been deleted.
3. 409 Conflict: the resource is in a state that does not allow this operation.
4. 500: internal Prism Central error — check Prism Central logs.
5. If the response body is returned as `payload` instead of an error, look for a `data.error` or `data.message` field inside the payload — Nutanix API errors are not translated into MCP error codes.

---

### Async operations — tool returns a task ID, not a result

**Symptom:** A POST/PUT/DELETE call returns a payload like:
```json
{
  "ok": true,
  "tool": "vmm_execute",
  "payload": {
    "data": {
      "extId": "ZXJnb24=:xxxxxxxx...",
      "status": "QUEUED"
    }
  }
}
```

**Cause:** Many Nutanix V4 write operations are asynchronous — the API returns a task object immediately. The MCP server does not poll for task completion; it returns the raw API response.

**Fix:**
1. Copy the `extId` from the task payload.
2. Use `prism_execute` to poll task status:
   ```
   listOperations(search="task", namespace="prism")
   ```
   Then call the appropriate task-get operation with the task `extId`.
3. Poll until `status` is `SUCCEEDED` or `FAILED`.
4. Version `0.8` has no built-in polling — this is a manual step.

---

## Installation

---

### `pip install` fails with dependency resolution errors

**Symptom:** Running `pip install -e .` produces errors like:

```
ERROR: Cannot install ntnx-api-mcp-server because these package versions have conflicting dependencies.
```

or:

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
```

**Cause:** pip version 21 and earlier use a legacy resolver that does not correctly handle complex dependency graphs. pip 24+ uses a stricter resolver that surfaces conflicts earlier and resolves them correctly.

**Fix:** Upgrade pip before installing:

```bash
pip install --upgrade pip
pip install -e .
```

Verify you have pip 24+:

```bash
pip --version
# Expected: pip 24.x or higher
```

If you are on a managed Python environment where upgrading pip system-wide is not possible, create a fresh virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

---

## AI client integration

---

### Tools show as loading or agent reports "no MCP resources found"

**Symptom:** Cursor or Claude shows the server as loading for 15–25 seconds, or the agent says it cannot find any Nutanix tools even though the server appears enabled in settings.

**Cause:** The server parses all downloaded OpenAPI YAML files synchronously during the MCP handshake. Depending on how many namespaces are loaded and the machine's I/O speed, this can take 15–25 seconds. If the AI client enforces a strict handshake timeout, it may give up before the tools are registered.

**Fix:**
1. Wait 20–30 seconds after toggling the server on before sending any queries. The server is ready once tools appear in the tool list.
2. Reduce the number of loaded namespaces by downloading only the ones you need:
   ```bash
   nutanix-mcp init   # only fetches namespaces your PC reports as available
   ```
   Removing unused YAML files from `ARTIFACTS_DIR` reduces parse time proportionally.
3. If the server still appears as disconnected after 30 seconds, check the server log for errors:
   ```bash
   ls -lt logs/ | head -5   # find the most recent log file
   ```

---

### Server not appearing in Cursor / Claude Desktop tool list

**Symptom:** After adding the server to your MCP client config, no Nutanix tools appear.

**Cause:** Most common causes: wrong path to the executable, missing `serve-stdio` argument, or a config file parse error.

**Fix:**

1. Verify the config block format exactly. For Cursor (`~/.cursor/mcp.json`):
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
   For Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`): same structure under `"mcpServers"`.

2. Use an **absolute path** for `command`. Relative paths are not resolved from the config file location.

3. Confirm the virtual environment is activated and the binary exists:
   ```bash
   ls -la /absolute/path/.venv/bin/nutanix-mcp
   ```

4. Test the command manually before adding it to the client:
   ```bash
   /absolute/path/.venv/bin/nutanix-mcp serve-stdio
   ```
   It should start silently (stdio mode — no output unless a tool is called).

5. Restart the AI client after changing the config file. Most clients do not hot-reload MCP configs.

---

### Server appears but no tools are listed

**Symptom:** The `nutanix-v4-mcp-server` entry is visible in the AI client but the tool list is empty or only discovery tools appear.

**Cause:** No YAML artifacts have been downloaded, so no namespace `_execute` tools were registered. The 4 discovery tools (`listOperations`, `getOperationSchema`, `getCodeSample`, `getOperationPermissions`) are always registered regardless of artifacts.

**Fix:**
1. Run `init` to download artifacts:
   ```bash
   nutanix-mcp init
   ```
   With `PC_HOST` set, this downloads version-compatible YAMLs from the Nutanix developer portal. Without `PC_HOST`, it downloads the latest release versions.
2. Verify artifacts were downloaded:
   ```bash
   ls artifacts/
   # Expected: dataprotection-v4.0-all-documentation.yaml, lifecycle-v4.0-all-documentation.yaml, ...
   ```
3. Restart the AI client so the server reloads with new artifacts.

---

### Server appears and tools are listed but every call returns an error

**Symptom:** Tools are visible and callable but all calls return `execution_error` immediately.

**Cause:** Connection or auth issue not caught at startup (because `serve-stdio` skips the startup probe).

**Fix:**
1. Run `nutanix-mcp run` to execute the full startup probe:
   ```bash
   nutanix-mcp run
   ```
   This will surface connectivity, TLS, and authentication errors before the server enters stdio mode.
2. Fix any errors reported (see [Connection and network](#connection-and-network) and [Authentication](#authentication) sections above).
3. Verify `PC_HOST` and credentials are passed in the `env` block of the client config — environment variables set in your shell are **not** automatically inherited by the AI client's subprocess.

---

### MCP Inspector: server connects but tool calls fail

**Symptom:** Tools are visible in MCP Inspector at `http://localhost:5173` but execution returns errors.

MCP Inspector does not forward environment variables from your shell. Pass them inline:
```bash
PC_HOST=10.1.1.10 PC_USERNAME=admin PC_PASSWORD=your_password PC_INSECURE=true \
  npx @modelcontextprotocol/inspector .venv/bin/nutanix-mcp serve-stdio
```

---

## Configuration

---

### `PC_HOST is required to build Prism Central base URL.`

**Symptom:** A tool call (not `listOperations` or other discovery tools) returns `execution_error` with:
```
PC_HOST is required to build Prism Central base URL.
```

**Cause:** `PC_HOST` was not set before calling an `_execute` tool. Discovery tools (`listOperations`, etc.) do not need `PC_HOST` and work without it. Only namespace `_execute` tools require a configured Prism Central host.

**Fix:**

Set `PC_HOST` in the `env` block of your client config (not just in your shell):
```json
"env": {
  "PC_HOST": "10.1.1.10"
}
```
Or as an environment variable before starting the server:
```bash
export PC_HOST=10.1.1.10
```

---

### `No YAML artifacts found in runtime or bundled directories.`

**Symptom:** `nutanix-mcp serve-stdio` or `nutanix-mcp run` crashes with:
```
RuntimeError: No YAML artifacts found in runtime or bundled directories. Checked: /path/to/artifacts and /path/to/src/artifacts/default_specs
```

**Cause:** No OpenAPI YAML artifacts have been downloaded and the `src/artifacts/default_specs/` fallback directory is empty. This happens when `nutanix-mcp init` was never run, or when `ARTIFACTS_DIR` points to an empty directory.

**Fix:**
```bash
nutanix-mcp init
```
This downloads YAML artifacts. With `PC_HOST` configured it downloads version-compatible specs; without `PC_HOST` it downloads latest-release specs.

If you receive `skipped` results (common with `success: 0`), the Nutanix developer portal did not expose YAMLs for your PC version. The artifacts bundled with the package should still be present in `src/artifacts/default_specs/`. If that directory is missing or empty in your installation, re-install:
```bash
pip install -e .
```

---

### `Settings file does not exist: <path>`

**Symptom:**
```
ValueError: Settings file does not exist: /path/to/config.toml
```

**Cause:** The path passed to `--config-file` does not exist.

**Fix:**
```bash
nutanix-mcp --config-file /correct/path/to/config.toml serve-stdio
```
Verify the file exists:
```bash
ls /correct/path/to/config.toml
```

---

### `Unsupported settings file extension. Use .json, .yaml/.yml, or .toml.`

**Symptom:**
```
ValueError: Unsupported settings file extension. Use .json, .yaml/.yml, or .toml.
```

**Cause:** `--config-file` points to a file with an unsupported extension (e.g., `.ini`, `.cfg`, `.conf`).

**Fix:** Convert your config to one of the supported formats. Example `config.toml`:
```toml
pc_host = "10.1.1.10"
pc_port = 9440
pc_username = "admin"
pc_password = "your_password"
pc_insecure = true
log_level = "INFO"
```

---

### Wrong `PC_HOST` URL format — includes `https://` or trailing slash

**Symptom:** Connection errors or mangled request URLs like `https://https://10.1.1.10:9440/api/...`.

**Cause:** `PC_HOST` was set to `https://10.1.1.10` or `10.1.1.10/` instead of just the IP/FQDN.

**Fix:**
```bash
# Wrong:
export PC_HOST=https://10.1.1.10
export PC_HOST=10.1.1.10/

# Correct:
export PC_HOST=10.1.1.10
```

The server builds the full URL internally as `https://{PC_HOST}:{PC_PORT}/api{path}`. `PC_HOST` must be a bare IP address or hostname only.

---

### `Artifacts directory is not writable: <path>`

**Symptom:**
```
ValueError: Artifacts directory is not writable: /custom/artifacts
```

**Cause:** The `ARTIFACTS_DIR` path exists but is not writable by the current user.

**Fix:**
```bash
chmod u+w /custom/artifacts
# or choose a different writable location:
export ARTIFACTS_DIR=/home/user/nutanix-artifacts
```

---

## Performance

---

### Slow tool call responses

**Symptom:** Every `_execute` tool call takes several seconds.

**Cause:** Each tool call opens a new HTTP connection to Prism Central — there is no connection pool in version `0.8`. Round-trip latency to your cluster directly impacts response time.

**Fix:**
1. Ensure the machine running the server has low network latency to Prism Central (same datacenter or VPN with low latency).
2. Use `_limit` to restrict result set size — large result sets take longer to transfer and serialise:
   ```json
   { "operation": "listVms", "_limit": 10 }
   ```
3. Use `_filter` to narrow results on the server side:
   ```json
   { "operation": "listVms", "_filter": "name eq 'my-vm'" }
   ```

---

### Suspected rate limiting from Prism Central

**Symptom:** Rapid successive tool calls start returning HTTP 429 or Prism Central becomes unresponsive.

**Cause:** Prism Central imposes its own rate limits on API requests. The MCP server does not implement client-side rate limiting in version `0.8`.

**Fix:**
1. Reduce call frequency — add delays between agentic workflow steps.
2. Check Prism Central rate limit settings in **Prism Central → Settings → API Rate Limiting** (if available in your version).
3. Use `_filter` and `_limit` to reduce the number of calls needed.

---

### Too many tools in AI client context window

**Symptom:** The AI client struggles with tool selection, returns errors about context length, or is slow to respond when all tools are listed.

**Cause:** With a full 19-namespace artifact set, up to 23 MCP tools are registered. Some AI clients pass all tool schemas in the system prompt, which consumes significant context.

**Fix:**
1. Use `NAMESPACE_OVERRIDE_LIST` to restrict which namespaces load tools:
   ```bash
   export NAMESPACE_OVERRIDE_LIST=vmm,prism
   ```
   This limits the loaded namespaces at artifact discovery time.
2. With only the namespaces you need, far fewer tools are registered.
3. Use `nutanix-mcp run` to verify how many tools are registered:
   ```bash
   nutanix-mcp run
   # Look for "registered_tool_count" in the output
   ```

---

### `listOperations` returns no results for a keyword search

**Symptom:** `listOperations(search="snapshots")` returns an empty list.

**Cause:** The search is a case-insensitive substring match across `operation_id`, `path`, `summary`, and `description`. If no loaded operation contains the keyword in any of those fields, the result is empty. The searched namespace may not be loaded, or the keyword may not match the OpenAPI terminology.

**Fix:**
1. Try a broader search term — e.g., `"snapshot"` instead of `"snapshots"`.
2. Confirm the namespace is loaded:
   ```
   listOperations(namespace="dataprotection", limit=5)
   ```
3. If the namespace is missing, run `nutanix-mcp refresh --force`.

---

## FAQ

<details>
<summary><strong>What Nutanix / Prism Central versions are supported?</strong></summary>

The server targets **Prism Central V4 APIs**. When `PC_HOST` is configured, `nutanix-mcp init` downloads YAML artifacts version-matched to your PC's deployed API versions (`pc_compatible` mode). Without `PC_HOST`, it downloads the latest published API specs (`latest_release` mode).

No specific minimum PC version is enforced in the code. In practice, Prism Central versions shipping V4 APIs (PC 2023.1 / AOS 6.5 and later) should work. Prism Element is not supported — all API paths are Prism Central endpoints.

If your PC version is too old to have V4 API YAMLs published on the Nutanix developer portal, `init` will report `skipped: N` with `skipped_reasons: {"not_found": N}`.

</details>

<details>
<summary><strong>Does this work with Nutanix Community Edition?</strong></summary>

Community Edition (CE) includes a limited set of Nutanix services and may not expose all V4 API namespaces. The MCP server will work for namespaces that CE does expose (typically `vmm`, `storage`, `clustermgmt`). Namespaces like `dataprotection` or `files` may return errors if those services are not running on CE.

Run `nutanix-mcp init` with `PC_HOST` pointing to your CE cluster to discover which namespaces are available. Check the `success` and `skipped_reasons` fields in the output.

</details>

<details>
<summary><strong>Can I connect to multiple clusters simultaneously?</strong></summary>

No. Version `0.8` supports a single `PC_HOST` per server process. Each server instance connects to exactly 1 Prism Central.

To work with multiple clusters, run a separate server process for each cluster with different `PC_HOST` values, and register each as a separate MCP server entry in your client config:
```json
{
  "mcpServers": {
    "nutanix-cluster-a": {
      "command": "/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": { "PC_HOST": "10.1.1.10", "PC_USERNAME": "admin", "PC_PASSWORD": "pass_a" }
    },
    "nutanix-cluster-b": {
      "command": "/path/.venv/bin/nutanix-mcp",
      "args": ["serve-stdio"],
      "env": { "PC_HOST": "10.2.2.20", "PC_USERNAME": "admin", "PC_PASSWORD": "pass_b" }
    }
  }
}
```

</details>

<details>
<summary><strong>Are my Nutanix credentials stored by the AI client?</strong></summary>

No. The AI client (Cursor, Claude Desktop) passes credentials to the MCP server process via the `env` block in its config file. The credentials live in that config file on your local disk. The AI client does not transmit credentials to any external service.

Within the server process, `PC_PASSWORD` and `PC_API_KEY` are stored as Pydantic `SecretStr` fields — they are masked in log output as `**********` and are only decrypted at request-build time.

Running `nutanix-mcp init` or `nutanix-mcp refresh` writes credentials in plaintext to a `.env` file in the current working directory. Ensure this `.env` file is not committed to version control (it is gitignored by default). For security guidance: [authentication and security guide](authentication.md).

</details>

<details>
<summary><strong>Which operations are read-only vs destructive?</strong></summary>

`READ_ONLY_MODE` defaults to `true` — all non-GET operations are blocked server-side by default. To allow write operations, set `READ_ONLY_MODE=false` in your `.env` or client config `env` block.

- **Read-only operations:** All HTTP GET operations (107 in the current default artifact set).
- **Destructive operations:** HTTP POST (create), PUT (replace), PATCH (update), DELETE (destroy).

Use `getOperationSchema` to check the `method` field before calling an unfamiliar operation.

To further reduce risk in production, restrict which namespaces load by setting `NAMESPACE_OVERRIDE_LIST` to only the namespaces you need, and use a Viewer-role Prism Central account for RBAC-level enforcement.

</details>

<details>
<summary><strong>How do I enable debug logging?</strong></summary>

**Via CLI flag (recommended for one-off debugging):**
```bash
nutanix-mcp --log-level DEBUG serve-stdio
```

**Via environment variable:**
```bash
export LOG_LEVEL=DEBUG
nutanix-mcp serve-stdio
```

**Via config file:**
```toml
# config.toml
log_level = "DEBUG"
```
```bash
nutanix-mcp --config-file config.toml serve-stdio
```

**Via AI client env block:**
```json
"env": {
  "LOG_LEVEL": "DEBUG"
}
```

Log output goes to **both stderr and a file** at `<LOG_DIR>/nutanix-mcp-<YYYYMMDD>-<HHMMSS>-<microseconds>.log`. The default `LOG_DIR` is `<project_root>/logs/`.

To read the latest log:
```bash
ls -t logs/ | head -1 | xargs -I{} cat logs/{}
```

</details>

<details>
<summary><strong>Why does the AI sometimes call the wrong tool or guess operation names?</strong></summary>

AI models sometimes attempt to infer Nutanix operation names from training data or from the tool description rather than calling `listOperations` first. When a guessed name does not exactly match a loaded operation ID, the call returns `{"code": "unknown_operation"}`.

The MCP server's instructions field tells AI clients:

> *"Use listOperations/getOperationSchema/getCodeSample before executing operations."*

If your AI client ignores this guidance, try prepending a system prompt that reinforces the discovery-first pattern:

> *"Before calling any Nutanix API operation, always call listOperations to find the exact operation ID. Never guess operation names."*

The `listOperations` search is a case-insensitive substring match — a broad keyword like `"vm"` or `"snapshot"` is sufficient to find what you need.

</details>

<details>
<summary><strong>What is the <code>listOperations</code> tool and when should I use it?</strong></summary>

`listOperations` is a discovery tool that searches the in-memory operation index built from the downloaded OpenAPI YAML artifacts. It does not call any Nutanix API — it queries only local data.

**Use it:**
- Before every `_execute` call to find the exact operation ID.
- To explore what operations are available in a namespace.
- To check required roles via the `required_roles` field in results.
- When an `_execute` call returns `unknown_operation`.

**Parameters:**

| Parameter | Description |
|---|---|
| `search` | Keyword substring to search across operation ID, path, summary, description |
| `namespace` | Filter to one namespace (e.g., `"vmm"`, `"prism"`) |
| `limit` | Max results returned (default 100, max 500) |
| `offset` | Pagination offset |

**Example:**
```
listOperations(search="recovery point", namespace="dataprotection", limit=10)
```

Results are sorted alphabetically by `(namespace, operation)`. There is no relevance ranking — use a specific keyword for better results.

</details>
