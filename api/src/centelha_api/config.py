from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CENTELHA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://centelha:centelha@localhost:5432/centelha"
    # Origens do site autorizadas a chamar a API pelo navegador.
    cors_origins: list[str] = ["http://localhost:4321"]
    # Atrás da Cloudflare o IP real chega em CF-Connecting-IP.
    confiar_cf_connecting_ip: bool = True
    waitlist_limite_por_ip: int = 5
    waitlist_janela_segundos: int = 3600
    # Validade absoluta da sessão do admin; não renova com uso.
    admin_sessao_horas: int = 12
    # Tentativas de login por IP e por e-mail na janela. Por e-mail barra a força bruta
    # distribuída contra uma conta; por IP barra a varredura de muitas contas.
    admin_login_limite: int = 10
    admin_login_janela_segundos: int = 900
    # Áudio: o worker grava em audio_dir; Caddy serve essa pasta em audio_url_base,
    # com a Cloudflare na frente fazendo cache.
    audio_dir: str = "./audio"
    audio_url_base: str = "http://localhost:8000/audio"
    # Worker: intervalo de consulta da fila e prazo para um job "executando" ser
    # considerado abandonado (worker que morreu) e voltar à fila.
    worker_intervalo_segundos: float = 5.0
    worker_lease_minutos: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
