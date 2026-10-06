# Dossiê para o parecer de direitos autorais (#3)

Preparado em 2026-10-06 pelo agente, para o(a) advogado(a) que vai emitir o parecer. **Não é parecer jurídico.** Reúne a lei, as licenças e os termos que se aplicam às seis perguntas da #3, com a fonte de cada afirmação, e marca o que precisa de confirmação profissional (**A CONFIRMAR**).

## O projeto em uma frase

O Centelha publica, num app gratuito para iOS e Android e num site, audiolivros das obras de Allan Kardec na tradução de Guillon Ribeiro, narrados por voz sintética (TTS), com o texto acompanhando a narração. Não vende conteúdo; aceita apoio voluntário (#40) e divulga campanhas de doação de instituições parceiras (#41). Titular, por ora: pessoa física (#4, opção A).

## Resumo

| # | Pergunta | Resposta provável | Risco |
| --- | --- | --- | --- |
| 1 | A tradução de Guillon Ribeiro está livre? | Sim, desde 1º/1/2014, **se** a edição usada não tiver acréscimos de terceiros | Baixo, com edição antiga (#2) |
| 2 | O motor de TTS permite distribuir o áudio? | **Piper: há impedimento provável** nas vozes pt-BR (ver abaixo). Azure: sim, em assinatura paga | **Alto (Piper)** |
| 3 | O audiolivro é nosso? Podemos protegê-lo? | Sim, como fonograma (direito conexo do produtor) | Baixo |
| 4 | Como creditar? | Autor, tradutor, edição-fonte e aviso de voz sintética | Baixo |
| 5 | Adaptações infantis ficam livres? | Sim, se feitas de texto em domínio público | Baixo |
| 6 | Critério para obras futuras | Checklist da seção 6 | — |

**Ponto que pede ação antes do parecer:** as três vozes pt-BR do Piper escolhidas na [ADR 0005](../decisoes/0005-tts-piper-agora-azure-depois.md) derivam de um modelo treinado com dados licenciados **só para pesquisa** (pergunta 2).

---

## 1. Edição-fonte: a tradução de Guillon Ribeiro

**Fatos**
- Allan Kardec morreu em 1869: os originais franceses estão em domínio público.
- Luís Olímpio Guillon Ribeiro nasceu em 17/1/1875 e morreu em 26/10/1943 ([O Consolador](https://www.oconsolador.com.br/ano6/284/cartaaoleitor_ingles.html)). Traduziu quase toda a obra de Kardec para a FEB.
- Decisão do dono (#2): usar uma edição FEB antiga (décadas de 1940–1950), digitalizada.

**Lei 9.610/98**
- Art. 7º, XI: protege "as adaptações, traduções e outras transformações de obras originais, apresentadas como criação intelectual nova". A tradução tem direito próprio, independente do original.
- Art. 14: "É titular de direitos de autor quem adapta, traduz, arranja ou orquestra obra caída no domínio público", sem poder se opor a outra tradução que não seja cópia da sua.
- Art. 41: os direitos patrimoniais "perduram por setenta anos contados de 1º de janeiro do ano subseqüente ao de seu falecimento".
- Art. 45: pertencem ao domínio público as obras em que o prazo expirou.

**Conta:** morte em 1943 → prazo corre de 1º/1/1944 → 70 anos → **domínio público desde 1º/1/2014**.

**Riscos e o que confirmar**
- Edições posteriores podem trazer notas, prefácios, revisão do texto ou fixação feitas por terceiros; cada acréscimo tem prazo próprio. A edição antiga elimina a dúvida, e o ano da folha de rosto é a prova (#2).
- **A CONFIRMAR:** a atualização ortográfica feita pelo pipeline (grafia de 1943 para a atual) é ato técnico, sem criação intelectual nova, e não gera direito de terceiro nem nosso. Também confirmar que ela não fere a integridade da obra (art. 24, §2º: "Compete ao Estado a defesa da integridade e autoria da obra caída em domínio público").
- **A CONFIRMAR:** a FEB tem alguma pretensão sobre a tradução (contrato de cessão com o tradutor, por exemplo) que sobreviva ao prazo do art. 41? Em princípio não: a cessão não estende o prazo.

## 2. Voz sintética e termos do motor de TTS

### Piper (motor atual, ADR 0005)

| Item | Licença | Fonte |
| --- | --- | --- |
| Motor (código) | GPL-3.0 | ADR 0005 |
| Dados das vozes `faber`, `cadu`, `jeff` (pt-BR) | CC0 | MODEL_CARD de cada voz em `rhasspy/piper-voices` |
| **Checkpoint de origem** das três vozes | "U.S. English lessac voice (medium quality)" | os mesmos MODEL_CARDs |
| Dados do `lessac` | Licença Blizzard 2013 (Lessac Technologies) | [licença](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html) |

A licença Blizzard 2013 concede uso "exclusively for Research Purposes only" e exclui do conceito de pesquisa o uso "for any commercial purpose, including the development, marketing, commercialisation, sale or licencing of voice synthesis or speech recognition products or services". O mantenedor do Piper diz que não pode dar orientação jurídica e que "it is the responsibility of the end user to make the ultimate judgement" ([discussão #271](https://github.com/rhasspy/piper/discussions/271)).

**Leitura do agente:** as três vozes pt-BR são ajustes finos de um modelo treinado com esses dados. Mesmo gratuito, o Centelha é um serviço público de síntese de voz nas lojas, com apoio financeiro voluntário; isso dificilmente cabe em "Research Purposes".

**A CONFIRMAR (prioridade):**
- a restrição da licença dos dados alcança um modelo derivado (pesos ajustados) e o áudio que ele gera?
- um app gratuito com apoio voluntário é "commercial purpose" nos termos dessa licença?
- qual a lei aplicável e o risco prático (a licença é de uma universidade escocesa para dados de uma empresa americana)?

**Saídas técnicas, se o parecer confirmar o impedimento** (decisão do dono em #1):
1. migrar já para o Azure (adaptador pronto; custo por caractere);
2. treinar uma voz pt-BR **do zero** com os dados CC0 (o `faber` é CC0), sem partir do `lessac`: sem custo de licença, mas exige GPU e semanas, e a qualidade é incerta;
3. outro modelo aberto com licença comprovadamente permissiva nos pesos **e** nos dados (a levantar).

### Azure (migração prevista na ADR 0005)

Segundo respostas da Microsoft em seu fórum oficial ([Q&A 1192398](https://learn.microsoft.com/en-us/answers/questions/1192398/can-i-use-azure-text-to-speech-for-commercial-usag), [Q&A 652774](https://learn.microsoft.com/en-us/answers/questions/652774/usage-license-of-wav-mp3-generated-by-azure-text-2)): o áudio gerado pode ser usado comercialmente, sem royalties, desde que o recurso seja de assinatura paga e o texto de entrada seja do cliente ou licenciado. O [código de conduta](https://learn.microsoft.com/legal/cognitive-services/speech-service/text-to-speech/code-of-conduct) exige informar que a voz é sintética.

**A CONFIRMAR:** essas respostas não são o contrato. Conferir nos Microsoft Product Terms / termos do Azure AI Speech vigentes: titularidade do áudio, uso em app gratuito distribuído nas lojas, e se o nível gratuito (F0) proíbe distribuição.

### Quem é titular do áudio

Não há intérprete humano, então não há direito conexo de artista (arts. 89 e seguintes). O que existe é o fonograma (pergunta 3).

## 3. O audiolivro é obra nossa? Podemos protegê-lo contra cópia?

**Lei 9.610/98**
- Art. 5º, IX: fonograma é "toda fixação de sons de uma execução ou interpretação ou de outros sons, ou de uma representação de sons".
- Art. 5º, XI: produtor é "a pessoa física ou jurídica que toma a iniciativa e tem a responsabilidade econômica da primeira fixação".
- Art. 93: o produtor de fonogramas tem o direito exclusivo de autorizar ou proibir reprodução, distribuição, comunicação ao público e outras formas de uso.
- Art. 96: "É de setenta anos o prazo de proteção aos direitos conexos, contados a partir de 1º de janeiro do ano subseqüente" à fixação.
- Art. 107, I: pune quem altera, suprime ou inutiliza dispositivos técnicos destinados a evitar ou restringir cópia.

**Leitura do agente:** o texto é livre, mas cada faixa gerada pelo Centelha é um fonograma, e o Centelha, como produtor, tem direito conexo sobre ele por 70 anos. Isso sustenta a proteção contra cópia decidida em #73 ([ADR 0004](../decisoes/0004-audio-cifrado-e-chave-atestada.md)) e a reação a quem republicar o áudio. As marcações de tempo e a leitura acompanhada reforçam o caráter de produto próprio. Ninguém fica impedido de ler o mesmo texto em domínio público e gravar o próprio áudio.

**A CONFIRMAR:**
- som produzido inteiramente por máquina, sem execução humana, é "fixação de outros sons" e gera direito conexo ao produtor?
- produtor pessoa física (#4) é titular sem formalidade adicional?
- a proteção técnica (art. 107) vale sobre fonograma de obra em domínio público?

## 4. Créditos obrigatórios

**Lei 9.610/98**
- Art. 24, II: direito moral de "ter seu nome, pseudônimo ou sinal convencional indicado ou anunciado, como sendo o do autor". Vale para Kardec e para Guillon Ribeiro, como tradutor, e não prescreve com o domínio público.
- Art. 53, parágrafo único: o editor deve mencionar, em cada exemplar, os dados de identificação da obra; no caso de obra traduzida, o título original e o nome do tradutor (**A CONFIRMAR** a redação exata e se o app é "exemplar" para esse fim).

**Proposta de crédito** (app, site e ficha das lojas), por edição:
> *O Livro dos Espíritos*, de Allan Kardec (*Le Livre des Esprits*, 1857). Tradução de Guillon Ribeiro, edição FEB de [ano] ([fonte]). Narração por voz sintética ([motor]). Áudio e leitura acompanhada: Centelha.

O aviso de voz sintética também é exigido pelo código de conduta do Azure e recomendado pelas lojas.

## 5. Adaptações infantis e juvenis (#49)

- Art. 14: quem adapta obra em domínio público é titular da adaptação, sem impedir outras adaptações.
- Adaptar a partir do original francês ou de Guillon Ribeiro (ambos livres) dá ao Centelha a titularidade da adaptação, sem terceiros.
- Art. 24, §2º: o Estado defende a integridade da obra em domínio público. Uma adaptação apresentada **como adaptação**, com crédito ao original, não deve ferir a integridade.

**A CONFIRMAR:** a adaptação deve ser rotulada como tal ("adaptado de…") para não ser confundida com o texto de Kardec; algum limite à simplificação de texto doutrinário?

## 6. Critério para obras e traduções futuras (#38, #46)

Uma obra entra quando **todas** as respostas abaixo estão registradas no cadastro de direitos da edição:

1. **Autor:** nome, data de morte e fonte. Domínio público se a morte ocorreu há mais de 70 anos, contando de 1º de janeiro do ano seguinte (art. 41).
2. **Tradutor** (se houver): nome, data de morte e fonte; mesma conta. Tradutor desconhecido: tratar como risco e preferir outra edição.
3. **Edição:** editora, ano e número da edição, com foto da folha de rosto. Acréscimos de terceiros (notas, prefácios, revisões) identificados e excluídos, ou com prazo vencido.
4. **Arquivo:** origem do exemplar ou do digital (quem digitalizou, de onde veio). Texto de portal só como apoio para revisar o OCR, nunca como fonte.
5. **Motor de TTS e voz:** licença do motor, dos pesos da voz **e dos dados de treino de toda a cadeia de checkpoints**.
6. **Créditos:** texto do crédito pronto (seção 4).

Fora desse critério ficam obras psicografadas recentes (Chico Xavier, Divaldo Franco), que exigem licença das editoras.

A skill [`dossie-direitos`](../../.claude/skills/dossie-direitos/SKILL.md) aplica este critério a uma obra ou tradução nova e produz a ficha para o cadastro.

---

## O que o parecer precisa entregar

1. Confirmação ou correção de cada item **A CONFIRMAR**, começando pela pergunta 2 (Piper).
2. O texto de crédito aprovado.
3. Aval ao critério da seção 6, para não haver um parecer por obra.

## Fontes

- Lei 9.610/1998, texto original na [Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/lei/1998/lei-9610-19-fevereiro-1998-365399-publicacaooriginal-1-pl.html); conferir a versão compilada no Planalto (indisponível na consulta).
- MODEL_CARDs das vozes pt-BR em [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices): `faber`, `cadu`, `jeff` (medium).
- [Licença Blizzard 2013 (Lessac)](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html).
- [Piper, discussão #271](https://github.com/rhasspy/piper/discussions/271).
- Microsoft Q&A [1192398](https://learn.microsoft.com/en-us/answers/questions/1192398/can-i-use-azure-text-to-speech-for-commercial-usag) e [652774](https://learn.microsoft.com/en-us/answers/questions/652774/usage-license-of-wav-mp3-generated-by-azure-text-2); [código de conduta do TTS](https://learn.microsoft.com/legal/cognitive-services/speech-service/text-to-speech/code-of-conduct).
- [O Consolador](https://www.oconsolador.com.br/ano6/284/cartaaoleitor_ingles.html), sobre Guillon Ribeiro.
