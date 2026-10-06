#!/usr/bin/env bash
# Teste dos scripts da VPS (ci/validar.sh vps), sem VPS:
#  1. preparar.sh roda num Ubuntu 24.04 (MODO_TESTE=1: sem systemd, sem Docker) e
#     deixa usuário, chave, sshd e fail2ban válidos; rodar de novo não duplica nada.
#  2. firewall-cloudflare.sh com pacote de verdade: um "servidor" na porta 80 com a
#     cadeia DOCKER-USER no caminho; cliente fora das faixas não conecta, dentro conecta.
set -euo pipefail
export MSYS_NO_PATHCONV=1
raiz=$(cd "$(dirname "$0")/.." && pwd)
rede="centelha-vps-teste-$$"
falhar() { echo "FALHOU: $*" >&2; exit 1; }
limpar() { docker rm -f "$rede-srv" >/dev/null 2>&1; docker network rm "$rede" >/dev/null 2>&1; }
trap limpar EXIT

echo "== preparar.sh no Ubuntu 24.04"
docker run --rm -v "$raiz:/vps:ro" ubuntu:24.04 bash -c '
  set -e
  export MODO_TESTE=1 CHAVE_DEPLOY="ssh-ed25519 AAAAteste deploy@teste"
  bash /vps/preparar.sh >/tmp/1.log
  bash /vps/preparar.sh >/tmp/2.log
  [ "$(grep -c AAAAteste /home/centelha/.ssh/authorized_keys)" = 1 ] || { echo "chave duplicada"; exit 1; }
  [ "$(stat -c %a /home/centelha/.ssh/authorized_keys)" = 600 ] || { echo "permissão da chave"; exit 1; }
  id -nG centelha | grep -qw docker || { echo "fora do grupo docker"; exit 1; }
  passwd -S centelha | grep -q " L " || { echo "senha não travada"; exit 1; }
  sshd -T | grep -qx "passwordauthentication no" || { echo "senha no ssh"; exit 1; }
  sshd -T | grep -qx "permitrootlogin no" || { echo "root no ssh"; exit 1; }
  fail2ban-client -d >/dev/null 2>&1 || { echo "config do fail2ban"; exit 1; }
  [ -x /usr/local/sbin/centelha-firewall-cloudflare ] || { echo "firewall não instalado"; exit 1; }
  [ "$(stat -c %a /opt/centelha/certs)" = 700 ] || { echo "permissão de certs"; exit 1; }
  echo "preparar ok"
'

echo "== firewall com pacote de verdade"
docker network create --subnet 10.231.0.0/24 "$rede" >/dev/null
# Servidor: python na porta 80 e a DOCKER-USER pendurada na INPUT, como a FORWARD faz
# numa VPS com Docker.
docker run -d --name "$rede-srv" --network "$rede" --ip 10.231.0.10 --cap-add NET_ADMIN \
  -v "$raiz:/vps:ro" ubuntu:24.04 bash -c '
  apt-get update -qq && apt-get install -y -qq iptables iproute2 curl python3 >/dev/null
  iptables -N DOCKER-USER && iptables -I INPUT -j DOCKER-USER
  ip6tables -N DOCKER-USER && ip6tables -I INPUT -j DOCKER-USER
  touch /pronto
  exec python3 -m http.server 80' >/dev/null
for _ in $(seq 1 90); do docker exec "$rede-srv" test -f /pronto 2>/dev/null && break; sleep 2; done
docker exec "$rede-srv" test -f /pronto || falhar "servidor de teste não subiu"

cliente() { docker run --rm --network "$rede" --ip 10.231.0.20 curlimages/curl:8.10.1 \
  -s -o /dev/null --max-time 4 -w "%{http_code}" http://10.231.0.10/ || true; }

[ "$(cliente)" = 200 ] || falhar "sem firewall o servidor deveria responder"

# Lista real da Cloudflare: o cliente (10.231.0.20) está fora dela.
docker exec "$rede-srv" bash /vps/firewall-cloudflare.sh
docker exec "$rede-srv" bash /vps/firewall-cloudflare.sh >/dev/null   # idempotente
n=$(docker exec "$rede-srv" iptables -S DOCKER-USER | grep -c -- "--dports 80,443 -j RETURN")
[ "$n" -ge 15 ] || falhar "faltam faixas da Cloudflare ($n)"
[ "$(docker exec "$rede-srv" iptables -S DOCKER-USER | grep -c DROP)" = 1 ] || falhar "DROP duplicado"
[ "$(cliente)" = 000 ] || falhar "cliente fora da Cloudflare conectou"

# Cliente dentro das faixas permitidas.
docker exec -e FAIXAS_V4=10.231.0.20/32 "$rede-srv" bash /vps/firewall-cloudflare.sh >/dev/null
[ "$(cliente)" = 200 ] || falhar "cliente permitido não conectou"
echo "firewall ok: fora da lista bloqueado, dentro passa, reaplicar não duplica"
