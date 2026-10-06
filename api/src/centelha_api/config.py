from functools import lru_cache
from typing import Literal

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
    # Logs: "json" em produção (uma linha por evento), "texto" para ler no terminal.
    log_formato: str = "json"
    log_nivel: str = "info"
    ambiente: str = "desenvolvimento"
    # Vazio = Sentry desligado. Ligar é decisão do dono (terceiro recebendo dados).
    sentry_dsn: str = ""

    # Preço do motor de TTS por milhão de caracteres, para o custo estimado no admin.
    # Ex.: CENTELHA_TTS_PRECO_POR_MILHAO='{"azure": 85.0, "google": 85.0}'. Vazio por
    # padrão: preço muda por provedor e contrato, a fonte é a fatura.
    tts_preco_por_milhao: dict[str, float] = {"falso": 0.0, "piper": 0.0}
    tts_moeda: str = "BRL"
    # Pedido ao motor: "segmento" (um por segmento) ou "bloco" (segmentos da mesma voz
    # juntos, entonação contínua; só em motor com marcadores). O padrão sai da escuta (#77).
    tts_modo: Literal["segmento", "bloco"] = "segmento"
    tts_limite_bloco_bytes: int = 4500


@lru_cache
def get_settings() -> Settings:
    return Settings()
