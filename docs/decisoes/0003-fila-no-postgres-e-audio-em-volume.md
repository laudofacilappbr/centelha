# 0003 — Fila de áudio no PostgreSQL e faixas em volume local

Data: 2026-10-05 · Status: aceita (#18, #19)

## Contexto

A especificação sugeria Redis + Celery para a fila e Cloudflare R2 para o áudio. O volume do MVP é pequeno (duas obras, algumas centenas de capítulos, gerados poucas vezes) e o deploy é uma VPS própria ([ADR 0001](0001-deploy-vps-docker-cloudflare.md)).

## Decisão

- **Fila:** tabela `job_audio` no PostgreSQL. O worker reserva com `SELECT … FOR UPDATE SKIP LOCKED` e um lease; worker que morre deixa o lease vencer e outro retoma. Índice parcial garante um job ativo por capítulo. Falha volta à fila com espera de 1, 4 e 9 minutos e desiste na terceira.
- **Relógio:** toda comparação de tempo da fila usa o `now()` do banco. Na máquina de desenvolvimento o relógio do container estava 5 minutos à frente do host; com o relógio do processo, a fila parecia vazia.
- **Áudio:** o worker grava num volume Docker; o Caddy serve esse volume em `audio.{domínio}` com cache eterno (o nome do arquivo leva a versão), e a Cloudflare faz o cache de borda. A interface `Armazenamento` permite trocar por S3/R2 sem mexer no worker.
- **Worker:** imagem própria (`--target worker`, com ffmpeg). Começa como root só para ajustar o dono do volume e roda como usuário sem privilégio.

## Consequências

- Um serviço a menos na VPS (sem Redis para a fila) e nenhuma dependência nova.
- O volume `audio` passa a fazer parte do backup, junto com o banco (#26).
- Se o volume de geração crescer muito (catálogo inteiro, vários idiomas), reavaliar: mais workers resolvem até o banco virar gargalo; storage externo resolve disco.
