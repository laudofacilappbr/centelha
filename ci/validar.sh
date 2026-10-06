#!/usr/bin/env bash
# Validação completa em Docker, sem depender do CI do GitHub.
#
#   ci/validar.sh            # api + site + infra + app
#   ci/validar.sh api        # só a API (lint, testes, migrações)
#   ci/validar.sh site       # só o site (build, astro check)
#   ci/validar.sh infra      # compose de dev e prod, Caddyfile
#   ci/validar.sh app        # só o app Flutter (format, analyze, testes)
#   ci/validar.sh backup     # backup → apaga → restaura, com PostgreSQL e S3 locais
#   ci/validar.sh vps        # preparar.sh num Ubuntu 24.04 e o firewall da Cloudflare com
#                            # pacote de verdade; actionlint dos workflows
#   ci/validar.sh imagens    # build das imagens api, worker, site, piper, digitalizacao e backup
#
# Roda o que está na worktree (commitado ou não). Cada worktree usa um projeto Docker
# próprio, então duas sessões validam ao mesmo tempo sem colidir. Sai com código
# diferente de zero se qualquer etapa falhar, e limpa os containers no fim.
set -uo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
cd "$raiz"
projeto="centelha-ci-$(basename "$raiz" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-')"
compose() { docker compose -p "$projeto" -f ci/docker-compose.yml "$@"; }

if ! docker info >/dev/null 2>&1; then
  echo "Docker não responde. Abra o Docker Desktop e rode de novo." >&2
  exit 2
fi

alvos=("$@")
[ ${#alvos[@]} -eq 0 ] && alvos=(api site infra app)

resultado=()
falhou=0
marcar() {
  if [ "$2" -eq 0 ]; then resultado+=("ok     $1"); else resultado+=("FALHOU $1"); falhou=1; fi
}

limpar() { compose down -v --remove-orphans >/dev/null 2>&1; }
trap limpar EXIT

for alvo in "${alvos[@]}"; do
  case "$alvo" in
    api)
      echo "### api"
      compose build -q api && compose run --rm api
      marcar api $?
      ;;
    site)
      echo "### site"
      compose run --rm site
      marcar site $?
      ;;
    app)
      echo "### app"
      compose build -q app && compose run --rm app
      marcar app $?
      ;;
    backup)
      echo "### backup"
      bash infra/backup/teste/testar.sh
      marcar backup $?
      ;;
    vps)
      echo "### vps"
      ok=0
      bash infra/vps/teste/testar.sh || ok=1
      MSYS_NO_PATHCONV=1 docker run --rm -v "$raiz:/repo" -w /repo rhysd/actionlint:1.7.7         -no-color || ok=1
      marcar vps $ok
      ;;
    infra)
      echo "### infra"
      ok=0
      docker compose -f infra/docker-compose.yml config -q || ok=1
      DOMINIO=exemplo.com POSTGRES_PASSWORD=x \
        docker compose -f infra/docker-compose.prod.yml config -q || ok=1
      MSYS_NO_PATHCONV=1 docker run --rm -e DOMINIO=exemplo.com \
        -v "$raiz/infra/Caddyfile:/etc/caddy/Caddyfile:ro" \
        caddy:2-alpine caddy adapt --config /etc/caddy/Caddyfile >/dev/null || ok=1
      marcar infra $ok
      ;;
    imagens)
      echo "### imagens"
      ok=0
      docker build -q --target api -t "$projeto-api" api >/dev/null || ok=1
      docker build -q --target worker -t "$projeto-worker" api >/dev/null || ok=1
      docker build -q -t "$projeto-site" site >/dev/null || ok=1
      docker build -q -t "$projeto-piper" infra/piper >/dev/null || ok=1
      docker build -q --target digitalizacao -t "$projeto-digitalizacao" api >/dev/null || ok=1
      docker build -q -t "$projeto-backup" infra/backup >/dev/null || ok=1
      docker rmi "$projeto-api" "$projeto-worker" "$projeto-site" "$projeto-piper" \
        "$projeto-digitalizacao" "$projeto-backup" >/dev/null 2>&1
      marcar imagens $ok
      ;;
    *)
      echo "alvo desconhecido: $alvo (use api, site, infra, app, backup, vps, imagens)" >&2
      exit 2
      ;;
  esac
done

printf '\n== resultado\n'
printf '%s\n' "${resultado[@]}"
exit $falhou
