---
name: centelha-loop
description: Uma volta do ciclo de desenvolvimento do Centelha — sincroniza a main, limpa o que já entrou, escolhe a próxima issue elegível do GitHub, implementa, valida em Docker (ci/validar.sh) e roda de verdade, e abre a PR. Use com /centelha-loop para uma volta, ou /loop /centelha-loop para repetir. Para sozinha quando não há issue elegível ou quando há PRs demais esperando merge.
---

# /centelha-loop — uma volta do ciclo

Repositório: `laudofacilappbr/centelha` · checkout principal: `D:\REPOSITORIOS\CENTELHA`.
Regras do projeto em `CLAUDE.md` (raiz) e fluxo em `RICARDO-DEFAULT/20-engenharia/fluxo-desenvolvimento/FLUXO-DE-TRABALHO.md`. Este arquivo não as repete: aplica.

Cada volta faz **uma** tarefa, do começo ao PR validado em Docker. Nunca faz merge: merge é do dono.

## Passo 0 — Parar antes de começar?

Pare a volta (e, dentro de `/loop`, encerre o loop) dizendo o motivo, se:

- houver **2 ou mais PRs abertas desta sessão** esperando merge — empilhar gera conflito e PR que não entra na main (aconteceu com #53–#55);
- alguma PR aberta desta sessão estiver **em conflito com a main** (`mergeable: CONFLICTING`) — traga a main para a branch, resolva, rode `ci/validar.sh` e dê push antes de começar outra coisa;
- o Docker não responder (`docker info`) — sem ele não há teste de API nem verificação real.

```sh
gh pr list -R laudofacilappbr/centelha --state open --json number,title,headRefName,mergeable
```

## Passo 1 — Sincronizar e limpar

```sh
cd D:/REPOSITORIOS/CENTELHA && git checkout main && git pull
git worktree list
gh issue list -R laudofacilappbr/centelha --label em-andamento --json number,title
```

- Worktree desta sessão cuja branch já entrou na main: `git worktree remove` + `git branch -d`.
- Issue fechada ainda com `em-andamento`: tirar a label.
- Issue aberta com `em-andamento` cuja PR entrou mas sobrou parte: comentar o que falta e tirar a label (fica elegível de novo).
- **Nunca** remover worktree, branch ou label de outra sessão. Worktree `CENTELHA-<n>` que não é sua é de outra sessão: deixe.

## Passo 2 — Escolher a tarefa

Elegível = aberta **sem** `decisao`, `manual`, `espera`, `em-andamento`:

```sh
gh issue list -R laudofacilappbr/centelha --state open \
  --search "-label:decisao -label:manual -label:espera -label:em-andamento" \
  --json number,title,labels,milestone
```

Ordem: `p0` → `p1` → `p2` → `p3`; dentro da mesma prioridade, a de número menor. Pule (sem rotular) a que:

- é de **área que outra sessão está tocando agora** (veja `em-andamento` e os comentários de reivindicação; ex.: admin com outra sessão no admin);
- depende de ferramenta ausente: app (`area:app`) só se `flutter --version` funcionar;
- depende de outra issue aberta e elegível — faça a outra primeiro.

Ao ler a issue, se descobrir que ela precisa de **decisão humana** (negócio, legal, financeiro, segurança, irreversível) ou de **ação fora do computador** (conta, cartão, painel, chave): aplique `decisao` ou `manual`, comente as **opções com risco e reversibilidade** (ou o que exatamente o dono precisa fazer) e escolha outra tarefa. O agente nunca escolhe sozinho.

Se não sobrar nenhuma elegível: pare e liste o que está esperando o dono (`decisao`, `manual`) e o que está em `espera`.

## Passo 3 — Reivindicar, antes do primeiro commit

```sh
N=<número>; B=<tipo>/$N-<slug>          # feat/, fix/, chore/
cd D:/REPOSITORIOS/CENTELHA
git worktree add -b $B ../CENTELHA-$N main
gh issue edit $N -R laudofacilappbr/centelha --add-label em-andamento
gh issue comment $N -R laudofacilappbr/centelha -b "Pegando. Branch: \`$B\`, worktree \`CENTELHA-$N\`. <escopo desta volta>"
```

Se outra sessão comentou reivindicação antes (mesmo segundos antes): solte, remova a worktree, escolha outra.
Vai mexer em `models.py`, `main.py`, `pyproject.toml` ou criar migração? Avise as outras sessões ativas (`ListAgents` → `SendMessage`) com os arquivos e a migração-pai.

## Passo 4 — Implementar

Trabalhe só dentro de `../CENTELHA-$N`.

- Leia a issue, a especificação relevante em `docs-iniciais/MDs/` e o código vizinho. Escreva como o código ao redor (português no domínio, comentário só onde há motivo não óbvio).
- Escreva o teste que importa junto com o código. API: testes contra PostgreSQL real, **banco próprio**:
  ```sh
  docker start centelha-pg-test || docker run -d --name centelha-pg-test -e POSTGRES_USER=centelha \
    -e POSTGRES_PASSWORD=centelha -e POSTGRES_DB=centelha_test -p 55432:5432 postgres:17-alpine
  docker exec centelha-pg-test sh -c "dropdb -U centelha --if-exists centelha_test_$N; createdb -U centelha centelha_test_$N"
  cd api && uv sync && CENTELHA_TEST_DATABASE_URL="postgresql+psycopg://centelha:centelha@localhost:55432/centelha_test_$N?connect_timeout=5" uv run pytest -q
  ```
- Mudou modelo: `alembic revision --autogenerate` num banco descartável, confira `down_revision` (= head atual da main), que o downgrade remove tipos enum criados, e rode upgrade → check → downgrade → upgrade. **Uma head só** (`alembic heads`).
- Dependência nova só se não houver alternativa razoável; `uv lock`, nunca editar `uv.lock` à mão.
- Tempo em fila/agendamento: relógio do banco (`func.now()`), não do processo — o container está minutos à frente do host.

## Passo 5 — Verificar de verdade

A validação é local, em Docker — o CI do GitHub não é usado. Antes da PR, na worktree:

```sh
bash ci/validar.sh            # api (lint, testes, migrações) + site (build, astro check) + infra
bash ci/validar.sh imagens    # se mexeu em Dockerfile: build das imagens api, worker e site
```

Tem que terminar com `ok` em todos os alvos e código de saída 0. Teste verde não basta:

E rode a coisa: API/worker em containers (`docker compose -p centelha$N -f infra/docker-compose.yml up -d --build ...`), site com `npm run preview` e captura em Chrome headless (`--user-data-dir` próprio no scratchpad; o navegador do DevTools pode estar com outra sessão). Ao terminar, derrube o que subiu (`docker compose -p centelha$N down -v`) e apague o banco de teste — só o que for seu.

Se não conseguiu verificar algo, diga na PR o quê e por quê. Nunca afirme verificação que não fez.

## Passo 6 — PR

```sh
git add <arquivos> && git commit   # mensagem conta a decisão, não só o diff; termina com o Co-Authored-By da sessão
git push -u origin $B
gh pr create -R laudofacilappbr/centelha --base main --title "<título>" --body-file -
```

Corpo da PR: o que muda, o resultado do `ci/validar.sh` (alvos e número de testes), o que foi verificado rodando de verdade (e como), o que **não** foi, o que falta na issue. `Closes #N` **em linha própria, uma por número**, só se a issue fecha inteira; se sobra parte, diga "parte de #N" e o que falta. PR sempre na `main` — nunca empilhada sobre outra branch.

Não espere checks do GitHub: a PR não tem. Se a main andou enquanto você trabalhava, traga-a para a branch (`git merge origin/main`), resolva conflitos e rode `ci/validar.sh` de novo antes do push.

## Passo 7 — Fechar a volta

- `git worktree remove ../CENTELHA-$N` (a branch fica no remoto, na PR).
- Mantenha `em-andamento` até a PR entrar (o passo 1 da próxima volta limpa).
- Relatório curto ao dono: issue e PR (links), o que foi verificado, o que ficou de fora, o que precisa dele (merge, decisão, ação manual), e se a próxima volta vai parar no passo 0.
