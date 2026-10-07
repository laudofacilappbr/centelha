from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .observabilidade import MiddlewareRequisicao, configurar_logs
from .routers import (
    admin,
    admin_audio,
    admin_custos,
    admin_direitos,
    admin_editorial,
    admin_exportacao,
    admin_pronuncia,
    admin_seo,
    apoio,
    campanhas,
    catalogo,
    conta,
    dispositivos,
    glossario,
    health,
    planos,
    posts,
    site,
    temas,
    transparencia,
    waitlist,
)


def create_app() -> FastAPI:
    configurar_logs("api")
    app = FastAPI(title="Centelhar API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    # Por último = mais externo: o request_id vale também para o CORS e os erros.
    app.add_middleware(MiddlewareRequisicao)
    app.include_router(health.router)
    app.include_router(waitlist.router)
    app.include_router(catalogo.router)
    app.include_router(dispositivos.router)
    app.include_router(admin.router)
    app.include_router(admin_direitos.router)
    app.include_router(admin_editorial.router)
    app.include_router(admin_audio.router)
    app.include_router(admin_pronuncia.router)
    app.include_router(admin_seo.router)
    app.include_router(admin_custos.router)
    app.include_router(transparencia.publico)
    app.include_router(transparencia.admin)
    app.include_router(temas.publico)
    app.include_router(temas.admin)
    app.include_router(glossario.publico)
    app.include_router(glossario.admin)
    app.include_router(posts.publico)
    app.include_router(posts.admin)
    app.include_router(apoio.publico)
    app.include_router(apoio.admin)
    app.include_router(campanhas.publico)
    app.include_router(campanhas.admin)
    app.include_router(site.router)
    app.include_router(planos.router)
    app.include_router(conta.router)
    app.include_router(admin_exportacao.router)
    return app


app = create_app()
