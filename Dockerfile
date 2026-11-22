# oscura-atti: CLI + MCP server, with OCR (Tesseract) and office conversion (LibreOffice).
#   docker build -t oscura-atti .
#   docker build -t oscura-atti:slim --build-arg WITH_OFFICE=false .   # without LibreOffice (~600 MB smaller)
FROM python:3.12-slim

ARG WITH_OFFICE=true
ARG OCR_LANGS="ita eng spa fra deu"

RUN set -eux; \
    apt-get update; \
    pkgs="tesseract-ocr"; \
    for l in $OCR_LANGS; do pkgs="$pkgs tesseract-ocr-$l"; done; \
    if [ "$WITH_OFFICE" = "true" ]; then pkgs="$pkgs libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui"; fi; \
    apt-get install -y --no-install-recommends $pkgs; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[mcp]"

# Unprivileged user; /data is the only folder the MCP tools may read and write (OSCURA_ATTI_DIR).
RUN useradd --create-home --uid 10001 oscura && mkdir -p /data && chown oscura /data
USER oscura
ENV OSCURA_ATTI_DIR=/data HOME=/tmp PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), 3)" || exit 1

ENTRYPOINT ["oscura-atti"]
CMD ["mcp", "--http", "--host", "0.0.0.0", "--port", "8000"]
