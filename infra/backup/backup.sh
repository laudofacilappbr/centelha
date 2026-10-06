#!/usr/bin/env bash
# Um backup: dump do PostgreSQL e cópia do áudio para o bucket, tudo cifrado.
#
# Destino: remote "cifrado" do rclone (crypt) por cima do bucket S3. Conteúdo e nomes
# saem cifrados com BACKUP_SENHA; sem ela, o bucket é ilegível, inclusive para o
# provedor. Guarde a senha fora da VPS: sem ela não há restauração.
#
# Variáveis: PGHOST PGUSER PGPASSWORD PGDATABASE, BACKUP_S3_ENDPOINT BACKUP_S3_BUCKET
# BACKUP_S3_ACCESS_KEY BACKUP_S3_SECRET_KEY, BACKUP_SENHA, BACKUP_RETENCAO_DIAS (30).
set -euo pipefail

: "${BACKUP_S3_ENDPOINT:?defina BACKUP_S3_ENDPOINT}" "${BACKUP_S3_BUCKET:?}" \
  "${BACKUP_S3_ACCESS_KEY:?}" "${BACKUP_S3_SECRET_KEY:?}" "${BACKUP_SENHA:?defina BACKUP_SENHA}"

# Toda a configuração vem do ambiente; nenhum rclone.conf no container.
export RCLONE_CONFIG=/dev/null
export RCLONE_CONFIG_BUCKET_TYPE=s3
export RCLONE_CONFIG_BUCKET_PROVIDER=Other
export RCLONE_CONFIG_BUCKET_ENDPOINT="$BACKUP_S3_ENDPOINT"
export RCLONE_CONFIG_BUCKET_ACCESS_KEY_ID="$BACKUP_S3_ACCESS_KEY"
export RCLONE_CONFIG_BUCKET_SECRET_ACCESS_KEY="$BACKUP_S3_SECRET_KEY"
export RCLONE_CONFIG_BUCKET_REGION="${BACKUP_S3_REGION:-auto}"
# R2 e B2 não criam bucket pelo rclone com chave restrita; o bucket já existe.
export RCLONE_CONFIG_BUCKET_NO_CHECK_BUCKET=true
export RCLONE_CONFIG_CIFRADO_TYPE=crypt
export RCLONE_CONFIG_CIFRADO_REMOTE="bucket:${BACKUP_S3_BUCKET}/centelha"
RCLONE_CONFIG_CIFRADO_PASSWORD="$(rclone obscure "$BACKUP_SENHA")"
export RCLONE_CONFIG_CIFRADO_PASSWORD

[ "${1:-}" = "--so-config" ] && return 0 2>/dev/null

inicio=$(date -u +%s)
carimbo=$(date -u +%Y%m%d-%H%M%S)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "backup: dump do banco ${PGDATABASE:-centelha}"
pg_dump --format=custom --no-owner --file="$tmp/centelha-$carimbo.dump"
rclone copyto --quiet "$tmp/centelha-$carimbo.dump" "cifrado:postgres/centelha-$carimbo.dump"

# Faixas nunca mudam depois de gravadas (o nome leva a versão): copy só manda as novas.
if [ -d /data/audio ]; then
  echo "backup: áudio novo"
  rclone copy --quiet --transfers 4 /data/audio cifrado:audio
fi

retencao=${BACKUP_RETENCAO_DIAS:-30}
rclone delete --quiet --min-age "${retencao}d" cifrado:postgres

echo "backup ok: centelha-$carimbo.dump em $(( $(date -u +%s) - inicio ))s, retenção ${retencao} dias"
