# Security — Nutanix V4 API MCP Server

---

## Reporting a vulnerability

To report a security vulnerability, open a [GitHub Security Advisory](https://github.com/nutanix-core/ntnx-api-mcp-server/security/advisories/new) in this repository. Please do not open a public issue for security vulnerabilities.

Your report should include:

- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested mitigations

We aim to respond within 5 business days. We follow a responsible disclosure model — please allow time for a fix to be prepared before publishing details publicly.

---

## Security posture summary

| Question | Short answer | Full details |
|---|---|---|
| What credentials does it need? | PC username + password **or** a PC API key | [§1 Supported authentication methods](docs/authentication.md#1-supported-authentication-methods) |
| What is the minimum permission set? | Viewer role for read-only use; namespace-specific roles for write operations | [§2 Nutanix role requirements](docs/authentication.md#2-nutanix-role-requirements) |
| Does it open a listening network port? | No — stdio transport only; no inbound connections | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| What external connections does it make? | Outbound HTTPS to `PC_HOST:9440` (API calls) and `developers.nutanix.com` (artifact download only, not at runtime) | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| Does it log credentials? | No — passwords and API keys are masked in all log output | [§7 Audit logging](docs/authentication.md#7-audit-logging) |
| Can it be restricted to read-only? | Yes — use a Viewer-role PC account and restrict namespaces via `NAMESPACE_OVERRIDE_LIST` | [§6 Attack surface](docs/authentication.md#6-attack-surface) |
| License | Apache 2.0 | [LICENSE](LICENSE) |

For the full attack surface analysis, production hardening checklist, TLS options, and audit logging detail: [authentication and security guide](docs/authentication.md).

---

## Actively maintained

This project is maintained by the Nutanix developer experience team. For the full release history and a list of known limitations per version: [CHANGELOG.md](CHANGELOG.md).
