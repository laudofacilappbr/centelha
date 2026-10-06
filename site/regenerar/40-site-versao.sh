#!/bin/sh
# Serviço site (#42): o nginx serve $RAIZ/atual, link para uma pasta de $RAIZ/versoes.
# Imagem nova = aponta para o site embutido nela até o site-construtor gerar outro com
# o conteúdo de agora. Reinício da mesma imagem não mexe no que o construtor gerou.
set -eu
RAIZ=/srv/site
id="imagem-$(cat /usr/share/nginx/html/.versao)"
mkdir -p "$RAIZ/versoes"
if [ ! -d "$RAIZ/versoes/$id" ] || [ ! -e "$RAIZ/atual" ]; then
  rm -rf "$RAIZ/versoes/$id.tmp"
  cp -a /usr/share/nginx/html "$RAIZ/versoes/$id.tmp"
  rm -rf "$RAIZ/versoes/$id"
  mv "$RAIZ/versoes/$id.tmp" "$RAIZ/versoes/$id"
  ln -sfn "versoes/$id" "$RAIZ/atual.novo"
  mv -T "$RAIZ/atual.novo" "$RAIZ/atual"
  # Imagens anteriores não servem mais.
  for v in "$RAIZ"/versoes/imagem-*; do
    [ "$v" = "$RAIZ/versoes/$id" ] || rm -rf "$v"
  done
fi
# O construtor roda como node (1000) e escreve aqui.
chown 1000:1000 "$RAIZ" "$RAIZ/versoes"
