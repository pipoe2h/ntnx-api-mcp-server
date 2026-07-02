# Security — Nutanix V4 API MCP Server

---

## Reporting bugs and feature requests

Use [GitHub Issues](https://github.com/nutanix/ntnx-api-mcp-server/issues) to report bugs, request features, or flag documentation problems. Issue templates are available for each category — select the appropriate one when opening an issue.

---

## Security posture summary

| Question | Short answer | Full details |
|---|---|---|
| What credentials does it need? | PC username + password **or** a PC API key | [§1 Supported authentication methods](docs/authentication.md#1-supported-authentication-methods) |
| What is the minimum permission set? | Viewer role for read-only use; namespace-specific roles for write operations | [§2 Nutanix role requirements](docs/authentication.md#2-nutanix-role-requirements) |
| Does it open a listening network port? | No — stdio transport only; no inbound connections | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| What external connections does it make? | Outbound HTTPS to `PC_HOST:9440` (API calls) and `developers.nutanix.com` (artifact download only, not at runtime) | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| Does it log credentials? | No — passwords and API keys are masked in all log output | [§7 Audit logging](docs/authentication.md#7-audit-logging) |
| Can it be restricted to read-only? | Yes — set `READ_ONLY_MODE=true` for server-side GET-only enforcement; additionally use a Viewer-role PC account for RBAC-level restriction | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| License | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | — |

For the full attack surface analysis, production hardening checklist, TLS options, and audit logging detail: [authentication and security guide](docs/authentication.md).

---

## Project status

This project is in **Technical Preview**. It is not designed, tested, or supported for production workloads. Breaking changes may occur between releases. For the full release history and known limitations per version: [CHANGELOG.md](CHANGELOG.md).
