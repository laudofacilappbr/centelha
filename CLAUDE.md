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

`/centelha-loop` faz uma volta (próxima issue elegível → PR validada em Docker); `/loop /centelha-loop` repete. Definição em [.claude/skills/centelha-loop/SKILL.md](.claude/skills/centelha-loop/SKILL.md).

## Verificação antes de abrir PR

Local, em Docker; o CI do GitHub não valida PR (só publica as imagens quando algo entra na main).

```sh
bash ci/validar.sh            # api: lint, testes com PostgreSQL, migrações · site: build, astro check · infra: compose e Caddyfile
bash ci/validar.sh api        # um alvo só (api, site, infra, imagens)
```

Roda o que está na worktree, com projeto Docker próprio por worktree (sessões em paralelo não colidem) e PostgreSQL em memória. Saída diferente de zero = não abra a PR.

## Não negociável

- Nada é publicado sem direitos aprovados (`dominio/publicacao.py`). Não contorne essa regra.
- Perfil infantil: nenhuma analítica, anúncio, apoio ou link externo.
- Deploy é VPS própria com um container por serviço e Cloudflare na frente ([ADR 0001](docs/decisoes/0001-deploy-vps-docker-cloudflare.md)). Postgres e Redis nunca expostos.
- Mudou modelo? Gere migração com Alembic e confira `alembic check`.
