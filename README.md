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

Os testes apagam e recriam as tabelas a cada caso. Com duas sessões rodando testes ao mesmo tempo, aponte cada uma para um banco próprio com `CENTELHA_TEST_DATABASE_URL`.

## Admin: contas e papéis

A API do admin fica em `/v1/admin` e exige `Authorization: Bearer <token>` (token de `POST /v1/admin/sessoes`, válido por 12 h). Os papéis seguem a [especificação](docs-iniciais/MDs/especificacao-plataforma.md): administrador, revisor de texto e revisor de áudio; as permissões de cada um estão em `api/src/centelha_api/dominio/permissoes.py`. Toda ação fica em `registro_auditoria` (`GET /v1/admin/auditoria`).

Direitos de cada edição em `/v1/admin/edicoes/{id}/direitos`: só se aprova com base legal, link https do documento e, em tradução, a data de falecimento do tradutor. Mudar qualquer desses campos devolve o status a pendente. O catálogo público só mostra edição com direitos aprovados: recusar ou alterar os direitos tira a edição do ar na hora.

Não há cadastro aberto. A primeira conta sai da linha de comando, no servidor:

```sh
cd api && uv run centelha-admin criar --email voce@exemplo.org --nome "Seu nome"
# senha pedida no terminal, ou em CENTELHA_ADMIN_SENHA (mínimo 12 caracteres)
```

Fluxo editorial do capítulo: `importado → texto_revisado → audio_gerado → audio_revisado → publicado`. Para mudar de estado, `POST /v1/admin/capitulos/{id}/transicoes` com a ação; `GET /v1/admin/capitulos/{id}` lista as ações que o usuário logado pode tomar. A tabela de transições está em `api/src/centelha_api/dominio/editorial.py`. O texto só se edita com o capítulo em `importado`; depois disso, é preciso reabrir o texto.

Para gerar o áudio, `POST /v1/admin/capitulos/{id}/gerar-audio` com as vozes (`GET /v1/admin/vozes`), por um administrador ou revisor de áudio. A rota só enfileira; o worker sintetiza e leva o capítulo a `audio_gerado`. O motor de TTS sai da voz escolhida, e a resposta traz `caracteres_estimados`, que é a base de cobrança dos motores em nuvem.

Dicionário de pronúncia em `/v1/admin/pronuncias` (revisor de áudio ou administrador). Criar, alterar ou apagar uma entrada devolve `capitulos_afetados`: os capítulos com áudio cuja síntese usaria a entrada, pela mesma regra da pipeline (termo mais longo primeiro, palavra inteira). `POST /v1/admin/pronuncias/{id}/regenerar` enfileira esses capítulos de novo, com as vozes da última geração. Capítulos publicados ficam de fora até alguém despublicar.

## Deploy

VPS própria, um container por serviço, Cloudflare no DNS. Ver [ADR 0001](docs/decisoes/0001-deploy-vps-docker-cloudflare.md) e `infra/docker-compose.prod.yml`.
