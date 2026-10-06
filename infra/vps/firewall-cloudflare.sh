#!/usr/bin/env bash
# Deixa 80/443 abertos só para os IPs da Cloudflare (#26).
#
# O ufw não vale para porta publicada pelo Docker: o Docker põe as regras dele antes.
# Por isso o filtro vai na cadeia DOCKER-USER, que o Docker consulta primeiro e não
# apaga. Roda na partida do Docker (centelha-firewall.service) e pode ser repetido.
#
# Sem rede para baixar a lista, usa a cópia abaixo (www.cloudflare.com/ips, out/2026).
# SAIDA=arquivo: só escreve as regras (iptables-restore) no arquivo, sem aplicar.
# INTERFACE: a interface pública; sem ela, a da rota padrão.
# FAIXAS_V4 / FAIXAS_V6: usam estas faixas em vez da lista da Cloudflare (teste).
set -euo pipefail

IPV4_PADRAO="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18
108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17
162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22"
IPV6_PADRAO="2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32
2a06:98c0::/29 2c0f:f248::/32"

baixar() {
  local lista
  if lista=$(curl -fsS --max-time 10 "https://www.cloudflare.com/ips-$1" 2>/dev/null) &&
    [ -n "$lista" ]; then
    echo "$lista"
  else
    echo "$2"
  fi
}

regras() {
  # $1: lista de faixas. Só a interface pública é filtrada: Caddy falando com o site
  # (porta 80) pela bridge interna do Docker também passa por esta cadeia.
  echo "*filter"
  echo ":DOCKER-USER - [0:0]"
  echo "-F DOCKER-USER"
  # Resposta de conexão já aberta (inclusive saída dos containers) passa sempre.
  echo "-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN"
  for faixa in $1; do
    echo "-A DOCKER-USER -i $INTERFACE -p tcp -m multiport --dports 80,443 -s $faixa -j RETURN"
  done
  echo "-A DOCKER-USER -i $INTERFACE -p tcp -m multiport --dports 80,443 -j DROP"
  echo "-A DOCKER-USER -j RETURN"
  echo "COMMIT"
}

INTERFACE=${INTERFACE:-$(ip -o route show default 2>/dev/null | awk '{print $5; exit}')}
: "${INTERFACE:?não achei a interface da rota padrão; defina INTERFACE}"

v4=${FAIXAS_V4:-$(baixar v4 "$IPV4_PADRAO")}
v6=${FAIXAS_V6:-$(baixar v6 "$IPV6_PADRAO")}

if [ -n "${SAIDA:-}" ]; then
  { regras "$v4"; echo "# ipv6"; regras "$v6"; } >"$SAIDA"
  exit 0
fi
regras "$v4" | iptables-restore --noflush
regras "$v6" | ip6tables-restore --noflush
echo "DOCKER-USER: 80/443 liberados para $(echo "$v4 $v6" | wc -w) faixas da Cloudflare"
