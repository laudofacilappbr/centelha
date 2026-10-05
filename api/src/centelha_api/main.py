from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import health, waitlist


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
    return app


app = create_app()
