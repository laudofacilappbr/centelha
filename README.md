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
| `app/` | App Android e iOS em Flutter ([app/README.md](app/README.md)) |
| `infra/` | Docker Compose de dev e produção (VPS + Cloudflare), Caddyfile |

## Rodar localmente

Tudo em containers:

```sh
docker compose -f infra/docker-compose.yml up --build
# site: http://localhost:8080  ·  api: http://localhost:8000/docs
```

Validar antes de abrir PR (tudo em Docker, sem depender do CI do GitHub):

```sh
bash ci/validar.sh            # api + site + infra + app
bash ci/validar.sh imagens    # build das imagens
```

Rodar os testes da API fora do Docker, durante o desenvolvimento:

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

Edição juvenil ou infantil tem um passo a mais antes do áudio: `texto_revisado → doutrina_revisada`, com as ações `aprovar_doutrina` e `reprovar_doutrina` (permissão `APROVAR_DOUTRINA`, só administrador). A IA pode fazer a primeira leitura (#98), mas quem aprova é uma pessoa. Sem esse passo, a geração de áudio é recusada. A geração também recusa voz de outro público: história infantil com voz infantil, obra adulta com voz adulta.

Para gerar o áudio, `POST /v1/admin/capitulos/{id}/gerar-audio` com as vozes (`GET /v1/admin/vozes`), por um administrador ou revisor de áudio. A rota só enfileira; o worker sintetiza e leva o capítulo a `audio_gerado`. O motor de TTS sai da voz escolhida, e a resposta traz `caracteres_estimados`, que é a base de cobrança dos motores em nuvem.

Dicionário de pronúncia em `/v1/admin/pronuncias` (revisor de áudio ou administrador). Criar, alterar ou apagar uma entrada devolve `capitulos_afetados`: os capítulos com áudio cuja síntese usaria a entrada, pela mesma regra da pipeline (termo mais longo primeiro, palavra inteira). `POST /v1/admin/pronuncias/{id}/regenerar` enfileira esses capítulos de novo, com as vozes da última geração. Capítulos publicados ficam de fora até alguém despublicar.

Apoio ao projeto em `PUT /v1/admin/apoio` (só administrador): liga e desliga, quem recebe, valores sugeridos e os meios (compra no app, chave Pix, link https). Nasce desligado. Para ligar, é preciso informar quem recebe, ao menos um meio e um valor. Chave Pix CPF é recusada porque publicaria o documento de quem recebe. O app lê `apoio` em `GET /v1/config` e o site monta `/apoie` com `GET /v1/apoio`, que devolve só `ligado: false` enquanto o apoio estiver desligado. O site só mostra a mudança no próximo build.

Glossário em `/v1/admin/glossario` (só administrador). Cada termo tem uma definição curta e as referências dos trechos de Kardec que a fundamentam (`LE-93`, `LE-C001`). A resposta lista em `nao_resolvidas` as referências que ainda não apontam para trecho publicado. Só se publica um termo com ao menos uma referência resolvida. O slug vira a URL `/glossario/<slug>` e não muda depois de publicado. O site lê `GET /v1/glossario` e monta o índice, a página de cada termo e "Termos desta questão".

Campos de SEO (título até 60 caracteres e descrição até 160, ambos opcionais) em `PUT /v1/admin/edicoes/{id}/seo` e `PUT /v1/admin/capitulos/{id}/seo` (administrador). No post, os mesmos campos vão no corpo do próprio post e passam pela revisão como o texto. Vazio volta ao modelo da página. O SEO fica na edição, não na obra, porque o texto que responde a uma busca é de um idioma só.

Campanhas de caridade em `/v1/admin/instituicoes` e `/v1/admin/campanhas` (só administrador). A instituição parceira tem CNPJ (o dígito verificador é conferido), descrição, chave Pix e página de doação. O dinheiro vai direto para ela. Regras para publicar uma campanha:

- a instituição precisa ter Pix ou página de doação;
- o período não pode cruzar o de outra campanha publicada, porque só uma fica ativa por vez;
- depois de publicada, a campanha não troca de slug nem de instituição.

O resultado (`PUT /v1/admin/campanhas/{id}/resultado`) só entra depois do fim, com o valor que a instituição informar. `GET /v1/config` liga `caridade` só durante uma campanha publicada, pela data do banco. O site monta `/campanhas` com `GET /v1/campanhas` e recalcula no navegador se a campanha é futura, ativa ou encerrada, para não mostrar o Pix depois do fim.

## Deploy

VPS própria, um container por serviço, Cloudflare no DNS. Ver [ADR 0001](docs/decisoes/0001-deploy-vps-docker-cloudflare.md) e `infra/docker-compose.prod.yml`. Passo a passo da primeira vez, deploy automático e volta de versão em [docs/deploy.md](docs/deploy.md).
