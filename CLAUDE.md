# Regras deste repositório

Monorepo do Centelha: `api/` (FastAPI), `site/` (Astro), `infra/` (Docker Compose + Caddy). Plano em [docs/ROADMAP.md](docs/ROADMAP.md), especificação em [docs-iniciais/MDs/](docs-iniciais/MDs/).

## Fluxo de trabalho

Segue `RICARDO-DEFAULT/20-engenharia/fluxo-desenvolvimento/FLUXO-DE-TRABALHO.md`.

- **Pegar tarefa:** label `em-andamento` + comentário com o branch, antes do primeiro commit.
- **Um branch e uma PR por tarefa.** Na PR, `Closes #N` em linha própria, uma por número. Nunca escreva `Closes #N` para dizer que **não** fecha.
- **Labels (§5):** ausência de label = elegível.
  - `decisao`: escolha de negócio, legal, financeira ou de segurança. O agente escreve opções com risco e reversibilidade e **para naquela tarefa**. Vira `decidida` só com a resposta transcrita num comentário.
  - `manual`: senha, cartão, painel ou ação fora do computador. O dono executa e comenta a prova; se sobra trabalho de agente, ele tira a label (handoff).
  - `espera`: precondição que nenhuma sessão destrava pegando trabalho.
  - `p0`…`p3`: prioridade pela fase.

## Loop de desenvolvimento

`/centelha-loop` faz uma volta (próxima issue elegível → PR com CI verde); `/loop /centelha-loop` repete. Definição em [.claude/skills/centelha-loop/SKILL.md](.claude/skills/centelha-loop/SKILL.md).

## Verificação antes de abrir PR

```sh
# API (precisa de PostgreSQL em localhost:55432, ver README)
cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
# Site
cd site && npm run build && npx astro check
```

## Não negociável

- Nada é publicado sem direitos aprovados (`dominio/publicacao.py`). Não contorne essa regra.
- Perfil infantil: nenhuma analítica, anúncio, apoio ou link externo.
- Deploy é VPS própria com um container por serviço e Cloudflare na frente ([ADR 0001](docs/decisoes/0001-deploy-vps-docker-cloudflare.md)). Postgres e Redis nunca expostos.
- Mudou modelo? Gere migração com Alembic e confira `alembic check`.
