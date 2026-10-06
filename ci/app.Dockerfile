# Flutter para validar o app (analyze e testes), na mesma versão do desenvolvimento.
# Imagem montada aqui, a partir do repositório oficial, em vez de uma imagem de terceiros.
FROM debian:bookworm-slim

ARG FLUTTER_VERSION=3.47.6
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl unzip xz-utils ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "$FLUTTER_VERSION" https://github.com/flutter/flutter.git /opt/flutter
ENV PATH="/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:$PATH" \
    PUB_CACHE=/cache/pub \
    FLUTTER_SUPPRESS_ANALYTICS=true
# Baixa o Dart SDK e os artefatos do host (flutter_tester) no build, não a cada validação.
RUN flutter config --no-analytics --no-cli-animations >/dev/null \
 && dart --disable-analytics >/dev/null \
 && flutter precache --universal --linux \
 && flutter --version
