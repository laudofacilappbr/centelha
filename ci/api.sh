#!/usr/bin/env bash
# Roda dentro do container "api" de ci/docker-compose.yml.
set -euo pipefail

etapa() { printf '\n== %s\n' "$*"; }

etapa "dependências (uv sync --frozen)"
uv sync --frozen --quiet

etapa "lint (ruff check)"
uv run --no-sync ruff check .

etapa "formatação (ruff format --check)"
uv run --no-sync ruff format --check .

etapa "testes (pytest, PostgreSQL)"
uv run --no-sync pytest -q

etapa "migrações: head única, upgrade, check, downgrade, upgrade"
export CENTELHA_DATABASE_URL="$CENTELHA_MIG_DATABASE_URL"
heads=$(uv run --no-sync alembic heads | grep -c "(head)")
if [ "$heads" -ne 1 ]; then
  echo "esperava 1 head de migração, achei $heads" >&2
  exit 1
fi
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync alembic downgrade base
uv run --no-sync alembic upgrade head
