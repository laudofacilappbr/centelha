#!/bin/sh
# Regera o site quando o conteúdo muda (#42). Roda no serviço site-construtor.
#
# A cada REGENERAR_INTERVALO segundos lê GET /v1/site/marca na API interna. Marca nova
# e igual na leitura seguinte (o admin parou de mexer) = build do site inteiro numa
# pasta nova de $SITE_RAIZ/versoes e troca atômica do link "atual", que o nginx do
# serviço site serve. Build com falha não toca no site no ar.
set -u

RAIZ=${SITE_RAIZ:-/srv/site}
API=${CATALOGO_API_URL:?defina CATALOGO_API_URL, ex.: http://api:8000}
INTERVALO=${REGENERAR_INTERVALO:-60}
MANTER=${REGENERAR_MANTER:-3}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) site-construtor: $*"; }

marca() {
  wget -q -T 10 -O - "$API/v1/site/marca" 2>/dev/null |
    sed -n 's/.*"marca": *"\([0-9a-f]\{64\}\)".*/\1/p'
}

gerar() {
  nome=$(date -u +%Y%m%dT%H%M%SZ)
  destino="$RAIZ/versoes/$nome"
  inicio=$(date +%s)
  # Obrigatório: com a API fora, o build falha em vez de publicar um site sem obras.
  # Build em /app/dist e cópia depois: o Astro move arquivos com rename, que não
  # atravessa para o volume.
  rm -rf dist
  if ! CATALOGO_OBRIGATORIO=1 npx astro build >/tmp/build.log 2>&1; then
    log "build falhou; o site no ar continua o mesmo. Fim do log:"
    tail -n 20 /tmp/build.log
    return 1
  fi
  cp -a dist "$destino.tmp"
  mv "$destino.tmp" "$destino"
  ln -sfn "versoes/$nome" "$RAIZ/atual.novo"
  mv -T "$RAIZ/atual.novo" "$RAIZ/atual"
  # Versões antigas: ficam as MANTER mais recentes (o nome ordena por data). As da
  # imagem (imagem-*) são do serviço site.
  ls -1 "$RAIZ/versoes" | grep -v -e '^imagem-' -e '\.tmp$' | sort -r |
    tail -n +$((MANTER + 1)) | while read -r v; do rm -rf "${RAIZ:?}/versoes/$v"; done
  log "site regerado em $(($(date +%s) - inicio)) s ($nome)"
}

mkdir -p "$RAIZ/versoes"
# Sobra de build interrompido.
rm -rf "$RAIZ"/versoes/*.tmp

# Em memória: ao subir (deploy com código novo do site), gera logo.
ultima=""
vista=""
fora=""
while :; do
  m=$(marca)
  if [ -z "$m" ]; then
    # Uma linha quando cai e outra quando volta, não uma por volta do laço.
    [ -n "$fora" ] || log "API sem resposta em $API/v1/site/marca; o site no ar continua"
    fora=1
  elif [ "$m" != "$ultima" ] && { [ -z "$ultima" ] || [ "$m" = "$vista" ]; }; then
    if gerar; then
      ultima=$m
    else
      # Não insistir a cada minuto num build quebrado.
      sleep $((INTERVALO * 9))
    fi
  fi
  if [ -n "$m" ] && [ -n "$fora" ]; then
    log "API respondeu de novo"
    fora=""
  fi
  vista=$m
  sleep "$INTERVALO"
done
