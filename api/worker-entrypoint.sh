#!/bin/sh
set -e
# O volume de áudio pode ter sido criado por outro container (Caddy, nginx) como root.
# Ajusta o dono e larga o root antes de rodar qualquer código do worker.
chown centelha:centelha /data/audio
exec setpriv --reuid=centelha --regid=centelha --init-groups "$@"
