# Contributing to ntnx-api-mcp-server

> New to this project? See the [README](README.md) for an overview of what this server does, how to install it, and the full namespace list.

Thank you for your interest in contributing. This document covers setup, testing, and the PR process.

---

## Development setup

**Requirements:** Python 3.11 or higher, Git.

```bash
git clone https://github.com/nutanix-core/ntnx-api-mcp-server
cd ntnx-api-mcp-server
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

---

## Running the test suite

```bash
pytest -q
```

All 39 tests must pass before submitting a PR. The tests use mocked HTTP clients — no live Prism Central cluster is required.

To run a single file:

```bash
pytest tests/unit/test_api_handler.py -q
```

**Test structure:**

| Directory | Contents |
|---|---|
| `tests/unit/` | 10 unit test files covering core modules |
| `tests/integration/` | 1 integration test (mocked dispatcher) |
| `tests/functional/` | 1 CLI smoke test |
| `tests/performance/` | Empty — not yet implemented |
| `tests/security/` | Empty — not yet implemented |

---

## Branching and commits

- Branch off `main` for all changes: `git checkout -b your-feature-name`
- Open an issue first for significant changes or new features
- Keep commits focused and atomic
- Write a clear commit message that explains _why_, not just _what_

---

## Pull requests

1. Ensure `pytest -q` passes with all 39 tests.
2. Add unit tests for any new behaviour. New code without tests will not be merged.
3. Run `nutanix-mcp run --validate-only` locally to confirm the server still starts cleanly.
4. Open a PR against `main` with a description of what changed and why.
5. All PRs are reviewed before merge.

---

## Code style

- Python 3.11+ type hints throughout
- Pydantic models for all settings and tool schemas — no raw dicts for structured data
- No `print()` in server code — use the configured logger (`logging.getLogger(__name__)`)
- Keep `src/config/constants.py` free of user-facing strings; error messages belong in the module that raises them

---

## Adding a new namespace

Namespace tools are generated dynamically from downloaded OpenAPI YAML artifacts — no code change is needed to support a new namespace. To test locally:

1. Place a valid OpenAPI YAML file in `artifacts/` with the naming pattern `<namespace>-<version>-all-documentation.yaml`.
2. Run `nutanix-mcp run` to confirm the namespace is discovered and tools are registered.
3. Run `pytest -q` to confirm no existing tests broke.

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
