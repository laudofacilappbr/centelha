---
name: revisao-doutrinaria
description: Faz a primeira revisão doutrinária e de linguagem de um capítulo adaptado (juvenil ou infantil) comparado ao original de Kardec, trecho a trecho, e gera o relatório para a pessoa que aprova no admin. Use quando um capítulo de adaptação chegar a "texto revisado" e precisar da revisão de doutrina (#49, #76 opção D, #98), ou quando o dono pedir para conferir uma adaptação. Não aprova nada no admin.
---

# Revisão doutrinária de uma adaptação

Decisão do dono (#76, opção D): a IA faz a **primeira** revisão e aponta os problemas; a aprovação da doutrina no admin (`aprovar_doutrina`) é de uma pessoa.

## Recusas

- **Não aprove nem reprove no admin**, nem mude o estado do capítulo. O resultado é o relatório.
- **Não reescreva o original nem a adaptação.** Se um trecho precisa mudar, diga o que está errado e por quê; a correção é de quem adapta.
- **Não corrija em silêncio.** Todo problema vira um apontamento, com o trecho.
- **Não acrescente doutrina.** Não use conhecimento espírita de fora do original para "completar" a adaptação: a régua é o texto de Kardec daquele capítulo.
- **Na dúvida, "atencao", nunca "ok".** "ok" quer dizer que você leu o par inteiro e não achou nada nas cinco conferências.

## Passos

1. **Montar o par.** No servidor (ou com o banco de desenvolvimento):

   ```sh
   python -m centelha_api.pipeline.revisao_doutrinaria montar --capitulo <id do capítulo adaptado> --saida par.json
   ```

   O original é a edição adulta da mesma obra no mesmo idioma (Guillon Ribeiro para pt-BR); para comparar com o francês, `--original-edicao <id>`. O comando já aponta, sem leitura:
   - link e chamada externa no infantil;
   - edição sem o rótulo "adaptado de";
   - resposta que no original é comentário de Kardec;
   - trecho sem par;
   - questões do original fora da adaptação;
   - frases longas para o público.

2. **Ler cada trecho de `par.json`**: o `original` ao lado da `adaptacao`, e as cinco conferências:
   1. **Fidelidade doutrinária.** A ideia central do original está na adaptação. Nada foi acrescentado como se fosse ensino de Kardec ou dos Espíritos. Nada foi contradito ou suavizado a ponto de mudar o sentido (ex.: "as provas são castigos" no lugar de "as provas são escolhidas para o progresso").
   2. **Atribuição.** Pergunta continua pergunta, resposta dos Espíritos continua deles, e comentário de Kardec não vira fala dos Espíritos (nem o contrário).
   3. **Linguagem para o público.**
      - Infantil: frases curtas, palavras do dia a dia, conceitos abstratos com exemplo concreto.
      - Juvenil: pode ter conceito abstrato, explicado.
      - Nos dois: sem infantilizar e sem assustar (morte, sofrimento e "expiação" tratados com cuidado, sem ameaça).
   4. **Perfil infantil.** Nenhum link, pedido de apoio, loja ou rede social.
   5. **Rótulo de adaptação.** Nada apresenta o texto adaptado como sendo o de Kardec ("Kardec escreveu: …" seguido de texto que não é o original).

3. **Gravar a avaliação** em `avaliacao.json`, um item por trecho de `par.json` (todos, sem exceção):

   ```json
   [
     {"id": "88 · resposta", "nivel": "ok", "motivo": ""},
     {"id": "89 · resposta", "nivel": "bloqueio", "motivo": "fidelidade: diz que o Espírito fica preso ao corpo até o enterro; o original diz que a separação é gradual e varia", "trecho": "fica preso ao corpo até o enterro"}
   ]
   ```

   Os níveis são:
   - `bloqueio`: muda a doutrina, troca a atribuição ou fere a regra do infantil;
   - `atencao`: linguagem ou omissão que uma pessoa precisa olhar;
   - `ok`: nada nas cinco conferências.

   O motivo começa pelo nome da conferência ("fidelidade:", "atribuição:", "linguagem:", "infantil:", "rótulo:") e diz o que o original afirma. `trecho` é a parte exata da adaptação.

4. **Gerar o relatório:**

   ```sh
   python -m centelha_api.pipeline.revisao_doutrinaria relatorio par.json avaliacao.json --saida revisao.md
   ```

   O comando recusa a avaliação incompleta, o nível desconhecido e o apontamento sem motivo, e junta os apontamentos automáticos.

5. **Entregar** o `revisao.md` a quem aprova (comentário na issue do capítulo ou anexo da revisão no admin, quando existir) e dizer em uma linha quantos bloqueios há. Não diga que o capítulo "está aprovado": diga que a revisão da IA não achou bloqueios.
