# 0005 — Motor de TTS: Piper agora, Azure depois

Data: 2026-10-06 · Status: aceita (#1)

## Contexto

O motor de TTS define o custo e a percepção de qualidade do catálogo. As opções estão em #1: Azure (A), Google (B), ElevenLabs (C) e Piper (D). O dono escolheu começar com D e migrar para A depois.

## Decisão

- **Motor inicial: Piper**, num container próprio (`infra/piper`, serviço `piper`). Ele roda o servidor HTTP oficial do Piper (`piper-tts` 1.8.0), só na rede interna, e o worker chama `POST /synthesize` com o texto e a voz (`CENTELHA_PIPER_URL`).
  - Container separado, e não Piper dentro do worker: um serviço por container ([ADR 0001](0001-deploy-vps-docker-cloudflare.md)), e o modelo de cada voz é carregado uma vez, não a cada segmento como na linha de comando.
  - O motor é GPL-3.0. Como roda em outro processo, falando por HTTP, o código da API não importa o Piper.
- **Vozes** (pt-BR, medium, 22 050 Hz), fixas por revisão do repositório `rhasspy/piper-voices` e conferidas por SHA-256 no build:

  | Voz | Papel sugerido |
  | --- | --- |
  | `pt_BR-faber-medium` | Narrador |
  | `pt_BR-cadu-medium` | Pergunta (Livro dos Espíritos) |
  | `pt_BR-jeff-medium` | Alternativa para a escuta |

  As três são masculinas; o Piper não tem voz feminina pt-BR em qualidade medium. A escolha final dos papéis sai da escuta das amostras.
- **Custo:** zero por caractere (`tts_preco_por_milhao["piper"] = 0`). O custo é CPU da VPS: na máquina de desenvolvimento, um minuto de áudio sai em 4 a 7 segundos, com cerca de 120 MB de memória.
- **Sem SSML.** O Piper recebe texto puro, com a normalização e as substituições do dicionário já aplicadas. O IPA do dicionário não chega a ele, e marcas de tempo dentro do bloco também não: a geração é por segmento (`CENTELHA_TTS_MODO=segmento`).

## Migração para o Azure (A)

O adaptador do Azure está pronto. Para migrar:

1. o dono cria a conta e as chaves e as coloca só no `.env` da VPS;
2. as vozes Azure são cadastradas no admin;
3. o catálogo é regerado. Cada regeração cria uma versão nova da faixa, e o app retoma pelo segmento, não pelo tempo;
4. `CENTELHA_TTS_PRECO_POR_MILHAO` recebe o preço do Azure, para o custo por obra aparecer no admin.

## Licenças, para o parecer (#3)

- **Motor:** GPL-3.0. Rodar como serviço não obriga a abrir o código da API; distribuir a imagem do container, sim, obriga a oferecer o código do Piper, que já é público.
- **Dados das vozes:** CC0 (faber, cadu, jeff).
- **Ponto aberto:** as três vozes foram treinadas a partir do checkpoint da voz `en_US-lessac`, cujos dados (Blizzard 2013, Lessac) têm licença própria. É preciso saber se ela alcança o uso de vozes derivadas num app gratuito com apoio voluntário.

## Consequências

- Nenhum terceiro recebe o texto das obras, e não há custo por caractere.
- A qualidade é menor que a do Azure ou do Google (avaliação em #1). Lançar com o Piper pode pesar na nota das lojas: a escuta decide se o MVP sai assim ou espera a migração.
- Mais um container na VPS (`centelha-piper`, cerca de 840 MB de imagem: onnxruntime e as três vozes, de 63 MB cada).
