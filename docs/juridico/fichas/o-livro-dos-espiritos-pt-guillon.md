# O Livro dos Espíritos — tradução de Guillon Ribeiro (texto de trabalho)

Ficha da skill [`dossie-direitos`](../../../.claude/skills/dossie-direitos/SKILL.md), 2026-10-06, para a #13, com a decisão do dono na #2. Não é parecer jurídico.

| Item | Valor | Fonte |
| --- | --- | --- |
| Autor / morte | Allan Kardec, 31/3/1869 | ficha do [original](le-livre-des-esprits-fr.md) |
| Tradutor / morte | Luís Olímpio Guillon Ribeiro, 26/10/1943 | [dossiê](../dossie-direitos.md), seção 1 |
| Domínio público desde | 1º/1/2014 (tradução) | art. 41 da Lei 9.610/98 |
| Edição do arquivo | FEB, 76ª edição, "Do 1.271º ao 1.320º milheiro", 5/1995; "Copyright 1944 by Federação Espírita Brasileira" | folha de rosto do PDF (p. 6) |
| Arquivo | `ph000028.pdf`, 494 páginas, 1.335.451 bytes, SHA-256 `343f0bb6245172775f1cac6d3abe8a7781bea4faecde936e6a240b9780985795` | [Biblioteca Comum da UEL](https://projetos.uel.br/bibliotecacomum/bc-texto/obras/ph000028.pdf), baixado em 2026-10-06 |
| Quem digitalizou | Edição digital em Word, não digitalização de imagem: metadados "WF Consultoria", assunto "FEB", criada em 20/5/1996. Permissões do PDF liberam cópia de texto | metadados do PDF |
| Acréscimos de terceiros | "Nota da Editora" (p. 4), "Nota Especial nº 1 e nº 2 (à 34ª edição, em 1974)" no fim da p. 494, e a nota de rodapé "Vide Nota Especial nº 2, da Editora (FEB)" | leitura do PDF |

**Como o texto foi extraído (#13).**

```sh
centelha-ingestao ph000028.pdf --paginas 13-494 --cortar-em "Nota Especial" --perfil perguntas --json le.json
```

- As páginas 13–494 vão da Introdução à Conclusão. Ficam de fora a folha de rosto, a "Nota da Editora" e a Tábua das Matérias.
- `--cortar-em` tira as Notas Especiais da FEB, que estão na mesma página da Conclusão.
- O leitor descarta a nota de rodapé que remete à Nota Especial. As outras 7 notas de rodapé são de Kardec e ficam como segmento "nota".

Saída: 32 capítulos, 3.363 segmentos e 1.017 questões, de 1 a 1.019.

**O que a revisão de texto precisa olhar.**
- **Questão 674** aparece como "647." no PDF (p. 328, início de "Da lei do trabalho"). É erro de digitação da edição digital, e o resumo da ingestão a acusa como questão faltando.
- **Questão 1011** não existe: Kardec pulou o número na 2ª edição francesa, e a própria Nota Especial nº 2 da FEB registra isso. Não é erro.
- O título "CAPÍTULO VI — DA LEI DO PROGRESSO" deveria ser VIII. O erro está no PDF.
- O PDF tem a grafia anterior ao Acordo de 1990 ("conseqüência", "idéia"). O pipeline atualiza a grafia.

**A CONFIRMAR (#2, antes do áudio).** Conferir por amostragem contra um exemplar FEB antigo (décadas de 1940–1950), com a introdução, um capítulo inteiro e a q. 88, que o texto do corpo é o de Guillon Ribeiro. A 76ª edição pode ter revisão silenciosa.

**Crédito:** *O Livro dos Espíritos*, de Allan Kardec, tradução de Guillon Ribeiro. Texto conferido com a edição FEB de [ano do exemplar]. Narração por voz sintética ([motor]). Áudio e leitura acompanhada: Centelhar.

**Campos para o admin (`Direitos`):** falecimento_tradutor = 1943-10-26 · base_legal = "Tradução de Guillon Ribeiro (†1943), domínio público desde 1º/1/2014 (Lei 9.610/98, art. 41). Sem as notas da editora (FEB)." · documento_url = <fotos da folha de rosto do exemplar antigo, na #2>
