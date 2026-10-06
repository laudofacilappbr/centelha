# O Evangelho segundo o Espiritismo — tradução de Guillon Ribeiro (texto de trabalho)

Ficha da skill [`dossie-direitos`](../../../.claude/skills/dossie-direitos/SKILL.md), 2026-10-06, para a #13, com a decisão do dono na #2. Não é parecer jurídico.

| Item | Valor | Fonte |
| --- | --- | --- |
| Autor / morte | Allan Kardec, 31/3/1869 | ficha do [original](evangile-selon-le-spiritisme-fr.md) |
| Tradutor / morte | Luís Olímpio Guillon Ribeiro, 26/10/1943 | [dossiê](../dossie-direitos.md), seção 1 |
| Domínio público desde | 1º/1/2014 (tradução) | art. 41 da Lei 9.610/98 |
| Edição do arquivo | FEB, 131ª edição, 1ª impressão (Edição Histórica), 1/2013, ISBN 978-85-7328-730-1; "Copyright © 1944 by FEB"; "Texto revisado conforme o Novo Acordo Ortográfico" | folha de rosto do PDF (p. 5) |
| Arquivo | `Evangelho-Segundo-O-Espiritismo-Guillon-131aEd-1_2013.pdf`, 417 páginas, 15.192.334 bytes, SHA-256 `20d373283f54ffd9e846034675e9d03b10e4be233a5b8371714aced723957137` | [site da FEE Fraternidade](https://feefraternidade.org.br/wp-content/uploads/2025/03/Evangelho-Segundo-O-Espiritismo-Guillon-131aEd-1_2013.pdf), baixado em 2026-10-06 |
| Quem digitalizou | Não é digitalização: é o miolo de impressão da FEB (InDesign CS6, 30/1/2013) | metadados do PDF |
| Acréscimos de terceiros | "Nota da Editora" (p. 12), "Explicação" assinada "A Editora" (p. 14), 17 notas de rodapé "N.E." (de 1947, 1948 e atuais), "Nota Explicativa" (p. 372–376), "Índice Geral" e páginas finais de divulgação; atualização ortográfica de 2013 | leitura do PDF |

**Como o texto foi extraído (#13).**

```sh
centelha-ingestao Evangelho-...-2013.pdf --paginas 16-371 --json ese.json
```

- As páginas 16–371 vão do Prefácio ao fim do capítulo XXVIII. Ficam de fora a folha de rosto, o sumário, a Nota da Editora, a "Explicação", a Nota Explicativa e o índice.
- O leitor descarta as 17 notas "N.E.". As 10 restantes são de Kardec ("Nota de Allan Kardec: …") e ficam como segmento "nota", com uma exceção, descrita abaixo.

Saída: 30 capítulos (Prefácio, Introdução e capítulos I a XXVIII) e 1.709 segmentos.

**O que a revisão de texto precisa olhar.**
- A nota "Nota do Sr. Pezzani: *Non odit*…" (cap. XXIII) ficou. **A CONFIRMAR (editorial):** está no original francês de Kardec ou foi acrescentada?
- Os subtítulos internos ("Moisés", "Instruções dos Espíritos") entram como parágrafos.

**A CONFIRMAR.**
- **(#3, advogado):** a revisão ortográfica de 2013 feita pela FEB é ato técnico, sem criação nova, e não gera direito que impeça o uso? O pipeline normaliza a grafia de qualquer forma.
- **(#2, antes do áudio):** conferir por amostragem contra o exemplar FEB de 1949 que só a grafia mudou. Comparar a introdução e um capítulo inteiro.

**Crédito:** *O Evangelho segundo o Espiritismo*, de Allan Kardec, tradução de Guillon Ribeiro. Texto conferido com a edição FEB de [ano do exemplar]. Narração por voz sintética ([motor]). Áudio e leitura acompanhada: Centelha.

**Campos para o admin (`Direitos`):** falecimento_tradutor = 1943-10-26 · base_legal = "Tradução de Guillon Ribeiro (†1943), domínio público desde 1º/1/2014 (Lei 9.610/98, art. 41). Sem notas, explicações e nota explicativa da editora (FEB)." · documento_url = <fotos da folha de rosto do exemplar antigo, na #2>
