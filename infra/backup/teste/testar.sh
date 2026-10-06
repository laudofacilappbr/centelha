#!/usr/bin/env bash
# Backup → apaga → restaura, e confere que os dados voltaram e que o bucket está cifrado.
set -euo pipefail
# Git Bash no Windows reescreve "/dados/..." como caminho do Windows.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"
projeto="centelha-backup-teste-$$"
dc() { docker compose -p "$projeto" -f docker-compose.yml "$@"; }
trap 'dc down -v --remove-orphans >/dev/null 2>&1' EXIT
psql() { dc exec -T postgres psql -U centelha -d centelha -Atc "$1"; }
falhar() { echo "FALHOU: $*" >&2; exit 1; }

dc build -q backup
dc up -d --wait postgres s3 >/dev/null

echo "== dados de exemplo"
psql "create table lista_espera (email text); insert into lista_espera values ('pessoa@exemplo.org'), ('outra@exemplo.org');"
dc run --rm -T --entrypoint sh backup -c "mkdir -p /data/audio/le/pt-BR && echo faixa > /data/audio/le/pt-BR/le-c001-v1.m4a"

echo "== backup"
dc run --rm -T backup backup.sh

echo "== bucket cifrado"
listagem=$(dc exec -T s3 find /dados/centelha-backup -type f)
echo "$listagem" | grep -q . || falhar "bucket vazio"
if echo "$listagem" | grep -Eq "centelha-[0-9]|le-c001|postgres/|audio/"; then
  falhar "nomes legíveis no bucket"
fi
dc exec -T s3 sh -c "cat \$(find /dados/centelha-backup -type f)" | grep -aq "pessoa@exemplo" &&
  falhar "conteúdo legível no bucket"

echo "== perda"
psql "drop table lista_espera;"
dc run --rm -T --entrypoint sh backup -c "rm -rf /data/audio/*"

echo "== restauração"
dc run --rm -T backup restaurar.sh ultimo
[ "$(psql 'select count(*) from lista_espera;')" = "2" ] || falhar "linhas não voltaram"
dc run --rm -T --entrypoint sh backup -c "cat /data/audio/le/pt-BR/le-c001-v1.m4a" | grep -q faixa || falhar "áudio não voltou"
[ "$(dc run --rm -T --entrypoint stat backup -c %u /data/audio/le/pt-BR)" = "10001" ] ||
  falhar "áudio restaurado sem o dono do worker"

echo "== senha errada não restaura"
if dc run --rm -T -e BACKUP_SENHA=outra backup restaurar.sh ultimo >/dev/null 2>&1; then
  falhar "restaurou com a senha errada"
fi
echo "backup ok: dump e áudio restaurados; bucket cifrado"
