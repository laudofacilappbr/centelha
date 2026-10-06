#!/usr/bin/env bash
# Roda o backup uma vez por dia, na hora BACKUP_HORA (UTC, padrão 6 = 3h em Brasília).
# Sem cron: um laço que dorme até a próxima hora marcada, com o log no stdout do
# container. Falha não derruba o laço; a linha "BACKUP FALHOU" é o que o alerta
# (#27) procura.
set -uo pipefail
hora=${BACKUP_HORA:-6}
echo "backup agendado para ${hora}h UTC"
while true; do
  agora=$(date -u +%s)
  alvo=$(date -u -d "$(date -u +%Y-%m-%d) $(printf %02d "$hora"):00:00" +%s)
  [ "$alvo" -le "$agora" ] && alvo=$(( alvo + 86400 ))
  sleep $(( alvo - agora ))
  if ! backup.sh; then
    echo "BACKUP FALHOU em $(date -u +%FT%TZ)" >&2
  fi
done
