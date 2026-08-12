#!/bin/sh
set -eu

case "${1:-}" in
    init|refresh|run|serve-stdio|serve-http)
        set -- nutanix-mcp "$@"
        ;;
esac

if [ "$#" -eq 2 ] && [ "$1" = "nutanix-mcp" ] && [ "$2" = "serve-http" ]; then
    set -- "$@" --host 0.0.0.0 --port "${MCP_PORT:-8000}"
fi

if [ "${1:-}" = "nutanix-mcp" ] && [ "${2:-}" = "serve-http" ]; then
    mkdir -p "${ARTIFACTS_DIR:-/tmp/artifacts}" "${LOG_DIR:-/tmp/logs}"
    if ! find "${ARTIFACTS_DIR:-/tmp/artifacts}" -maxdepth 1 \
        -name '*-all-documentation.yaml' -print -quit | grep -q .; then
        # Forward Prism Central command arguments to automatic initialization.
        # Python is used here to preserve argument boundaries (notably passwords
        # containing spaces or shell metacharacters) without eval.
        python - "$@" <<'PY'
import subprocess
import sys

value_options = {
    "--pc-host",
    "--pc_host",
    "--pc-port",
    "--pc_port",
    "--pc-username",
    "--pc_username",
    "--pc-password",
    "--pc_password",
}
forwarded = []
arguments = iter(sys.argv[1:])
for argument in arguments:
    option = argument.split("=", 1)[0]
    if option not in value_options:
        continue
    forwarded.append(argument)
    if "=" not in argument:
        try:
            forwarded.append(next(arguments))
        except StopIteration as exc:
            raise SystemExit(f"Missing value for {argument}") from exc

subprocess.run(["nutanix-mcp", "init", *forwarded], check=True)
PY
    fi
fi

exec "$@"
