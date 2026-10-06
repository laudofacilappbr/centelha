FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS base
RUN useradd --system --uid 10001 centelha \
 && mkdir -p /data/audio && chown centelha /data/audio
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh /usr/local/bin/
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 CENTELHA_AUDIO_DIR=/data/audio

# Worker da fila de áudio: precisa de ffmpeg; a API não. docker build --target worker
# fonts-comfortaa: fonte da marca na legenda dos vídeos curtos (libass, #44).
FROM base AS worker
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-comfortaa \
 && rm -rf /var/lib/apt/lists/*
COPY worker-entrypoint.sh /usr/local/bin/
# Começa como root só para o chown do volume; o entrypoint troca para "centelha".
ENTRYPOINT ["worker-entrypoint.sh"]
CMD ["python", "-m", "centelha_api.pipeline.worker"]

# Último estágio = alvo padrão do docker build.
FROM base AS api
USER centelha
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
ENTRYPOINT ["docker-entrypoint.sh"]
# --proxy-headers: o IP do cliente chega via Caddy/Cloudflare.
CMD ["uvicorn", "centelha_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
