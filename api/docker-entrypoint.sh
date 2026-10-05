#!/bin/sh
set -e
# Migrações rodam antes de subir a API. Com mais de uma réplica, mover para um job separado.
if [ "${CENTELHA_MIGRAR_AO_INICIAR:-1}" = "1" ]; then
  alembic upgrade head
fi
exec "$@"
