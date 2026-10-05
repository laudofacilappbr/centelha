from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..models import InscricaoListaEspera
from ..ratelimit import JanelaDeslizante, ip_do_cliente

router = APIRouter(prefix="/v1", tags=["site"])
limitador = JanelaDeslizante()


class Inscricao(BaseModel):
    email: EmailStr = Field(max_length=320)
    origem: str = Field(default="site", max_length=40, pattern=r"^[a-z0-9_-]+$")


@router.post("/waitlist", status_code=status.HTTP_202_ACCEPTED)
def inscrever(
    dados: Inscricao, request: Request, session: Session = Depends(get_session)
) -> dict[str, str]:
    cfg = get_settings()
    if not limitador.permitir(
        ip_do_cliente(request), cfg.waitlist_limite_por_ip, cfg.waitlist_janela_segundos
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas")
    email = dados.email.lower()
    # Mesma resposta para e-mail novo ou já inscrito: não revela quem está na lista.
    existe = session.scalar(
        select(InscricaoListaEspera.id).where(InscricaoListaEspera.email == email)
    )
    if not existe:
        session.add(InscricaoListaEspera(email=email, origem=dados.origem))
        session.commit()
    return {"status": "ok"}
