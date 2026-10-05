import os

# Banco de teste separado; precisa estar definido antes de importar o app.
os.environ.setdefault(
    "CENTELHA_DATABASE_URL",
    os.environ.get(
        "CENTELHA_TEST_DATABASE_URL",
        "postgresql+psycopg://centelha:centelha@localhost:55432/centelha_test?connect_timeout=5",
    ),
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from centelha_api.db import Base, SessionLocal, engine  # noqa: E402
from centelha_api.main import create_app  # noqa: E402
from centelha_api.routers.waitlist import limitador  # noqa: E402


@pytest.fixture(autouse=True)
def banco_limpo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limitador.limpar()
    yield


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(create_app())
