"""Worker da fila de áudio: python -m centelha_api.pipeline.worker

Um processo, um job por vez. Para escalar, suba mais containers do worker: o
SKIP LOCKED garante que cada job sai para um só.
"""

import logging
import signal
import sys
import time

from ..config import get_settings
from ..db import SessionLocal
from ..observabilidade import configurar_logs, contexto
from .armazenamento import armazenamento_padrao
from .jobs import executar, falhar, pegar

log = logging.getLogger("centelha.worker")


class _Parada:
    pedida = False

    def __call__(self, *_):
        # Termina o job atual e sai; o lease cobre o caso de ser morto à força.
        log.info("parada pedida; terminando o job atual")
        self.pedida = True


def processar_um(session_factory=SessionLocal, armazenamento=None, motor=None) -> bool:
    """Processa um job, se houver. Devolve se processou."""
    with session_factory() as session:
        job = pegar(session)
        if job is None:
            return False
        # job_id e capitulo_id em toda linha: os mesmos ids que o admin mostra.
        with contexto(job_id=job.id, capitulo_id=job.capitulo_id):
            log.info("job iniciado, tentativa %s", job.tentativas)
            try:
                faixa = executar(session, job, armazenamento or armazenamento_padrao(), motor)
            except Exception as e:  # noqa: BLE001 — qualquer erro vira falha registrada do job
                log.exception("job falhou")
                falhar(session, job, f"{type(e).__name__}: {e}")
            else:
                log.info("faixa %s v%s gravada", faixa.id, faixa.versao)
        return True


def main() -> int:
    configurar_logs("worker")
    parada = _Parada()
    signal.signal(signal.SIGTERM, parada)
    signal.signal(signal.SIGINT, parada)
    intervalo = get_settings().worker_intervalo_segundos
    log.info("worker iniciado")
    while not parada.pedida:
        try:
            processou = processar_um()
        except Exception:  # noqa: BLE001 — banco fora do ar ou migração ainda não aplicada
            log.exception("erro ao consultar a fila; tentando de novo")
            processou = False
        if not processou:
            time.sleep(intervalo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
