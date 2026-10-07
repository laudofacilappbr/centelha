#!/usr/bin/env bash
# Prepara a VPS (Ubuntu 24.04) para o Centelhar (#26). Roda como root, uma vez, e pode
# ser repetido sem estragar nada.
#
#   CHAVE_DEPLOY="ssh-ed25519 AAAA… deploy-github" bash preparar.sh
#
# Faz:
#   - usuário "centelha" (sem senha, no grupo docker) com a chave do deploy;
#   - SSH só por chave, sem root;
#   - ufw negando entrada, exceto SSH;
#   - 80 e 443 só para os IPs da Cloudflare (firewall-cloudflare.sh, na cadeia
#     DOCKER-USER, porque porta publicada pelo Docker passa por fora do ufw);
#   - fail2ban no SSH;
#   - atualizações de segurança automáticas;
#   - Docker oficial com o plugin compose;
#   - swap de 2 GB se não houver;
#   - /opt/centelha para o compose, o Caddyfile, o .env e os certificados.
#
# Antes de rodar, confirme que você entra com chave: depois dele, senha não entra mais.
set -euo pipefail

: "${CHAVE_DEPLOY:?defina CHAVE_DEPLOY com a chave pública do deploy (ssh-ed25519 …)}"
# MODO_TESTE=1: pula o que precisa de systemd, kernel ou rede (teste em container).
MODO_TESTE=${MODO_TESTE:-0}
DIR=/opt/centelha
USUARIO=centelha
aqui=$(cd "$(dirname "$0")" && pwd)

passo() { echo "== $*"; }
servico() { [ "$MODO_TESTE" = 1 ] || systemctl "$@"; }

passo "pacotes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg ufw fail2ban unattended-upgrades \
  openssh-server iptables >/dev/null

if [ "$MODO_TESTE" != 1 ] && ! command -v docker >/dev/null; then
  passo "docker"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  # shellcheck source=/dev/null
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc]" \
    "https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null
fi
getent group docker >/dev/null || groupadd docker

passo "usuário $USUARIO"
id "$USUARIO" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$USUARIO"
usermod -aG docker "$USUARIO"
passwd -l "$USUARIO" >/dev/null
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "/home/$USUARIO/.ssh"
chaves="/home/$USUARIO/.ssh/authorized_keys"
touch "$chaves"
grep -qxF "$CHAVE_DEPLOY" "$chaves" || echo "$CHAVE_DEPLOY" >>"$chaves"
chown "$USUARIO:$USUARIO" "$chaves"
chmod 600 "$chaves"

passo "ssh: só chave, sem root"
install -d /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-centelha.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
CONF
mkdir -p /run/sshd
sshd -t
servico reload ssh

passo "fail2ban"
cat >/etc/fail2ban/jail.d/centelha.local <<'CONF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
CONF
servico enable --now fail2ban

passo "atualizações de segurança automáticas"
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

passo "ufw"
if [ "$MODO_TESTE" != 1 ]; then
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  ufw limit OpenSSH >/dev/null
  ufw --force enable >/dev/null
fi

passo "80/443 só para a Cloudflare"
install -m 755 "$aqui/firewall-cloudflare.sh" /usr/local/sbin/centelha-firewall-cloudflare
cat >/etc/systemd/system/centelha-firewall.service <<'CONF'
[Unit]
Description=Centelhar: 80/443 só para a Cloudflare (cadeia DOCKER-USER)
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/centelha-firewall-cloudflare
RemainAfterExit=yes

[Install]
WantedBy=docker.service
CONF
servico daemon-reload
servico enable --now centelha-firewall.service

passo "swap"
if [ "$MODO_TESTE" != 1 ] && ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

passo "$DIR"
install -d -m 750 -o "$USUARIO" -g "$USUARIO" "$DIR" "$DIR/certs"
chmod 700 "$DIR/certs"

echo
echo "Pronto. Falta, na ordem:"
echo "  1. Teste em outro terminal: ssh $USUARIO@<ip> (sem fechar este)."
echo "  2. origin.pem e origin.key da Cloudflare em $DIR/certs (chmod 600)."
echo "  3. $DIR/.env a partir de infra/.env.example (chmod 600)."
echo "  4. Primeiro deploy pelo GitHub Actions (workflow Deploy)."
