# Piper — vozes francesas (fr_FR, medium)

Ficha da skill [`dossie-direitos`](../../../.claude/skills/dossie-direitos/SKILL.md), 2026-10-06, para a #45. Não é parecer jurídico. Segue a cadeia de checkpoints até os dados de treino, como pede a skill.

| Voz | Dados de treino (licença) | Ajustada a partir de | Fonte |
| --- | --- | --- | --- |
| `fr_FR-siwis-medium` | SIWIS (Edinburgh DataShare), **CC BY 4.0** | **`en_US-lessac` medium** | [MODEL_CARD](https://huggingface.co/rhasspy/piper-voices/raw/main/fr/fr_FR/siwis/medium/MODEL_CARD) |
| `fr_FR-upmc-medium` | upmc-pierre-data, **CC BY-SA 4.0** | **`en_US-lessac` medium** | [MODEL_CARD](https://huggingface.co/rhasspy/piper-voices/raw/main/fr/fr_FR/upmc/medium/MODEL_CARD) |
| `fr_FR-tom-medium` | French-tts-model-piper, **AGPLv3** | **não informado** ("See URL") | [MODEL_CARD](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/tom/medium/MODEL_CARD) |

**O mesmo problema das vozes pt-BR.** `siwis` e `upmc` foram ajustadas a partir do `en_US-lessac`, cujos dados (Blizzard 2013) são licenciados "exclusively for Research Purposes" e excluem uso comercial em "voice synthesis … products or services" (dossiê da #3, pergunta 2). Se o parecer confirmar a restrição para as vozes pt-BR, ela vale também para estas.

**`tom`:** dados sob AGPLv3, uma licença de software aplicada a dados de voz; não está claro o que ela exige de quem distribui áudio gerado. A cadeia de checkpoints não está documentada no MODEL_CARD. **A CONFIRMAR:** abrir o repositório de origem e ver se partiu de algum checkpoint.

**Atribuição:** mesmo que a cadeia seja liberada, `siwis` (CC BY) e `upmc` (CC BY-SA) exigem crédito aos dados, e o BY-SA pode exigir compartilhar derivados sob a mesma licença. **A CONFIRMAR (advogado):** o áudio sintetizado é "obra derivada" dos dados para fins da licença?

**Riscos**
- Licença de pesquisa na cadeia (`lessac`): alta, igual à das vozes pt-BR.
- BY-SA e AGPL nos dados: incerta.

**Leitura do agente:** a narração em francês deve seguir a decisão do motor em #1. Se o Piper ficar só em desenvolvimento, o francês sai pelo motor do lançamento (Azure tem vozes neurais `fr-FR`), e esta ficha só importa para amostras internas.
