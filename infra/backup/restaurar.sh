#!/usr/bin/env bash
# Restaura o banco a partir de um dump do bucket e traz o áudio de volta.
#
#   restaurar.sh                    # lista os dumps disponíveis
#   restaurar.sh ultimo             # o mais recente
#   restaurar.sh centelha-20261006-030000.dump
#
# Apaga e recria os objetos do banco de destino (pg_restore --clean). Na VPS:
#   docker compose -f docker-compose.prod.yml stop api worker
#   docker compose -f docker-compose.prod.yml run --rm backup restaurar.sh ultimo
#   docker compose -f docker-compose.prod.yml start api worker
set -euo pipefail
# shellcheck source=/dev/null  # backup.sh, no PATH do container
source backup.sh --so-config

if [ $# -eq 0 ]; then
  rclone lsf cifrado:postgres | sort
  exit 0
fi

arquivo=$1
if [ "$arquivo" = "ultimo" ]; then
  arquivo=$(rclone lsf cifrado:postgres | sort | tail -n 1)
  [ -n "$arquivo" ] || { echo "nenhum dump no bucket" >&2; exit 1; }
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "restaurar: $arquivo"
rclone copyto --quiet "cifrado:postgres/$arquivo" "$tmp/$arquivo"
pg_restore --clean --if-exists --no-owner --dbname="${PGDATABASE:-centelha}" "$tmp/$arquivo"

if [ -d /data/audio ]; then
  echo "restaurar: áudio"
  rclone copy --quiet --transfers 4 cifrado:audio /data/audio
  # O worker grava como uid 10001 (api/Dockerfile); pastas restauradas como root o
  # impediriam de criar faixas novas.
  chown -R 10001:10001 /data/audio
fi
echo "restauração ok: $arquivo"
