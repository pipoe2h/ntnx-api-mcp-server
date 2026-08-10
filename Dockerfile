FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/pipoe2h/ntnx-api-mcp-server"
LABEL org.opencontainers.image.description="Nutanix V4 API MCP Server"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_PORT=8000 \
    ARTIFACTS_DIR=/app/artifacts \
    LOG_DIR=/app/logs

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir . \
    && chmod +x /app/docker-entrypoint.sh \
    && groupadd --gid 1000 mcpuser \
    && useradd --uid 1000 --gid 1000 --create-home mcpuser \
    && chown -R 1000:1000 /app

USER 1000:1000

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["nutanix-mcp", "serve-http"]
