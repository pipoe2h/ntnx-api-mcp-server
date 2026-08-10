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
    mkdir -p "${ARTIFACTS_DIR:-/app/artifacts}" "${LOG_DIR:-/app/logs}"
    if ! find "${ARTIFACTS_DIR:-/app/artifacts}" -maxdepth 1 \
        -name '*-all-documentation.yaml' -print -quit | grep -q .; then
        nutanix-mcp init
    fi
fi

exec "$@"
