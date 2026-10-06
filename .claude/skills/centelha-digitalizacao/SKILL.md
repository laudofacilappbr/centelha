---
name: centelha-digitalizacao
description: Converte um exemplar escaneado (PDF ou fotos) de uma obra do Centelha em texto revisado e pronto para a ingestão. Faz OCR com Tesseract em português, limpa cabeçalhos, números de página e hifenização, atualiza a grafia de 1943 para a atual e gera um relatório de revisão com a página do exemplar. Use quando houver um exemplar novo para digitalizar (edição-fonte da #2), para revisar o OCR de uma obra ou para preparar o texto antes da centelha-ingestao.
---

# /centelha-digitalizacao — do exemplar escaneado ao texto revisado

Ferramenta: `centelha-digitalizar` (`api/src/centelha_api/pipeline/digitalizacao/`), que roda no container de digitalização.

## Regras

- **O exemplar manda.** O texto correto é o que está impresso na edição-fonte escolhida (#2, opção A: FEB antiga). Texto digital de portal (KardecPedia, IPEAK…) é só referência para achar erro de OCR, nunca fonte: o que vem dele pode ter revisão com direito próprio.
- **Só grafia e erro de leitura.** Nenhuma palavra de Guillon Ribeiro é trocada por outra. Mudar redação cria texto novo, com direito próprio, e pede revisão doutrinária. Isso é decisão do dono, não do agente.
- **Acervo fora do git.** Escaneados e saídas ficam em `acervo/` (no `.gitignore`); o repositório é público.
- **Origem registrada.** Antes de digitalizar, a issue da edição registra editora, ano, número da edição, de onde veio o arquivo e quem digitalizou (#2).

## Passo 1 — Preparar

```sh
mkdir -p acervo/le-1944                       # um diretório por exemplar
cp ~/Downloads/le-feb-1944.pdf acervo/le-1944/exemplar.pdf
docker build --target digitalizacao -t centelha-digitalizacao api
```

Escaneado bom: 300 dpi ou mais, página reta, sem sombra na lombada. Fotos de celular servem se forem nítidas. Use uma pasta de imagens, em ordem de nome, no lugar do PDF.

## Passo 2 — OCR e processamento

```sh
docker run --rm -v "$PWD/acervo/le-1944:/dados" centelha-digitalizacao \
  tudo exemplar.pdf --saida saida --perfil perguntas
```

- `--perfil perguntas` para o Livro dos Espíritos e o Livro dos Médiuns: o relatório confere a numeração das questões. Para as outras obras, omita a opção.
- `--referencia ref.txt` acrescenta as diferenças contra um texto digital, só para apontar onde olhar.
- Para refazer só o processamento, sem repetir o OCR, que é lento: `processar saida/paginas.txt --saida saida`.

Em `saida/` ficam:
- `paginas.txt`: o OCR cru, com as páginas separadas por `\f`;
- `texto.txt`: o texto limpo, com a grafia atualizada;
- `revisao.md`: o relatório de revisão.

No Windows (Git Bash), prefixe o comando com `MSYS_NO_PATHCONV=1`.

## Passo 3 — Revisar com o exemplar ao lado

Percorra `revisao.md` de cima para baixo, abrindo a página indicada no exemplar, e corrija em `texto.txt`.

| Achado | O que fazer |
| --- | --- |
| Questões faltando ou repetidas | Quase sempre um número mal lido ("8S" por "85") ou um parágrafo grudado no anterior. Confira e separe. |
| dígito em palavra, caractere estranho | Erro de leitura: corrija pela imagem. |
| trema lido como ii, parecida com palavra frequente, rn/m | O OCR trocou letras. A sugestão é um palpite: vale o que está impresso. |
| começa com minúscula | Parágrafo partido na virada da página ou da coluna: junte ao anterior. |
| Circunflexo a conferir | Palavra com ê/ô fora das listas. Corrija no texto e acrescente a palavra à lista certa em `ortografia.py` (`_DIFERENCIAIS` ou `_CIRCUNFLEXO_ATUAL`), com teste. |
| Atualização ortográfica | Leia a tabela de trocas. Troca errada é bug: conserte a regra em `ortografia.py`, com teste, e rode `processar` de novo. |
| diferença (com `--referencia`) | Olhe o exemplar. Se o OCR errou, corrija. Se a referência difere do exemplar, o exemplar vence. |

O relatório não pega tudo: letra maiúscula acentuada lida sem acento ("E" por "É") e maiúscula no meio da frase passam. Uma leitura corrida do texto final continua necessária.

## Passo 4 — Conferir a estrutura e ingerir

```sh
cd api
uv run centelha-ingestao ../acervo/le-1944/saida/texto.txt --perfil perguntas --json ../acervo/le-1944/estrutura.json
```

O resumo mostra capítulos, segmentos, questões e as que faltam. Com tudo certo, grave na edição cadastrada no admin, que precisa ter direitos e fonte registrados:

```sh
uv run centelha-ingestao ../acervo/le-1944/saida/texto.txt --perfil perguntas --edicao-id <id>
```

A partir daí, a revisão segue no admin, capítulo a capítulo, lado a lado com a fonte (estado `importado` → `texto_revisado`).

## Passo 5 — Registrar

Comente na issue da obra:
- edição e origem do arquivo;
- totais do relatório (questões, achados, trocas de grafia);
- regras novas de `ortografia.py`, se houve;
- quem revisou.

Nunca anexe o exemplar nem o texto na issue: o repositório é público.
