# Changelog — Nutanix V4 API MCP Server

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.8] — Initial release

### Added

**Server**
- MCP stdio server exposing Nutanix V4 REST APIs as callable tools
- 4 always-on discovery tools (no Nutanix API calls made):
  - `listOperations` — search the operation index by keyword or namespace
  - `getOperationSchema` — retrieve full parameter and response schema for any operation
  - `getCodeSample` — fetch a language-specific code example for an operation
  - `getOperationPermissions` — look up Nutanix RBAC roles required for an operation
- Dynamic namespace tool registration: one `<namespace>_execute` tool per downloaded OpenAPI YAML artifact
- Support for up to 19 V4 API namespaces; tools registered depend on your Prism Central version

**Commands**
- `nutanix-mcp init` — downloads API YAML artifacts from Prism Central (`pc_compatible` mode) or the Nutanix developer portal (`latest_release` mode)
- `nutanix-mcp refresh [--force]` — refreshes artifacts with automatic backup and restore on failure
- `nutanix-mcp run [--validate-only]` — runs startup checks including a Prism Central connectivity probe
- `nutanix-mcp serve-stdio` — starts the MCP stdio server for use in AI client configuration

**Authentication**
- HTTP Basic auth (`PC_USERNAME` / `PC_PASSWORD`)
- API key auth (`PC_API_KEY` via `X-ntnx-api-key` header)
- API key takes priority over basic auth when both are configured — no startup error raised; a warning is logged
- 401 / 403 responses from Prism Central are sanitized — raw credential and realm details are never forwarded to the AI client
- Startup connectivity probe with exponential backoff (3 attempts, 1 s → 8 s between retries)
- Credentials stored as `SecretStr` — masked in all log output

**Configuration**
- 12 configuration options via environment variables, `.env` file, or `--config-file`
- Supported config file formats: `.json`, `.yaml`/`.yml`, `.toml`
- Precedence order: CLI flags > `--config-file` > environment variables / `.env` > defaults
- `NAMESPACE_OVERRIDE_LIST` to restrict which namespaces are loaded (useful for air-gapped or restricted environments)
- `READ_ONLY_MODE` — server-side enforcement that rejects all non-GET operations before they reach Prism Central (default: `true`; set to `false` to opt in to write operations)

**Observability**
- `X-NTNX-REQUEST-SOURCE: MCP` header injected on every outbound API call for server-side auditability at the Prism Central layer
- Structured audit log events (`event=api_call`, `event=auth_failure`) emitted per request with method, path, status code, and request ID

**AI client support**
- Cursor (global `~/.cursor/mcp.json` and workspace-scoped `.cursor/mcp.json`)
- Claude Desktop (macOS and Windows)
- MCP Inspector for interactive debugging (`npx @modelcontextprotocol/inspector`)
- Custom clients via the MCP Python SDK (stdio transport)
- MCP tool annotations (`readOnlyHint`, `destructiveHint`, `openWorldHint`) on all namespace executor tools — enables native client-side confirmation UX in supporting clients

**Logging**
- Per-restart log files in `LOG_DIR` with microsecond-precision timestamps
- Text and JSON log formats (`LOG_FORMAT`)
- Credentials masked in all log output

### Known limitations in 0.8

- **Single cluster per process** — one `PC_HOST` per server instance; run separate instances for multiple clusters
- **No connection pooling** — each tool call opens a new HTTP connection to Prism Central
- **No rate limiting** — Prism Central's own rate limits are the only protection against high call volumes
- **Hardcoded 30-second request timeout** — not configurable in this version
- **No async operation polling** — POST/PUT/DELETE calls return a task ID; poll manually via `prism_execute` with the task `extId`
- **No custom CA bundle path** — TLS custom CA support requires installing the CA into the OS trust store
- **No hot-reload of connection settings** — credential or host changes require a server restart

---

For setup instructions: [README.md](README.md). For upgrade procedure: [deployment guide §9](docs/deployment.md#9-updating).
