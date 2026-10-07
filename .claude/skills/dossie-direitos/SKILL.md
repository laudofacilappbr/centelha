---
name: dossie-direitos
description: Levanta os direitos de uma obra, tradução ou voz de TTS antes de entrar no Centelhar e produz a ficha para o cadastro de direitos da edição, com fonte para cada fato e o que pede confirmação jurídica. Use ao avaliar uma obra ou tradução nova (Catálogo 2, outros idiomas, adaptações), ao trocar de motor ou de voz de TTS, ou quando o dono perguntar "podemos publicar X?". Não substitui o parecer de advogado(a): prepara o material para ele.
---

# Dossiê de direitos de uma obra ou voz

Aplica o critério da seção 6 de [docs/juridico/dossie-direitos.md](../../../docs/juridico/dossie-direitos.md) a um caso novo. A regra do repositório não muda: nada é publicado sem direitos aprovados no admin (`dominio/publicacao.py`), e quem aprova é uma pessoa, não o agente.

## Recusas

- **Não afirme que algo está livre sem a fonte.** Data de morte, ano da edição e licença vêm de documento citável (link, foto, catálogo de biblioteca). Sem fonte, o item fica **A CONFIRMAR**.
- **Não aprove direitos no admin** nem mude `status` de `Direitos`. O agente prepara a ficha; o dono aprova.
- **Não trate texto de portal como fonte.** Portais trazem revisões e notas próprias; servem só para conferir o OCR.
- **Não pare no primeiro modelo.** Voz de TTS herda as restrições de toda a cadeia: motor, pesos da voz, checkpoint de origem e dados de treino de cada etapa.

## Passos para uma obra ou tradução

1. **Autor.** Nome completo, data de morte, fonte. Conta do art. 41 da Lei 9.610/98: domínio público a partir de 1º de janeiro do ano seguinte ao 70º aniversário da morte (morte em 1943 → livre desde 1º/1/2014).
2. **Tradutor ou adaptador.** Mesma conta, com fonte. Tradução tem direito próprio (art. 7º, XI; art. 14). Tradutor não identificado = risco: procure outra edição.
3. **Edição.** Editora, cidade, ano, número da edição. Liste acréscimos de terceiros (notas, prefácios, revisão, atualização) e o prazo de cada um. Prefira a edição mais antiga em que o texto já esteja completo.
4. **Arquivo.** De onde vem o exemplar ou o digital, quem digitalizou, e a foto da folha de rosto e da ficha catalográfica (sem dados pessoais: o repositório é público).
5. **Créditos.** Escreva o crédito no modelo da seção 4 do dossiê.
6. **Riscos.** Uma linha por risco, com probabilidade e o que o reduz.

## Passos para um motor ou voz de TTS

1. Licença do **motor** (código).
2. Licença dos **pesos** da voz.
3. **Checkpoint de origem** (MODEL_CARD, campo de fine-tune). Repita os passos 2 e 3 até chegar a um modelo treinado do zero.
4. Licença dos **dados de treino** de cada modelo da cadeia. Procure "research", "non-commercial", "NC" e "no derivatives".
5. Termos do serviço, se for API paga: titularidade do áudio, uso comercial, nível gratuito, exigência de aviso de voz sintética.

Exemplo real: as vozes pt-BR do Piper têm dados CC0, mas foram ajustadas a partir do `en_US-lessac`, cujos dados (Blizzard 2013) são só para pesquisa. Ver a pergunta 2 do dossiê.

## Saída

Uma ficha em `docs/juridico/fichas/<obra-ou-voz>.md`:

```markdown
# <Obra> — <tradução/edição> (ou <motor>:<voz>)

| Item | Valor | Fonte |
| --- | --- | --- |
| Autor / morte | | |
| Tradutor / morte | | |
| Domínio público desde | | cálculo do art. 41 |
| Edição | | foto da folha de rosto |
| Acréscimos de terceiros | | |
| Arquivo | | |

**Crédito:** …

**Riscos:** …

**A CONFIRMAR (advogado):** …

**Campos para o admin (`Direitos`):** falecimento_tradutor = AAAA-MM-DD · base_legal = "…" · documento_url = <onde está o documento, fora do repositório>
```

Depois, comente na issue da obra o link da ficha e o que precisa do dono ou do advogado. Se faltar uma decisão (por exemplo, escolher entre duas edições), aplique `decisao` com as opções; se faltar ação fora do computador (conseguir o exemplar), aplique `manual`.
