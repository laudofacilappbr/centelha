"""Recifra as faixas .m4a gravadas antes de ligar a cifragem (#73, ADR 0004).

    centelha-recifrar              # só lista o que faria
    centelha-recifrar --executar   # cifra, apaga os .m4a e pede o purge na Cloudflare

Roda no container do worker, que monta o volume do áudio para escrita e tem a
chave-mestra. Só com CENTELHA_AUDIO_CIFRAR ligada: o app atual toca só .m4a, então
recifrar antes de o app decifrar tiraria o áudio do ar.

Ordem, por faixa, e por quê:
1. cifra o .m4a com chave nova e grava o .cent ao lado (mesmo nome, outra extensão);
2. troca url, formato e chave no banco e faz commit;
3. só então apaga o .m4a do volume e pede o purge na Cloudflare: da URL antiga do
   áudio e do JSON público do capítulo (/v1/capitulos/{id}), que a CDN guarda por
   1 h com a URL da faixa dentro. Sem o segundo, o app receberia o .m4a apagado.

Apagar antes do commit deixaria o banco apontando para arquivo inexistente. Pedir o
purge antes de apagar deixaria a CDN buscar o .m4a de novo na origem e guardá-lo com
cache eterno. A versão da faixa não muda: o áudio é o mesmo, byte a byte, e as
marcações e o progresso salvo no app continuam valendo.

O passo 3 olha todas as faixas .cent, não só as desta execução. Assim, uma execução
interrompida depois do commit é terminada pela seguinte. E o .m4a só é apagado depois
de o .cent ter sido decifrado e conferido contra ele.
"""

import argparse
import json
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FaixaAudio
from . import cifra
from .armazenamento import Armazenamento, armazenamento_padrao

# Limite de URLs por pedido de purge da Cloudflare (planos sem Enterprise).
_PURGE_POR_PEDIDO = 30


class ErroRecifrar(Exception):
    pass


class ErroPurge(Exception):
    pass


def _relativo(url: str) -> str | None:
    """Caminho dentro do volume, ou None se a URL não é do armazenamento local."""
    base = get_settings().audio_url_base.rstrip("/") + "/"
    return url[len(base) :] if url.startswith(base) else None


def _no_volume(relativo: str) -> Path:
    return Path(get_settings().audio_dir) / relativo


def pendentes(session: Session) -> list[FaixaAudio]:
    return list(
        session.scalars(
            select(FaixaAudio).where(FaixaAudio.formato == "m4a").order_by(FaixaAudio.id)
        )
    )


def recifrar(faixa: FaixaAudio, mestra: bytes, armazenamento: Armazenamento | None = None) -> None:
    """Grava o .cent da faixa e troca os campos dela. O commit fica com quem chama."""
    relativo = _relativo(faixa.url)
    if relativo is None or not relativo.endswith(".m4a"):
        raise ErroRecifrar(f"faixa {faixa.id}: {faixa.url} não é um .m4a do volume local")
    origem = _no_volume(relativo)
    if not origem.exists():
        raise ErroRecifrar(f"faixa {faixa.id}: arquivo {origem} não existe")

    chave = cifra.nova_chave()
    with tempfile.TemporaryDirectory() as tmp:
        cifrado = Path(tmp) / "faixa.cent"
        cifrado.write_bytes(cifra.cifrar(origem.read_bytes(), chave))
        destino = relativo.removesuffix(".m4a") + ".cent"
        url = (armazenamento or armazenamento_padrao()).salvar(cifrado, destino)
    faixa.url, faixa.formato = url, cifra.FORMATO
    faixa.chave_cifrada = cifra.embrulhar(chave, mestra)


@dataclass
class Aberto:
    """O .m4a que sobrou de uma faixa já cifrada."""

    faixa: FaixaAudio
    arquivo: Path
    url: str


def abertos_restantes(session: Session) -> list[Aberto]:
    restantes = []
    for faixa in session.scalars(
        select(FaixaAudio).where(FaixaAudio.formato == cifra.FORMATO).order_by(FaixaAudio.id)
    ):
        relativo = _relativo(faixa.url)
        if relativo is None or not relativo.endswith(".cent"):
            continue
        aberto = relativo.removesuffix(".cent") + ".m4a"
        if _no_volume(aberto).exists():
            url = faixa.url.removesuffix(".cent") + ".m4a"
            restantes.append(Aberto(faixa, _no_volume(aberto), url))
    return restantes


def apagar_aberto(aberto: Aberto, mestra: bytes) -> None:
    """Apaga o .m4a só se o .cent publicado decifra exatamente nele."""
    publicado = _no_volume(_relativo(aberto.faixa.url) or "")
    if aberto.faixa.chave_cifrada is None or not publicado.exists():
        raise ErroRecifrar(f"faixa {aberto.faixa.id}: .cent ou chave ausente; .m4a mantido")
    chave = cifra.desembrulhar(aberto.faixa.chave_cifrada, mestra)
    if cifra.decifrar(publicado.read_bytes(), chave) != aberto.arquivo.read_bytes():
        raise ErroRecifrar(f"faixa {aberto.faixa.id}: .cent não confere com o .m4a; mantido")
    aberto.arquivo.unlink()


Enviar = Callable[[urllib.request.Request], dict]


def _enviar(pedido: urllib.request.Request) -> dict:
    with urllib.request.urlopen(pedido, timeout=30) as r:  # noqa: S310 (URL fixa da API)
        return json.load(r)


def purgar(urls: list[str], zona: str, token: str, enviar: Enviar = _enviar) -> None:
    for i in range(0, len(urls), _PURGE_POR_PEDIDO):
        lote = urls[i : i + _PURGE_POR_PEDIDO]
        pedido = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{zona}/purge_cache",
            data=json.dumps({"files": lote}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            resposta = enviar(pedido)
        except OSError as e:
            raise ErroPurge(f"purge falhou: {e}") from e
        if not resposta.get("success"):
            raise ErroPurge(f"purge recusado: {resposta.get('errors')}")


@dataclass
class Relatorio:
    recifradas: list[int] = field(default_factory=list)
    apagados: list[str] = field(default_factory=list)
    # Capítulos cujo JSON público ainda pode ter, no cache, a URL do .m4a apagado.
    capitulos: list[int] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)

    def para_purgar(self, api_publica: str) -> list[str]:
        """URLs do purge; sem o endereço público da api, só as do áudio."""
        base = api_publica.rstrip("/")
        jsons = [f"{base}/v1/capitulos/{c}" for c in self.capitulos] if base else []
        return self.apagados + jsons


def executar(
    session: Session, mestra: bytes, limite: int | None = None, armazenamento=None
) -> Relatorio:
    rel = Relatorio()
    for faixa in pendentes(session)[:limite]:
        try:
            recifrar(faixa, mestra, armazenamento)
            session.commit()
            rel.recifradas.append(faixa.id)
        except (ErroRecifrar, OSError) as e:
            session.rollback()
            rel.falhas.append(str(e))
    for aberto in abertos_restantes(session):
        try:
            apagar_aberto(aberto, mestra)
            rel.apagados.append(aberto.url)
            if aberto.faixa.capitulo_id not in rel.capitulos:
                rel.capitulos.append(aberto.faixa.capitulo_id)
        except (ErroRecifrar, cifra.ErroCifra, OSError) as e:
            rel.falhas.append(str(e))
    return rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="centelha-recifrar", description=__doc__)
    parser.add_argument("--executar", action="store_true", help="sem isto, só lista")
    parser.add_argument("--limite", type=int, help="no máximo N faixas nesta execução")
    args = parser.parse_args(argv)

    cfg = get_settings()
    if not cfg.audio_cifrar:
        print(
            "CENTELHA_AUDIO_CIFRAR está desligada. Recifre só depois que o app decifrar "
            "o .cent: o app atual toca apenas .m4a.",
            file=sys.stderr,
        )
        return 2
    try:
        mestra = cfg.chave_mestra()
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    from ..db import SessionLocal

    with SessionLocal() as session:
        if not args.executar:
            faixas = pendentes(session)
            restantes = abertos_restantes(session)
            print(f"{len(faixas)} faixas .m4a para cifrar:")
            for f in faixas[: args.limite]:
                print(f"  {f.id}  {f.url}")
            print(f"{len(restantes)} .m4a de faixas já cifradas para apagar.")
            print("Nada feito: rode com --executar.")
            return 0
        rel = executar(session, mestra, args.limite)

    print(f"{len(rel.recifradas)} faixas cifradas; {len(rel.apagados)} .m4a apagados.")
    for falha in rel.falhas:
        print(f"falha: {falha}", file=sys.stderr)
    urls = rel.para_purgar(cfg.api_url_publica)
    if rel.capitulos and not cfg.api_url_publica:
        print(
            "Sem CENTELHA_API_URL_PUBLICA: purgue também /v1/capitulos/<id> dos capítulos "
            + ", ".join(map(str, rel.capitulos)),
            file=sys.stderr,
        )
    if urls:
        if cfg.cloudflare_zone_id and cfg.cloudflare_token:
            try:
                purgar(urls, cfg.cloudflare_zone_id, cfg.cloudflare_token, _enviar)
                print(f"purge pedido para {len(urls)} URLs.")
            except ErroPurge as e:
                print(f"{e}\nPurgue à mão no painel da Cloudflare:", file=sys.stderr)
                print("\n".join(urls), file=sys.stderr)
                return 1
        else:
            print("Sem CENTELHA_CLOUDFLARE_ZONE_ID/TOKEN. Purgue à mão estas URLs:")
            print("\n".join(urls))
    return 1 if rel.falhas else 0


if __name__ == "__main__":
    sys.exit(main())
