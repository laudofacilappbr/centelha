from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, admin_direitos, admin_editorial, catalogo, health, waitlist


def create_app() -> FastAPI:
    app = FastAPI(title="Centelha API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(waitlist.router)
    app.include_router(catalogo.router)
    app.include_router(admin.router)
    app.include_router(admin_direitos.router)
    app.include_router(admin_editorial.router)
    return app


app = create_app()
