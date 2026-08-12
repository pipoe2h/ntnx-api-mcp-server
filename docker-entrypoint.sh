#!/bin/sh
set -eu

# Kubernetes integrations sometimes provide only CLI options as the container
# arguments (and may combine an option and its value in one argument). In that
# case Docker's CMD is replaced, so restore the default command and normalize
# the combined arguments before continuing.
case "${1:-}" in
    --*)
        exec python -c '
import os
import sys

entrypoint, *arguments = sys.argv[1:]
normalized = []
for argument in arguments:
    if argument.startswith("--") and " " in argument:
        option, value = argument.split(None, 1)
        normalized.extend((option, value))
    else:
        normalized.append(argument)

os.execv(entrypoint, [entrypoint, "nutanix-mcp", "serve-http", *normalized])
' "$0" "$@"
        ;;
esac

case "${1:-}" in
    init|refresh|run|serve-stdio|serve-http)
        set -- nutanix-mcp "$@"
        ;;
esac

if [ "${1:-}" = "nutanix-mcp" ] && [ "${2:-}" = "serve-http" ]; then
    has_host=false
    has_port=false
    for argument in "$@"; do
        case "$argument" in
            --host|--host=*) has_host=true ;;
            --port|--port=*) has_port=true ;;
        esac
    done
    if [ "$has_host" = false ]; then
        set -- "$@" --host 0.0.0.0
    fi
    if [ "$has_port" = false ]; then
        set -- "$@" --port "${MCP_PORT:-8000}"
    fi

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
    "--pc-port",
    "--pc-username",
    "--pc-password",
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
