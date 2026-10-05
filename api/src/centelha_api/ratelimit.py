import time
from collections import defaultdict, deque

from fastapi import Request

from .config import get_settings


class JanelaDeslizante:
    """Limite em memória por chave. Basta enquanto a API roda em um único container;
    com réplicas, mover para o Redis."""

    def __init__(self) -> None:
        self._eventos: dict[str, deque[float]] = defaultdict(deque)

    def permitir(self, chave: str, limite: int, janela: float, agora: float | None = None) -> bool:
        agora = time.monotonic() if agora is None else agora
        fila = self._eventos[chave]
        while fila and agora - fila[0] >= janela:
            fila.popleft()
        if len(fila) >= limite:
            return False
        fila.append(agora)
        return True

    def limpar(self) -> None:
        self._eventos.clear()


def ip_do_cliente(request: Request) -> str:
    if get_settings().confiar_cf_connecting_ip:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf
    return request.client.host if request.client else "desconhecido"
