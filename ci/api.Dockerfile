# Ambiente da validação da API: Python, uv e ffmpeg. O projeto não entra na imagem
# (vem por bind mount); as dependências são instaladas no volume /venv a cada rodada,
# com cache, então trocar de branch não exige rebuild.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*
COPY api.sh /ci/api.sh
