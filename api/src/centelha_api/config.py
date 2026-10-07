import base64
import binascii
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
    # Faixa cifrada no formato .cent (ADR 0004). Desligado até o app decifrar. Ligado,
    # exige a chave-mestra: 32 bytes em base64, só no .env da VPS e no backup.
    audio_cifrar: bool = False
    audio_chave_mestra: str = ""
    # Purge da Cloudflare depois de recifrar faixa antiga (centelha-recifrar): o .m4a
    # aberto tem cache eterno e continuaria servido sem isso. Token só com a permissão
    # "Zone > Cache Purge" nesta zona. Vazio: o comando lista as URLs para purge à mão.
    cloudflare_zone_id: str = ""
    cloudflare_token: str = ""
    # Entrega da chave ao app atestado (ADR 0004). A chave vale 90 dias (decisão 2B):
    # depois disso o app precisa ficar online uma vez para renovar.
    chave_validade_dias: int = 90
    # Um capítulo por chave: 300 por dia cobre ouvir e baixar obras inteiras, e barra
    # quem tenta raspar o acervo com um aparelho só.
    chave_limite_por_dia: int = 300
    desafio_validade_segundos: int = 300
    desafio_limite_por_ip: int = 30
    desafio_janela_segundos: int = 3600
    # Só para desenvolvimento e testes: aceita o atestado "falso:<desafio>". Ignorado
    # com ambiente = "producao".
    atestacao_falsa: bool = False
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
    # Motores cujo áudio não vai ao ar: edição não publica e o catálogo não entrega a
    # faixa. As vozes pt-BR do Piper partem do checkpoint lessac, de licença só para
    # pesquisa; decisão do dono em #1 (opção A): nada do Piper sai até o parecer (#3).
    # Liberado o parecer: CENTELHA_TTS_MOTORES_SEM_LICENCA='[]'.
    tts_motores_sem_licenca: set[str] = {"piper"}
    # Pedido ao motor: "segmento" (um por segmento) ou "bloco" (segmentos da mesma voz
    # juntos, entonação contínua; só em motor com marcadores). O padrão sai da escuta (#77).
    tts_modo: Literal["segmento", "bloco"] = "segmento"
    tts_limite_bloco_bytes: int = 4500

    def chave_mestra(self) -> bytes:
        try:
            chave = base64.b64decode(self.audio_chave_mestra, validate=True)
        except binascii.Error as e:
            raise ValueError("CENTELHA_AUDIO_CHAVE_MESTRA não é base64 válido") from e
        if len(chave) != 32:
            raise ValueError("CENTELHA_AUDIO_CHAVE_MESTRA precisa ter 32 bytes em base64")
        return chave


@lru_cache
def get_settings() -> Settings:
    return Settings()
