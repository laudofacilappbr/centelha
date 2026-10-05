# Centelha

App gratuito de audiolivros espíritas (iOS e Android) com as obras de Allan Kardec em domínio público, narradas com TTS e revisadas por pessoas. Inclui leitura acompanhada, uso offline e perfis Jovem e Kids com a mascote Clara.

- Plano e fases: [docs/ROADMAP.md](docs/ROADMAP.md) e [issues](https://github.com/laudofacilappbr/centelha/issues)
- Decisões: [docs/decisoes/](docs/decisoes/)
- Especificação, pesquisa e marca: [docs-iniciais/](docs-iniciais/)

## Estrutura

| Pasta | O que é |
| --- | --- |
| `api/` | API FastAPI + PostgreSQL (modelo de dados, direitos, lista de espera) |
| `site/` | Site www e landing page em Astro, servido por nginx |
| `infra/` | Docker Compose de dev e produção (VPS + Cloudflare), Caddyfile |

## Rodar localmente

Tudo em containers:

```sh
docker compose -f infra/docker-compose.yml up --build
# site: http://localhost:8080  ·  api: http://localhost:8000/docs
```

Só a API, com testes:

```sh
docker run -d --name centelha-pg-test -e POSTGRES_USER=centelha -e POSTGRES_PASSWORD=centelha \
  -e POSTGRES_DB=centelha_test -p 55432:5432 postgres:17-alpine
cd api && uv sync && uv run pytest
```

## Deploy

VPS própria, um container por serviço, Cloudflare no DNS. Ver [ADR 0001](docs/decisoes/0001-deploy-vps-docker-cloudflare.md) e `infra/docker-compose.prod.yml`.
