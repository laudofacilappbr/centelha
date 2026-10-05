from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session

router = APIRouter(tags=["infra"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("select 1"))
    return {"status": "ok"}
