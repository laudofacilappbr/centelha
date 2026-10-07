# Roadmap

Fases da [especificação](../docs-iniciais/MDs/especificacao-plataforma.md). Cada fase só começa quando a anterior passa no portão. As tarefas estão nas [issues](https://github.com/laudofacilappbr/centelha/issues), agrupadas por [milestone](https://github.com/laudofacilappbr/centelha/milestones).

| Fase | Entrega | Portão |
| --- | --- | --- |
| 0 — Validação | Decisões de voz, edição-fonte e direitos; monorepo, API base, pipeline de texto, site "em breve", VPS | Motor de TTS escolhido, edição-fonte definida, parecer jurídico favorável |
| 1 — MVP | O Evangelho e O Livro dos Espíritos em pt-BR, uma voz, admin, app em teste fechado, landing completa | Teste fechado aprovado |
| 2 — Catálogo e lojas | Catálogo 1 e 2, lojas públicas, apoio e caridade, blog e temas | — |
| 3 — Multilíngue | fr, es, en no app e no site | — |
| 4 — Jovem e Kids | Adaptações com revisão doutrinária, perfil Kids com a Clara | — |

## Arquitetura

```
             Cloudflare (DNS proxied, TLS, cache)
                          │ 443, só IPs da Cloudflare
                    ┌─────▼─────┐   VPS própria, um container por serviço
                    │   Caddy   │
                    └─┬───────┬─┘
            centelhar │       │ api.centelhar
               ┌──────▼─┐   ┌─▼──────┐
               │  site  │   │  api   │──┐
               │ (nginx)│   │FastAPI │  │ rede interna
               └────────┘   └───┬────┘  │
                     ┌──────────▼┐   ┌──▼────┐   ┌─────────┐
                     │ postgres  │   │ redis │◄──│ worker  │ (pipeline, Fase 1)
                     └───────────┘   └───────┘   └─────────┘
```

Fase 1 acrescenta `admin` e `worker`; o áudio vai para storage S3-compatível servido pela Cloudflare.

## Pastas

| Pasta | Serviço |
| --- | --- |
| `api/` | FastAPI, modelo de dados, migrações Alembic |
| `site/` | Site www em Astro, servido por nginx |
| `infra/` | Compose de dev e produção, Caddyfile |
| `docs/decisoes/` | Registros de decisão (ADR) |
| `docs-iniciais/` | Especificação, pesquisa e marca |
