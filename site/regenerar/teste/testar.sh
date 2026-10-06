#!/usr/bin/env bash
# Site-construtor (#42): publica no banco → o site passa a mostrar; API fora → o site
# continua; reinício do site → continua a versão gerada, não a da imagem.
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"
projeto="centelha-site-teste-$$"
dc() { docker compose -p "$projeto" -f docker-compose.yml "$@"; }
trap 'dc down -v --remove-orphans >/dev/null 2>&1' EXIT
psql() { dc exec -T postgres psql -U centelha -d centelha -v ON_ERROR_STOP=1 -Atc "$1"; }
falhar() { echo "FALHOU: $*" >&2; dc logs site-construtor | tail -30 >&2; exit 1; }
status() { dc exec -T site sh -c "wget -S -q -O /dev/null http://127.0.0.1$1 2>&1 | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | tail -1"; }
pagina() { dc exec -T site wget -q -O - "http://127.0.0.1$1"; }
regeracoes() { dc logs site-construtor 2>/dev/null | grep -c "site regerado" || true; }
esperar_regeracao() {
  local antes=$1
  for _ in $(seq 1 90); do
    [ "$(regeracoes)" -gt "$antes" ] && return 0
    sleep 2
  done
  falhar "não regerou em 180 s"
}

dc build -q
dc up -d --wait postgres api site >/dev/null
dc up -d site-construtor >/dev/null

echo "== build inicial ao subir"
esperar_regeracao 0
[ "$(status /obras/o-livro-dos-espiritos)" = "404" ] || falhar "obra apareceu antes de existir"

echo "== publicação no banco"
psql "
insert into obra (slug, autor, titulo_original, ano, idioma_original, sigla)
  values ('o-livro-dos-espiritos', 'Allan Kardec', 'Le Livre des Esprits', 1857, 'fr', 'LE');
insert into edicao (obra_id, idioma, publico, titulo, tradutor, fonte, notas_rodape, publicada_em)
  values (1, 'pt-BR', 'adulto', 'O Livro dos Espíritos', 'Guillon Ribeiro', 'teste', 'fim', now());
insert into direitos (edicao_id, status) values (1, 'aprovado');
insert into capitulo (edicao_id, ordem, titulo, referencia_canonica, estado)
  values (1, 1, 'De Deus', 'LE-C001', 'publicado');
insert into segmento (capitulo_id, ordem, tipo, texto, numero_questao)
  values (1, 1, 'pergunta', 'Que é Deus?', 1), (1, 2, 'resposta', 'Deus é a inteligência suprema.', 1);"
esperar_regeracao 1
[ "$(status /obras/o-livro-dos-espiritos)" = "200" ] || falhar "obra não apareceu"
pagina /obras/o-livro-dos-espiritos | grep -q "O Livro dos Espíritos" || falhar "página sem o título"
pagina /livro-dos-espiritos/questao/1 | grep -q "inteligência suprema" || falhar "questão 1 sem o texto"
pagina / | grep -q "https://audio.centelha.exemplo" || falhar "CSP sem a origem do áudio"

echo "== sem mudança, sem build"
n=$(regeracoes); sleep 12
[ "$(regeracoes)" = "$n" ] || falhar "regerou sem mudança"

echo "== API fora: o site continua"
dc stop api >/dev/null
psql "update capitulo set titulo = 'De Deus (revisto)' where id = 1;"
for _ in $(seq 1 15); do
  dc logs site-construtor | grep -q "API sem resposta" && break
  sleep 2
done
dc logs site-construtor | grep -q "API sem resposta" || falhar "não registrou a API fora"
[ "$(status /obras/o-livro-dos-espiritos)" = "200" ] || falhar "site caiu com a API fora"

echo "== API de volta: a mudança chega"
n=$(regeracoes)
dc start api >/dev/null
esperar_regeracao "$n"
pagina /obras/o-livro-dos-espiritos | grep -q "De Deus (revisto)" || falhar "mudança não chegou"

echo "== reinício do site mantém a versão gerada"
dc restart site >/dev/null
sleep 3
pagina /obras/o-livro-dos-espiritos | grep -q "De Deus (revisto)" || falhar "voltou para a versão da imagem"

echo "== versões guardadas"
dc exec -T site sh -c 'ls /srv/site/versoes; readlink /srv/site/atual'
[ "$(dc exec -T site sh -c 'ls /srv/site/versoes | grep -vc ^imagem-')" -le 3 ] || falhar "versões antigas não foram apagadas"

echo "OK"
