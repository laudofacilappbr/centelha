# Piper (TTS local, #1): servidor HTTP oficial do Piper, só na rede interna.
# O worker manda o texto e recebe WAV; nenhum terceiro vê o texto.
#
# Motor GPL-3.0 rodando em container próprio, falando por HTTP: o código da API não
# importa o Piper. Vozes fixas por revisão do repositório e conferidas por SHA-256.
FROM python:3.12-slim

ARG PIPER_VERSION=1.8.0
ARG VOZES_REV=c10ece1aade47bb51c153c893d14e5bf8e5b7117

RUN pip install --no-cache-dir "piper-tts[http]==${PIPER_VERSION}"

# Datasets das três vozes: CC0. Treinadas a partir da voz lessac (en_US), cuja licença
# de dados entra no parecer jurídico (#3). Ver docs/decisoes/0005.
COPY vozes.sha256 /vozes/vozes.sha256
RUN set -eu; cd /vozes; base="https://huggingface.co/rhasspy/piper-voices/resolve/${VOZES_REV}/pt/pt_BR"; \
    for v in faber cadu jeff; do \
      for ext in onnx onnx.json; do \
        python -c "import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" \
          "$base/$v/medium/pt_BR-$v-medium.$ext" "pt_BR-$v-medium.$ext"; \
      done; \
    done; \
    sha256sum -c vozes.sha256

RUN useradd --system --uid 10002 piper
USER piper
EXPOSE 5000
# A voz padrão é só a carregada na partida; o worker escolhe a voz em cada pedido.
CMD ["python", "-m", "piper.http_server", "--host", "0.0.0.0", "--port", "5000", \
     "--data-dir", "/vozes", "-m", "pt_BR-faber-medium"]
